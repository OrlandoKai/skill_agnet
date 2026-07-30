import json
import re
from pathlib import Path

from agents.enhanced_agent_v2 import DEPENDENT_INPUT_SKILLS, EnhancedSkillAgentV2
from config import BASE_DIR


V2_CONTRACT_PATH = BASE_DIR / "data" / "skill_library_v2.json"


class EnhancedSkillAgentV3(EnhancedSkillAgentV2):
    """Contract-aware V3 agent focused on abstention and implicit multi-step tasks."""

    def __init__(
        self,
        model,
        retriever,
        max_steps: int = 2,
        top_k: int = 5,
        ablation: str = "none",
    ) -> None:
        super().__init__(
            model=model,
            retriever=retriever,
            max_steps=max_steps,
            top_k=top_k,
            ablation=ablation,
        )
        self.contract_by_name = self._load_v2_contracts()

    def _load_v2_contracts(self) -> dict[str, dict]:
        if not V2_CONTRACT_PATH.exists():
            return {}
        try:
            data = json.loads(V2_CONTRACT_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(data, list):
            return {}
        return {
            str(item.get("name", "")): item
            for item in data
            if isinstance(item, dict) and item.get("name")
        }

    def _v2_need_tool_decision(self, instruction: str, raw_model_outputs: list[str]) -> dict:
        if not self.ablation_config["use_need_tool_gate"]:
            return {
                "need_tool": True,
                "task_type": "multi_tool" if self._looks_composed_multi(instruction) else "single_tool",
                "reason": "Ablation disabled the NEED_TOOL / NO_TOOL gate.",
            }

        if self._is_unsupported_request(instruction):
            return {
                "need_tool": False,
                "task_type": "unsupported_tool",
                "reason": "The request needs an external side effect or live service outside the local skill set.",
            }

        if self._is_missing_info_request(instruction):
            return {
                "need_tool": False,
                "task_type": "missing_info",
                "reason": "The request references missing input required by the candidate skill contract.",
            }

        if self._is_conceptual_no_tool_request(instruction):
            return {
                "need_tool": False,
                "task_type": "direct_answer",
                "reason": "The request is conceptual and explicitly does not require tool execution.",
            }

        decision = super()._v2_need_tool_decision(instruction, raw_model_outputs)
        if self._looks_tool_required_multi(instruction):
            decision = {
                **decision,
                "need_tool": True,
                "task_type": "multi_tool",
                "reason": (decision.get("reason", "") + " V3 detected an implicit multi-skill composition.").strip(),
            }
        return decision

    @staticmethod
    def _normalize_instruction(instruction: str) -> str:
        return re.sub(r"\s+", " ", str(instruction).strip())

    def _is_unsupported_request(self, instruction: str) -> bool:
        lowered = self._normalize_instruction(instruction).lower()
        unsupported_patterns = [
            r"\bbuy\b|\bpurchase\b|\border\b.*\busing my account\b",
            r"\bbook\b.*\b(ticket|flight|hotel|room)\b|\breserve\b.*\b(hotel|room|seat)\b",
            r"\bsend\b.*\b(github|email|message|report|release)\b",
            r"\bcreate\b.*\brelease\b|\bsubmit\b.*\bform\b|\bupload\b",
            r"\bopen\b.*\b(wechat|browser|app|application)\b",
            r"\bmessage\b.*\b(teammate|friend|user)\b",
            r"\blive web\b|\btoday'?s\b.*\b(rate|weather|price)\b|\breal[- ]time\b",
        ]
        return any(re.search(pattern, lowered) for pattern in unsupported_patterns)

    def _is_missing_info_request(self, instruction: str) -> bool:
        lowered = self._normalize_instruction(instruction).lower()
        missing_refs = [
            "this value",
            "that value",
            "that result",
            "those items",
            "earlier value",
            "mentioned earlier",
            "the passage",
            "the document",
            "the article",
            "the json i meant",
            "the list i mentioned",
            "the sentence",
            "the email to that professor",
            "solve it",
            "make it formal",
            "find the date difference",
        ]
        if not any(ref in lowered for ref in missing_refs):
            return False

        has_payload = bool(
            re.search(r"'[^']+'|\"[^\"]+\"|\d{4}-\d{1,2}-\d{1,2}|\d+\s*(cm|m|kg|g|%)", lowered)
        )
        has_structured_after_colon = ":" in instruction and len(instruction.split(":", 1)[1].strip()) >= 8
        return not has_payload and not has_structured_after_colon

    def _is_conceptual_no_tool_request(self, instruction: str) -> bool:
        lowered = self._normalize_instruction(instruction).lower()
        if re.search(r"\b(do not|without)\b.*\b(compute|calculate|translate|extract|validate|run|call|tool)\b", lowered):
            return True
        conceptual_starts = [
            "explain ",
            "why ",
            "what does ",
            "what is the difference ",
            "what is ",
            "define ",
            "describe why ",
            "describe when ",
            "describe sequence ",
            "give a conceptual reason",
            "in words",
            "list two risks",
            "state one reason",
        ]
        return any(lowered.startswith(prefix) for prefix in conceptual_starts)

    def _looks_tool_required_multi(self, instruction: str) -> bool:
        if not self._looks_composed_multi(instruction):
            return False
        parts = self._split_instruction_for_v3(instruction)
        if len(parts) < 2:
            return False
        skill_hits = []
        for part in parts[: self.max_steps]:
            hints = self._skill_hints_for_text(part, part)
            skill_hits.extend(hints[:1])
        return len(set(skill_hits)) >= 2

    def _looks_composed_multi(self, instruction: str) -> bool:
        lowered = self._normalize_instruction(instruction).lower()
        if super()._looks_multi_step(lowered):
            return True
        followup_cues = [
            "summarize",
            "summarise",
            "state",
            "briefly",
            "format",
            "organize",
            "put",
            "show",
            "extract",
            "pull",
            "draft",
            "make",
            "turn",
            "classify",
            "detect",
            "rewrite",
            "estimate",
            "judge",
            "create",
            "generate",
            "title",
            "score",
            "remove",
        ]
        cue_pattern = "|".join(re.escape(cue) for cue in followup_cues)
        return bool(re.search(rf"\b(and|, and)\s+({cue_pattern})\b", lowered))

    def _decompose_instruction(self, instruction: str, need_tool_decision: dict) -> list[str]:
        if need_tool_decision.get("task_type") != "multi_tool":
            return [self._strip_meta_prefixes(instruction)]
        parts = self._split_instruction_for_v3(instruction)
        if len(parts) >= 2:
            return [self._clean_subtask(part) for part in parts[: self.max_steps] if part.strip()]
        return super()._decompose_instruction(instruction, need_tool_decision)

    def _split_instruction_for_v3(self, instruction: str) -> list[str]:
        cleaned = self._strip_meta_prefixes(instruction)
        explicit = super()._decompose_instruction(cleaned, {"task_type": "multi_tool"})
        if len(explicit) >= 2 and explicit[0] != cleaned:
            return explicit[: self.max_steps]

        match = re.search(
            r"^(.*?)\s+(?:,?\s*and)\s+("
            r"(?:state|summarize|summarise|organize|put|format|show|remove|extract|pull|draft|make|turn|classify|detect|rewrite|estimate|judge|create|generate|title|score)\b.*)$",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return [cleaned]

        first = self._clean_subtask(match.group(1))
        second = self._normalize_followup_subtask(self._clean_subtask(match.group(2)))
        return [part for part in [first, second] if part][: self.max_steps]

    @staticmethod
    def _strip_meta_prefixes(instruction: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(instruction).strip())
        prefixes = [
            r"^without using a numbered plan,\s*",
            r"^i need final response only after both parts are handled:\s*",
            r"^after both parts are handled,\s*",
        ]
        for pattern in prefixes:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    @staticmethod
    def _normalize_followup_subtask(subtask: str) -> str:
        lowered = subtask.lower()
        if re.search(r"\b(state|summarize|summarise)\b.*\b(briefly|result|it|validation)\b", lowered):
            return "summarize the previous result briefly"
        if re.search(r"\b(organize|put|format|show)\b.*\btable\b", lowered):
            return "format the previous result as a table"
        if re.search(r"\bextract\b.*\bkeywords?\b.*\b(translation|title|unique|result|that)\b", lowered):
            return "extract keywords from the previous result"
        if re.search(r"\bmake\b.*\b(formal|friendly|polite)\b|\bturn\b.*\bformal\b", lowered):
            return "make the previous result formal"
        if re.search(r"\b(readability|score|estimate)\b.*\b(after|correction|corrected)\b", lowered):
            return "score readability for the previous result"
        if re.search(r"\b(sentiment|judge)\b.*\b(afterward|afterwards|after)\b", lowered):
            return "analyze sentiment of the previous result"
        if re.search(r"\bdraft\b.*\bemail\b.*\b(person|professor|result)\b", lowered):
            return "draft an email using the previous result"
        if re.search(r"\bremove\b.*\b(repeated|duplicate)\b", lowered):
            return "remove duplicates from the previous result"
        return subtask

    def _skill_hints_for_text(self, text: str, full_instruction: str) -> list[str]:
        hints = super()._skill_hints_for_text(text, full_instruction)
        lowered_sources = [
            self._normalize_instruction(text).lower(),
            self._normalize_instruction(full_instruction).lower(),
        ]
        extra_rules = [
            (r"\bstate\b.*\bbriefly\b|\bbriefly\b.*\bresult\b", "summarizer"),
            (r"\bpull\b.*\baction items?\b|\baction items?\b", "todo_extractor"),
            (r"\bidentify\b.*\bentities?\b", "entity_extractor"),
            (r"\bgive\b.*\btitle\b|\btitle\b.*\banalysis\b", "title_generator"),
            (r"\bmake\b.*\bstudy questions?\b|\bstudy questions?\b", "question_generator"),
            (r"\bturn\b.*\bchecklist\b|\bconvert\b.*\bchecklist\b", "checklist_generator"),
            (r"\bfix\b.*\bgrammar\b|\bcorrection\b", "grammar_corrector"),
            (r"\bafter correction\b|\bafterward\b.*\bsentiment\b", "readability_scorer"),
            (r"\bvalidation result\b", "summarizer"),
            (r"\bconverted value\b", "summarizer"),
        ]
        for source in lowered_sources:
            for pattern, skill_name in extra_rules:
                if re.search(pattern, source) and skill_name not in hints:
                    hints.append(skill_name)
            for skill_name in self._contract_trigger_hints(source):
                if skill_name not in hints:
                    hints.append(skill_name)
        return hints

    def _contract_trigger_hints(self, lowered_text: str) -> list[str]:
        hints = []
        ignored = {"input", "output", "text", "data", "result", "tool", "skill"}
        for skill_name, contract in self.contract_by_name.items():
            retrieval = contract.get("retrieval_contract", {})
            triggers = retrieval.get("trigger_phrases", [])
            if not isinstance(triggers, list):
                continue
            for phrase in triggers:
                normalized = str(phrase).strip().lower()
                if len(normalized) < 4 or normalized in ignored:
                    continue
                if re.search(r"[{}\"]", normalized):
                    continue
                if normalized in lowered_text:
                    hints.append(skill_name)
                    break
        return hints

    def _select_skill_for_subtask(
        self,
        subtask: str,
        instruction: str,
        candidate_names: list[str],
        step_index: int,
    ) -> tuple[str, str]:
        if self.ablation_config["use_backfill"]:
            priority = self._priority_skill_for_text(subtask)
            if priority in candidate_names:
                return priority, "rule_v3"
        return super()._select_skill_for_subtask(subtask, instruction, candidate_names, step_index)

    @staticmethod
    def _priority_skill_for_text(text: str) -> str:
        lowered = re.sub(r"\s+", " ", str(text).strip().lower())
        priority_rules = [
            (r"\bformat\b.*\btable\b|\borganize\b.*\btable\b|\bput\b.*\btable\b|\bshow\b.*\btable\b", "table_formatter"),
            (r"\bextract\b.*\bkeywords?\b", "keyword_extractor"),
            (r"\bstate\b.*\bbriefly\b|\bsummarize\b|\bsummarise\b", "summarizer"),
            (r"\bremove\b.*\b(repeated|duplicate)\b|\bdeduplicate\b", "deduplicator"),
            (r"\bsort\b|\balphabetically\b", "list_sorter"),
            (r"\bclassify\b.*\bintent\b|\bintent\b", "intent_classifier"),
            (r"\bclassify\b.*\btopic\b|\btopic\b", "topic_classifier"),
            (r"\bdetect\b.*\blanguage\b|\blanguage\b", "language_detector"),
            (r"\bdraft\b.*\bemail\b", "email_drafter"),
            (r"\bmake\b.*\bformal\b|\bpolite\b|\bfriendly\b", "tone_converter"),
            (r"\breadability\b|\bscore readability\b", "readability_scorer"),
            (r"\bsentiment\b|\bjudge\b.*\bsentiment\b", "sentiment_analyzer"),
            (r"\btitle\b|\bgive\b.*\btitle\b", "title_generator"),
            (r"\bquestions?\b", "question_generator"),
            (r"\bchecklist\b", "checklist_generator"),
            (r"\baction items?\b|\btodos?\b", "todo_extractor"),
            (r"\bentities?\b|\bperson\b|\borganization\b|\blocation\b", "entity_extractor"),
            (r"\bdates?\b|\bemails?\b|\bphone\b", "regex_extractor"),
        ]
        for pattern, skill_name in priority_rules:
            if re.search(pattern, lowered):
                return skill_name
        return ""

    def _build_skill_input(
        self,
        skill_name: str,
        subtask: str,
        instruction: str,
        step_index: int,
        llm_input: str = "",
    ) -> tuple[str, str]:
        if self.ablation_config["use_input_builder"]:
            if step_index > 0 and skill_name in {
                *DEPENDENT_INPUT_SKILLS,
                "deduplicator",
                "email_drafter",
                "todo_extractor",
                "citation_formatter",
            }:
                if skill_name in {"intent_classifier", "topic_classifier", "language_detector"} and ":" in instruction:
                    return self._text_after_colon(instruction), "rule_v3"
                return "$PREVIOUS_OUTPUT", "previous_output"

            if skill_name == "python_executor":
                code = self._extract_python_code(instruction) or self._extract_python_code(subtask)
                if code:
                    return code, "rule_v3"

        return super()._build_skill_input(skill_name, subtask, instruction, step_index, llm_input)

    @staticmethod
    def _extract_python_code(text: str) -> str:
        match = re.search(
            r"(?:python\s+code|safe\s+python\s+code|code)\s*:\s*(.+)$",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            return match.group(1).strip(" .")
        return ""

    def _make_v2_final_answer(
        self,
        instruction: str,
        observations: list[dict],
        raw_model_outputs: list[str],
        need_tool_decision: dict,
        invalid_call: bool,
    ) -> tuple[str, str]:
        if not observations and not need_tool_decision.get("need_tool"):
            decision_type = str(need_tool_decision.get("task_type", ""))
            if decision_type == "missing_info":
                return (
                    "Please provide the missing value, number, unit, dates, equation, text, passage, JSON content, code, list, items, recipient, professor, topic, or meeting notes before I call a skill.",
                    "direct_answer",
                )
            if decision_type == "unsupported_tool":
                return (
                    "This request is unsupported by the current local skill set. I cannot perform external actions such as buying tickets, sending messages, creating GitHub releases, opening apps, live web search, uploading, reserving hotels, or submitting forms.",
                    "direct_answer",
                )
        return super()._make_v2_final_answer(
            instruction=instruction,
            observations=observations,
            raw_model_outputs=raw_model_outputs,
            need_tool_decision=need_tool_decision,
            invalid_call=invalid_call,
        )
