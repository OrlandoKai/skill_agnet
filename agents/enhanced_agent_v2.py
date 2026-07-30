import json
import re
from typing import Any

from agents.enhanced_agent import EnhancedSkillAgent
from skills.skill_registry import call_skill, get_skill


ABLATION_CHOICES = {
    "none",
    "no_need_tool_gate",
    "no_step_retrieval",
    "no_backfill",
    "no_input_builder",
    "no_rule_final_answer",
}


SKILL_ALIASES = {
    "summary_creator": "summarizer",
    "summary_generator": "summarizer",
    "summarization": "summarizer",
    "translator": "translator_zh_en",
    "zh_to_en_translator": "translator_zh_en",
    "chinese_to_english_translator": "translator_zh_en",
    "en_to_zh_translator": "translator_en_zh",
    "english_to_chinese_translator": "translator_en_zh",
    "keyword_generator": "keyword_extractor",
    "keyword_extraction": "keyword_extractor",
    "title_creator": "title_generator",
    "email_extractor": "regex_extractor",
    "date_extractor": "regex_extractor",
    "table_generator": "table_formatter",
    "markdown_table_formatter": "table_formatter",
}


DEPENDENT_INPUT_SKILLS = {
    "keyword_extractor",
    "summarizer",
    "text_rewriter",
    "sentiment_analyzer",
    "tone_converter",
    "table_formatter",
    "title_generator",
    "question_generator",
    "checklist_generator",
    "topic_classifier",
    "intent_classifier",
    "readability_scorer",
    "language_detector",
    "statistics_calculator",
    "list_sorter",
}


class EnhancedSkillAgentV2(EnhancedSkillAgent):
    """Enhanced agent with step-aware retrieval and deterministic repairs."""

    def __init__(
        self,
        model,
        retriever,
        max_steps: int = 2,
        top_k: int = 5,
        ablation: str = "none",
    ) -> None:
        super().__init__(model=model, retriever=retriever, max_steps=max_steps, top_k=top_k)
        if ablation not in ABLATION_CHOICES:
            raise ValueError(f"Unknown Enhanced V2 ablation: {ablation}")
        self.ablation = ablation
        self.ablation_config = {
            "use_need_tool_gate": ablation != "no_need_tool_gate",
            "use_step_retrieval": ablation != "no_step_retrieval",
            "use_backfill": ablation != "no_backfill",
            "use_input_builder": ablation != "no_input_builder",
            "use_rule_final_answer": ablation != "no_rule_final_answer",
        }
        self.skill_by_name = {
            skill.get("name", ""): skill
            for skill in getattr(self.retriever, "skills", [])
            if skill.get("name")
        }

    def run_task(self, task: dict) -> dict:
        instruction = task["instruction"]
        raw_model_outputs: list[str] = []
        called_skills: list[str] = []
        observations: list[dict] = []
        invalid_call = False

        need_tool_decision = self._v2_need_tool_decision(instruction, raw_model_outputs)
        subtasks: list[str] = []
        retrieved: list[dict] = []
        retrieved_by_step: list[dict] = []
        planned_steps: list[dict] = []
        plan_valid = True
        plan_repaired = False

        if need_tool_decision["need_tool"]:
            subtasks = self._decompose_instruction(instruction, need_tool_decision)
            retrieved, retrieved_by_step = self._retrieve_step_candidates(instruction, subtasks)
            planned_steps, plan_valid, plan_repaired = self._build_v2_plan(
                instruction=instruction,
                subtasks=subtasks,
                retrieved_by_step=retrieved_by_step,
                need_tool_decision=need_tool_decision,
                raw_model_outputs=raw_model_outputs,
            )
            invalid_call = not plan_valid
            if plan_valid:
                self._execute_v2_plan(planned_steps, called_skills, observations)

        final_answer, final_answer_source = self._make_v2_final_answer(
            instruction=instruction,
            observations=observations,
            raw_model_outputs=raw_model_outputs,
            need_tool_decision=need_tool_decision,
            invalid_call=invalid_call,
        )

        return {
            "task_id": task.get("task_id", ""),
            "instruction": instruction,
            "gold_skills": task.get("gold_skills", []),
            "expected_answer": task.get("expected_answer", ""),
            "task_type": task.get("task_type", ""),
            "retrieved_skills": [self._compact_skill(skill) for skill in retrieved],
            "subtasks": subtasks,
            "retrieved_by_step": retrieved_by_step,
            "need_tool_decision": need_tool_decision,
            "planned_skills": [step["skill"] for step in planned_steps],
            "planned_steps": planned_steps,
            "plan_valid": plan_valid,
            "plan_repaired": plan_repaired,
            "called_skills": called_skills,
            "observations": observations,
            "final_answer": final_answer,
            "final_answer_source": final_answer_source,
            "invalid_call": invalid_call,
            "raw_model_outputs": raw_model_outputs,
            "ablation": self.ablation,
            "ablation_config": dict(self.ablation_config),
        }

    def _v2_need_tool_decision(self, instruction: str, raw_model_outputs: list[str]) -> dict:
        if self.ablation_config["use_need_tool_gate"]:
            return self._decide_need_tool(instruction, raw_model_outputs)
        return {
            "need_tool": True,
            "task_type": "multi_tool" if self._looks_multi_step(instruction) else "single_tool",
            "reason": "Ablation disabled the NEED_TOOL / NO_TOOL gate.",
        }

    def _decompose_instruction(self, instruction: str, need_tool_decision: dict) -> list[str]:
        cleaned = re.sub(r"\s+", " ", instruction.strip())
        task_type = need_tool_decision.get("task_type")
        if task_type != "multi_tool":
            return [cleaned]

        patterns = [
            r"^\s*first\s+(.*?),?\s+then\s+(.*)$",
            r"^\s*(.*?)\s+then\s+(.*)$",
            r"^\s*(.*?)\s+after that\s+(.*)$",
            r"^\s*先(.+?)再(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, cleaned, flags=re.IGNORECASE)
            if match:
                parts = [self._clean_subtask(part) for part in match.groups()]
                return [part for part in parts if part][: self.max_steps]
        return [cleaned]

    @staticmethod
    def _clean_subtask(text: str) -> str:
        cleaned = str(text).strip(" ,.;")
        cleaned = re.sub(r"^(first|then|after that)\s+", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def _retrieve_step_candidates(
        self,
        instruction: str,
        subtasks: list[str],
    ) -> tuple[list[dict], list[dict]]:
        overall = self._add_backfill_skills(
            self.retriever.retrieve(instruction, top_k=self.top_k),
            instruction,
        )
        if not self.ablation_config["use_step_retrieval"]:
            retrieved_by_step = [
                {
                    "step": index,
                    "subtask": subtask,
                    "retrieved_skills": [self._compact_skill(skill) for skill in overall],
                }
                for index, subtask in enumerate(subtasks, start=1)
            ]
            return list(overall), retrieved_by_step

        union = list(overall)
        retrieved_by_step = []

        for index, subtask in enumerate(subtasks, start=1):
            step_skills = self.retriever.retrieve(subtask, top_k=self.top_k)
            step_skills = self._add_backfill_skills(step_skills, subtask, instruction)
            retrieved_by_step.append(
                {
                    "step": index,
                    "subtask": subtask,
                    "retrieved_skills": [self._compact_skill(skill) for skill in step_skills],
                }
            )
            union = self._merge_skills(union, step_skills)

        return union, retrieved_by_step

    def _add_backfill_skills(
        self,
        skills: list[dict],
        text: str,
        full_instruction: str | None = None,
    ) -> list[dict]:
        if not self.ablation_config["use_backfill"]:
            return skills
        hints = self._skill_hints_for_text(text, full_instruction or text)
        backfilled = [
            {**self.skill_by_name[name], "score": 0.0}
            for name in hints
            if name in self.skill_by_name
        ]
        return self._merge_skills(backfilled, skills)

    @staticmethod
    def _merge_skills(primary: list[dict], secondary: list[dict]) -> list[dict]:
        seen = set()
        merged = []
        for skill in [*primary, *secondary]:
            name = skill.get("name", "")
            if name and name not in seen:
                seen.add(name)
                merged.append(skill)
        return merged

    def _skill_hints_for_text(self, text: str, full_instruction: str) -> list[str]:
        primary = str(text).lower()
        secondary = str(full_instruction).lower()
        hints = []
        rules = [
            (r"\bintent\b.*\bclassif|\bclassif\w*\b.*\bintent\b", "intent_classifier"),
            (r"\btopic\b.*\bclassif|\bclassif\w*\b.*\btopic\b", "topic_classifier"),
            (r"\bformat\b.*\btable\b|\bmarkdown table\b|\bas a table\b", "table_formatter"),
            (r"\btone\b|\bformal\b|\bfriendly\b", "tone_converter"),
            (r"\bfind\b.*\bdays?\b.*\bbetween\b|\bdays?\s+between\b|\bdate difference\b", "date_difference_calculator"),
            (r"\bcsv\b.*\bsummar|\bsummarize\b.*\bcsv\b|\bsummarise\b.*\bcsv\b", "csv_summarizer"),
            (r"\bdetect\b.*\blanguage\b|\blanguage\b.*\bdetect", "language_detector"),
            (r"\breadability\b|\bscore readability\b", "readability_scorer"),
            (r"\bdraft\b.*\bemail\b|\bwrite\b.*\bemail\b|\bemail\b.*\bdraft\b", "email_drafter"),
            (r"\bjson\b.*\bvalid|\bvalidate\b.*\bjson\b|\bvalidate\s+\{|\bvalidate\s+\[", "json_validator"),
            (r"\bpredict\b.*\bnext\b|\bnext value\b|\bsequence\b", "number_sequence_analyzer"),
            (r"\bfilter\b.*\bbetween\b|\bselect\b.*\babove\b|\bselect\b.*\bbelow\b|\bkeep values\b|\brange\b", "range_filter"),
            (r"\bsort\b|\border\b.*\bascending\b|\balphabetically\b", "list_sorter"),
            (r"\bremove duplicates\b|\bdeduplicate\b|\bunique\b|\brepeated\b", "deduplicator"),
            (r"\bgenerate\b.*\bquestions?\b|\bcreate\b.*\bquestions?\b", "question_generator"),
            (r"\bchecklist\b", "checklist_generator"),
            (r"translate\b.*\binto english\b|chinese.*to english|zh[-_ ]?en", "translator_zh_en"),
            (r"translate\b.*\binto chinese\b|english.*to chinese|en[-_ ]?zh", "translator_en_zh"),
            (r"\bextract\b.*\bkeywords?\b|\bkeywords?\b.*\bfrom\b", "keyword_extractor"),
            (r"\bgenerate\b.*\btitle\b|\bcreate\b.*\btitle\b|\btitle\b.*\bfor\b", "title_generator"),
            (r"\bsummarize\b|\bsummarise\b|\bsummary\b|\bone short sentence\b|\bone sentence\b", "summarizer"),
            (r"\bpaper question\b|\bcontribution of the paper\b", "paper_qa"),
            (r"\bpython code\b|\bexecute\b.*\bcode\b", "python_executor"),
            (r"\bpercentage\b|\bpercent\b|%|\bdiscount\b|\bincrease\b|\bdecrease\b", "percentage_calculator"),
            (r"\bmean\b|\bmedian\b|\baverage\b|\bstatistics\b", "statistics_calculator"),
            (r"\bratio\b", "ratio_calculator"),
            (r"\bequation\b|\bsolve\b.*\bx\b", "equation_solver"),
            (r"\bconvert\b.*(?:cm|km|kg|g|celsius|fahrenheit|meter|mile|inch|pound)\b|\bcm\b|\bkm\b|\bkg\b|\bcelsius\b|\bfahrenheit\b", "unit_converter"),
            (r"\bregex\b|\bextract\b.*\bemails?\b|\bemail address\b|\bextract\b.*\bdates?\b|\bphone\b", "regex_extractor"),
            (r"\bentities\b|\bperson\b|\borganization\b|\blocation\b", "entity_extractor"),
            (r"\bformat\b.*\btable\b|\bmarkdown table\b", "table_formatter"),
            (r"\brewrite\b|\brephrase\b|\bpolished sentence\b", "text_rewriter"),
            (r"\bgrammar\b|\bcorrect\b.*\bsentence\b", "grammar_corrector"),
            (r"\btone\b|\bformal\b|\bfriendly\b", "tone_converter"),
            (r"\bsentiment\b|\bpositive\b|\bnegative\b", "sentiment_analyzer"),
            (r"\btopic\b.*\bclassif|\bclassif\w*\b.*\btopic\b", "topic_classifier"),
            (r"\bintent\b.*\bclassif|\bclassif\w*\b.*\bintent\b", "intent_classifier"),
            (r"\boutline\b", "outline_generator"),
            (r"\bcitation\b|\bcite\b", "citation_formatter"),
            (r"\btodo\b|\baction item\b", "todo_extractor"),
            (r"\bmeeting notes\b|\bdecision:\b|\baction:\b", "meeting_notes_extractor"),
            (r"\bpros\b.*\bcons\b", "pros_cons_analyzer"),
            (r"\bargument\b|\bclaim:\b", "argument_mapper"),
        ]

        def add_matches(source: str) -> None:
            for pattern, skill_name in rules:
                if re.search(pattern, source) and skill_name not in hints:
                    hints.append(skill_name)
            arithmetic_expression = re.search(r"\d+\s*[*+/]\s*\d+|\d+\s+-\s+\d+", source)
            if re.search(r"\bcalculate\b|\bcompute\b", source) or arithmetic_expression:
                if not any(
                    skill in hints
                    for skill in [
                        "percentage_calculator",
                        "statistics_calculator",
                        "ratio_calculator",
                        "equation_solver",
                        "unit_converter",
                    ]
                ):
                    hints.append("calculator")

        add_matches(primary)
        if secondary != primary:
            add_matches(secondary)
        return hints

    def _build_v2_plan(
        self,
        instruction: str,
        subtasks: list[str],
        retrieved_by_step: list[dict],
        need_tool_decision: dict,
        raw_model_outputs: list[str],
    ) -> tuple[list[dict], bool, bool]:
        target_steps = 1 if need_tool_decision.get("task_type") == "single_tool" else min(
            self.max_steps,
            len(subtasks),
        )
        planned_steps = []
        plan_repaired = False

        for index in range(target_steps):
            subtask = subtasks[index] if index < len(subtasks) else instruction
            candidates = retrieved_by_step[index]["retrieved_skills"] if index < len(retrieved_by_step) else []
            candidate_names = [skill["name"] for skill in candidates if skill.get("name")]
            selected, selection_source = self._select_skill_for_subtask(
                subtask,
                instruction,
                candidate_names,
                index,
            )

            llm_input = ""
            if not selected:
                llm_step = self._llm_plan_one_step(
                    instruction=instruction,
                    subtask=subtask,
                    candidate_names=candidate_names,
                    step_index=index,
                    raw_model_outputs=raw_model_outputs,
                )
                selected = self._repair_skill_name(llm_step.get("skill", ""), candidate_names)
                llm_input = str(llm_step.get("input", "") or "")
                selection_source = "llm"

            if not selected and candidate_names:
                selected = candidate_names[0]
                selection_source = "fallback_top1"
                plan_repaired = True

            if not selected:
                return planned_steps, False, plan_repaired

            if selection_source in {"llm", "fallback_top1"} and selected not in candidate_names:
                repaired = self._repair_skill_name(selected, candidate_names)
                if repaired:
                    selected = repaired
                    selection_source = "repaired"
                    plan_repaired = True
                else:
                    return planned_steps, False, plan_repaired

            if not self.ablation_config["use_input_builder"] and not llm_input.strip():
                llm_step = self._llm_plan_one_step(
                    instruction=instruction,
                    subtask=subtask,
                    candidate_names=candidate_names,
                    step_index=index,
                    raw_model_outputs=raw_model_outputs,
                )
                llm_skill = self._repair_skill_name(llm_step.get("skill", ""), candidate_names)
                if llm_skill == selected:
                    llm_input = str(llm_step.get("input", "") or "")

            skill_input, input_source = self._build_skill_input(
                skill_name=selected,
                subtask=subtask,
                instruction=instruction,
                step_index=index,
                llm_input=llm_input,
            )
            if selection_source in {"fallback_top1", "repaired"}:
                plan_repaired = True

            planned_steps.append(
                {
                    "step": index + 1,
                    "subtask": subtask,
                    "skill": selected,
                    "input": skill_input,
                    "input_source": input_source,
                    "selection_source": selection_source,
                }
            )

        return planned_steps, bool(planned_steps), plan_repaired

    def _select_skill_for_subtask(
        self,
        subtask: str,
        instruction: str,
        candidate_names: list[str],
        step_index: int,
    ) -> tuple[str, str]:
        if not self.ablation_config["use_backfill"]:
            return "", ""
        for skill_name in self._skill_hints_for_text(subtask, subtask):
            if skill_name in candidate_names:
                return skill_name, "rule"
        if step_index > 0 and "keyword_extractor" in candidate_names and re.search(
            r"\bkeywords?\b",
            subtask.lower(),
        ):
            return "keyword_extractor", "rule"
        return "", ""

    def _llm_plan_one_step(
        self,
        instruction: str,
        subtask: str,
        candidate_names: list[str],
        step_index: int,
        raw_model_outputs: list[str],
    ) -> dict:
        prompt = f"""[INST]
Choose one skill for one subtask.
Return JSON only. The skill must be one of the candidates.

Full task:
{instruction}

Subtask {step_index + 1}:
{subtask}

Candidate skill names:
{", ".join(candidate_names)}

Required schema:
{{"skill": "candidate skill name", "input": "complete input text"}}
[/INST]"""
        raw_output = self.model.generate(prompt, max_tokens=192, temperature=0.0)
        raw_model_outputs.append(raw_output)
        parsed = self._parse_json(raw_output)
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _repair_skill_name(skill_name: str, candidate_names: list[str]) -> str:
        normalized = re.sub(r"[^a-z0-9_]+", "_", str(skill_name).strip().lower()).strip("_")
        if normalized in candidate_names:
            return normalized
        alias = SKILL_ALIASES.get(normalized)
        if alias in candidate_names:
            return alias
        for candidate in candidate_names:
            if normalized and (normalized in candidate or candidate in normalized):
                return candidate
        return ""

    def _build_skill_input(
        self,
        skill_name: str,
        subtask: str,
        instruction: str,
        step_index: int,
        llm_input: str = "",
    ) -> tuple[str, str]:
        if not self.ablation_config["use_input_builder"]:
            if llm_input.strip():
                return llm_input.strip(), "llm"
            return subtask, "fallback_subtask"

        quoted = self._extract_first_quote(subtask) or self._extract_first_quote(instruction)

        if step_index > 0 and quoted and skill_name in {"translator_en_zh", "translator_zh_en"}:
            return quoted, "rule"
        if step_index > 0 and skill_name in DEPENDENT_INPUT_SKILLS:
            if re.search(
                r"\b(previous|result|answer|translated|title|entities|that|them|kept|unique|corrected|email|sorted)\b",
                subtask.lower(),
            ):
                return "$PREVIOUS_OUTPUT", "previous_output"
            if skill_name in {
                "keyword_extractor",
                "summarizer",
                "table_formatter",
                "tone_converter",
                "title_generator",
                "question_generator",
                "checklist_generator",
            }:
                return "$PREVIOUS_OUTPUT", "previous_output"

        lowered = subtask.lower()
        if skill_name == "calculator":
            match = re.search(
                r"(?:calculate|compute)\s+(.+?)(?:,?\s+then\b|$)",
                subtask,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group(1).strip(" ."), "rule"
            expression = re.search(r"[-+]?\d[\d\s+\-*/().]+", subtask)
            if expression:
                return expression.group(0).strip(" ."), "rule"

        if skill_name == "percentage_calculator":
            return re.sub(r"^calculate\s+", "", subtask, flags=re.IGNORECASE).strip(" ."), "rule"

        if skill_name == "statistics_calculator":
            return subtask, "rule"

        if skill_name == "date_difference_calculator":
            return subtask, "rule"

        if skill_name == "equation_solver":
            return self._normalize_equation_input(subtask), "rule"

        if skill_name == "range_filter":
            return subtask, "rule"

        if skill_name in {"list_sorter", "deduplicator"}:
            return quoted or subtask, "rule"

        if skill_name == "csv_summarizer":
            return self._extract_csv_input(instruction, subtask), "rule"

        if skill_name in {"language_detector", "readability_scorer"}:
            return quoted or self._text_after_colon(subtask) or subtask, "rule"

        if skill_name == "email_drafter":
            return subtask, "rule"

        if skill_name == "unit_converter":
            match = re.search(
                r"[-+]?\d+(?:\.\d+)?\s*[a-zA-Z°]+(?:\s+|[-_])to(?:\s+|[-_])[a-zA-Z°]+",
                subtask,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group(0).strip(), "rule"
            return subtask, "rule"

        if skill_name == "translator_zh_en":
            after_colon = self._text_after_colon(subtask)
            if after_colon:
                return after_colon, "rule"
            extracted = self._extract_between_translate_and_target(subtask, "english")
            return extracted or quoted or subtask, "rule"

        if skill_name == "translator_en_zh":
            after_colon = self._text_after_colon(subtask)
            if after_colon:
                return after_colon, "rule"
            extracted = self._extract_between_translate_and_target(subtask, "chinese")
            return extracted or quoted or subtask, "rule"

        if skill_name == "summarizer":
            text = self._text_after_colon(subtask)
            return text or subtask, "rule"

        if skill_name == "keyword_extractor":
            match = re.search(r"extract\s+keywords?\s+from\s+(.*)", subtask, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip(" ."), "rule"
            return quoted or subtask, "rule"

        if skill_name == "title_generator":
            return quoted or self._text_after_keyword(subtask, "for") or subtask, "rule"

        if skill_name == "python_executor":
            code = self._text_after_colon(instruction)
            if code:
                return code, "rule"
            code = self._text_after_keyword(subtask, "code")
            return code.strip(": ") if code else subtask, "rule"

        if skill_name in {"regex_extractor", "json_validator", "table_formatter"}:
            return self._text_after_colon(instruction) or subtask, "rule"

        if skill_name == "paper_qa":
            return self._text_after_colon(subtask) or subtask, "rule"

        if llm_input.strip():
            return llm_input.strip(), "llm"
        return subtask, "rule"

    @staticmethod
    def _extract_first_quote(text: str) -> str:
        match = re.search(r"'([^']+)'|\"([^\"]+)\"", text)
        if not match:
            return ""
        return next(group for group in match.groups() if group)

    @staticmethod
    def _extract_between_translate_and_target(text: str, target: str) -> str:
        match = re.search(
            rf"translate\s+(.*?)\s+into\s+{target}",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return ""
        return match.group(1).strip(" :,.")

    @staticmethod
    def _text_after_colon(text: str) -> str:
        return text.split(":", 1)[1].strip() if ":" in text else ""

    @staticmethod
    def _text_after_keyword(text: str, keyword: str) -> str:
        match = re.search(rf"\b{re.escape(keyword)}\b\s+(.*)", text, flags=re.IGNORECASE)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _normalize_equation_input(text: str) -> str:
        match = re.search(r"([-+*/().\dxX\s]+=[-+*/().\dxX\s]+)", text)
        equation = match.group(1).strip(" .") if match else str(text).strip(" .")
        equation = re.sub(r"(\d)\s*([xX])", r"\1*\2", equation)
        equation = re.sub(r"([xX])\s*(\d)", r"\1*\2", equation)
        return equation

    @staticmethod
    def _extract_csv_input(instruction: str, subtask: str) -> str:
        source = instruction if "\n" in instruction else subtask
        source = re.split(r",?\s+then\b", source, maxsplit=1, flags=re.IGNORECASE)[0]
        source = re.sub(
            r"^\s*summarize\s+(?:this\s+)?csv(?:\s+data|\s+rows)?[: ]*",
            "",
            source,
            flags=re.IGNORECASE,
        )
        return source.strip()

    def _execute_v2_plan(
        self,
        planned_steps: list[dict],
        called_skills: list[str],
        observations: list[dict],
    ) -> None:
        for step in planned_steps:
            skill_name = step["skill"]
            skill_input = self._resolve_step_input(step.get("input", ""), observations)
            output = call_skill(skill_name, skill_input)
            called_skills.append(skill_name)
            observations.append(
                {
                    "step": step.get("step", len(observations) + 1),
                    "skill": skill_name,
                    "input": skill_input,
                    "input_source": step.get("input_source", ""),
                    "output": output,
                }
            )
            if self._is_error_output(output):
                break

    def _make_v2_final_answer(
        self,
        instruction: str,
        observations: list[dict],
        raw_model_outputs: list[str],
        need_tool_decision: dict,
        invalid_call: bool,
    ) -> tuple[str, str]:
        if observations and any(self._is_error_output(item.get("output", "")) for item in observations):
            errors = [
                str(item.get("output", ""))
                for item in observations
                if self._is_error_output(item.get("output", ""))
            ]
            return "Tool execution failed: " + "; ".join(errors), "tool_error"

        if observations:
            if not self.ablation_config["use_rule_final_answer"]:
                answer = super()._make_final_answer(
                    instruction=instruction,
                    observations=observations,
                    raw_model_outputs=raw_model_outputs,
                    need_tool_decision=need_tool_decision,
                    invalid_call=invalid_call,
                )
                return answer, "llm_grounded"
            if len(observations) == 1:
                return str(observations[0].get("output", "")).strip(), "rule_observation"
            rendered = "; ".join(
                f"{item.get('skill')}: {item.get('output')}" for item in observations
            )
            return rendered.strip(), "rule_observation"

        if need_tool_decision.get("need_tool"):
            return (
                "I could not complete the requested tool call because no valid skill plan was produced.",
                "tool_error",
            )

        answer = super()._make_final_answer(
            instruction=instruction,
            observations=[],
            raw_model_outputs=raw_model_outputs,
            need_tool_decision=need_tool_decision,
            invalid_call=invalid_call,
        )
        return answer, "direct_answer"
