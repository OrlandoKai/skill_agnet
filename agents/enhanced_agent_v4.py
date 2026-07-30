import re

from agents.enhanced_agent_v3 import EnhancedSkillAgentV3


class EnhancedSkillAgentV4(EnhancedSkillAgentV3):
    """V4 agent with narrower abstention and stronger similar-skill priorities."""

    def _is_conceptual_no_tool_request(self, instruction: str) -> bool:
        cleaned = self._strip_meta_prefixes(instruction)
        lowered = self._normalize_instruction(cleaned).lower()

        explicit_no_tool = [
            r"\bdo not\b.*\b(compute|calculate|translate|extract|validate|run|call|use a tool|invoke)\b",
            r"\bwithout\b.*\b(running|calling|using)\b.*\b(tool|skill|function)\b",
            r"\bnot asking you to\b.*\b(compute|calculate|translate|extract|validate|run|call)\b",
        ]
        if any(re.search(pattern, lowered) for pattern in explicit_no_tool):
            return True

        conceptual_starts = [
            "explain ",
            "why ",
            "what does ",
            "what is the difference ",
            "define ",
            "describe why ",
            "describe when ",
            "describe sequence ",
            "give a conceptual reason",
            "in words",
            "list two risks",
            "state one reason",
        ]
        if any(lowered.startswith(prefix) for prefix in conceptual_starts):
            tool_action_cues = [
                "extract ",
                "translate ",
                "convert ",
                "calculate ",
                "compute ",
                "summarize ",
                "format ",
                "draft ",
                "generate ",
                "create ",
                "classify ",
                "detect ",
                "validate ",
                "sort ",
                "deduplicate ",
            ]
            return not any(cue in lowered for cue in tool_action_cues)
        return False

    def _is_missing_info_request(self, instruction: str) -> bool:
        cleaned = self._strip_meta_prefixes(instruction)
        lowered = self._normalize_instruction(cleaned).lower()

        if re.search(r"\band\s+make\s+it\s+(formal|friendly|polite)\b", lowered):
            first_clause = re.split(r"\band\s+make\s+it\s+", lowered, maxsplit=1)[0]
            if len(first_clause.split()) >= 5:
                return False

        if re.search(r"\band\s+(extract|summarize|format|put|organize|draft|generate|create|classify|detect|score|judge)\b", lowered):
            first_clause = re.split(r"\band\s+", lowered, maxsplit=1)[0]
            if self._skill_hints_for_text(first_clause, first_clause):
                return False

        return super()._is_missing_info_request(cleaned)

    def _looks_composed_multi(self, instruction: str) -> bool:
        if super()._looks_composed_multi(instruction):
            return True
        lowered = self._normalize_instruction(self._strip_meta_prefixes(instruction)).lower()
        extra_followups = [
            "outline",
            "answer",
            "fix",
            "correct",
            "validate",
            "summarize",
            "summarise",
        ]
        cue_pattern = "|".join(re.escape(cue) for cue in extra_followups)
        return bool(re.search(rf"\b(and|, and)\s+({cue_pattern})\b", lowered))

    def _split_instruction_for_v3(self, instruction: str) -> list[str]:
        parts = super()._split_instruction_for_v3(instruction)
        if len(parts) >= 2:
            return parts

        cleaned = self._strip_meta_prefixes(instruction)
        match = re.search(
            r"^(.*?)\s+(?:,?\s*and)\s+("
            r"(?:outline|answer|fix|correct|validate|summarize|summarise)\b.*)$",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return parts
        first = self._clean_subtask(match.group(1))
        second = self._normalize_followup_subtask(self._clean_subtask(match.group(2)))
        return [part for part in [first, second] if part][: self.max_steps]

    def _skill_hints_for_text(self, text: str, full_instruction: str) -> list[str]:
        hints = super()._skill_hints_for_text(text, full_instruction)
        lowered_sources = [
            self._normalize_instruction(text).lower(),
            self._normalize_instruction(full_instruction).lower(),
        ]
        priority_rules = [
            (r"\bcsv\b.*\bsummar|\bsummarize csv\b|\bsummarise csv\b", "csv_summarizer"),
            (r"\bfind\s+x\b|\bsolve\b.*\bx\b|[0-9]\s*\*\s*x|[0-9]x\b", "equation_solver"),
            (r"\bkeep\s+[-+]?\d+(?:\.\d+)?\s+to\s+[-+]?\d+(?:\.\d+)?\b", "range_filter"),
            (r"\bformat citation\b|\bcitation\b", "citation_formatter"),
            (r"\bpaper question\b|\banswer this paper\b", "paper_qa"),
            (r"\boutline\b", "outline_generator"),
            (r"\btitle\b|\bgive\b.*\btitle\b", "title_generator"),
            (r"\bquestions?\b|\bstudy questions?\b", "question_generator"),
            (r"\bchecklist\b", "checklist_generator"),
        ]
        for source in lowered_sources:
            for pattern, skill_name in priority_rules:
                if re.search(pattern, source) and skill_name not in hints:
                    hints.insert(0, skill_name)
        return self._dedupe(hints)

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        seen = set()
        result = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    @staticmethod
    def _priority_skill_for_text(text: str) -> str:
        lowered = re.sub(r"\s+", " ", str(text).strip().lower())
        priority_rules = [
            (r"\bcsv\b.*\bsummar|\bsummarize csv\b|\bsummarise csv\b", "csv_summarizer"),
            (r"\bfind\s+x\b|\bsolve\b.*\bx\b|[0-9]\s*\*\s*x|[0-9]x\b", "equation_solver"),
            (r"\bkeep\s+[-+]?\d+(?:\.\d+)?\s+to\s+[-+]?\d+(?:\.\d+)?\b", "range_filter"),
            (r"\bformat citation\b|\bcitation\b", "citation_formatter"),
            (r"\bpaper question\b|\banswer this paper\b", "paper_qa"),
            (r"\bformat\b.*\btable\b|\borganize\b.*\btable\b|\bput\b.*\btable\b|\bshow\b.*\btable\b", "table_formatter"),
            (r"\bextract\b.*\bkeywords?\b", "keyword_extractor"),
            (r"\btitle\b|\bgive\b.*\btitle\b", "title_generator"),
            (r"\bquestions?\b|\bstudy questions?\b", "question_generator"),
            (r"\bchecklist\b", "checklist_generator"),
            (r"\boutline\b", "outline_generator"),
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
            (r"\baction items?\b|\btodos?\b", "todo_extractor"),
            (r"\bentities?\b|\bperson\b|\borganization\b|\blocation\b", "entity_extractor"),
            (r"\bdates?\b|\bemails?\b|\bphone\b", "regex_extractor"),
        ]
        for pattern, skill_name in priority_rules:
            if re.search(pattern, lowered):
                return skill_name
        return ""
