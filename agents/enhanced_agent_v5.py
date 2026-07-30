import re

from agents.enhanced_agent_v4 import EnhancedSkillAgentV4


class EnhancedSkillAgentV5(EnhancedSkillAgentV4):
    """V5 agent with focused fixes for remaining V4 hard failures."""

    def _looks_composed_multi(self, instruction: str) -> bool:
        if super()._looks_composed_multi(instruction):
            return True
        lowered = self._normalize_instruction(self._strip_meta_prefixes(instruction)).lower()
        return bool(re.search(r"\b(and|, and)\s+convert\b", lowered))

    def _split_instruction_for_v3(self, instruction: str) -> list[str]:
        parts = super()._split_instruction_for_v3(instruction)
        if len(parts) >= 2:
            return parts

        cleaned = self._strip_meta_prefixes(instruction)
        match = re.search(
            r"^(.*?)\s+(?:,?\s*and)\s+(convert\b.*)$",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return parts
        first = self._clean_subtask(match.group(1))
        second = self._normalize_followup_subtask(self._clean_subtask(match.group(2)))
        return [part for part in [first, second] if part][: self.max_steps]

    @staticmethod
    def _normalize_followup_subtask(subtask: str) -> str:
        lowered = subtask.lower()
        if re.search(r"\bconvert\b.*\bchecklist\b", lowered):
            return "convert the previous result into a checklist"
        if re.search(r"\bextract\b.*\bkeywords?\b.*\bcitation\b", lowered):
            return "extract keywords from the previous result"
        return EnhancedSkillAgentV4._normalize_followup_subtask(subtask)

    def _skill_hints_for_text(self, text: str, full_instruction: str) -> list[str]:
        hints = super()._skill_hints_for_text(text, full_instruction)
        lowered_sources = [
            self._normalize_instruction(text).lower(),
            self._normalize_instruction(full_instruction).lower(),
        ]
        priority_rules = [
            (r"\btranslate\b.*\binto chinese\b|english.*to chinese|en[-_ ]?zh", "translator_en_zh"),
            (r"\btranslate\b.*\binto english\b|chinese.*to english|zh[-_ ]?en", "translator_zh_en"),
            (r"\b(people|persons?),?\s+(organizations?|orgs?),?\s+(and\s+)?(locations?|places?)\b", "entity_extractor"),
            (r"\bextract\b.*\bkeywords?\b", "keyword_extractor"),
            (r"\bextract\b.*\b(people|persons?|organizations?|orgs?|locations?|places?)\b", "entity_extractor"),
            (r"\bconvert\b.*\bchecklist\b", "checklist_generator"),
            (r"\boutline\b", "outline_generator"),
        ]
        for source in lowered_sources:
            for pattern, skill_name in priority_rules:
                if re.search(pattern, source):
                    hints.insert(0, skill_name)
        return self._dedupe(hints)

    @staticmethod
    def _priority_skill_for_text(text: str) -> str:
        lowered = re.sub(r"\s+", " ", str(text).strip().lower())
        priority_rules = [
            (r"\btranslate\b.*\binto chinese\b|english.*to chinese|en[-_ ]?zh", "translator_en_zh"),
            (r"\btranslate\b.*\binto english\b|chinese.*to english|zh[-_ ]?en", "translator_zh_en"),
            (r"\bextract\b.*\bkeywords?\b", "keyword_extractor"),
            (r"\b(people|persons?),?\s+(organizations?|orgs?),?\s+(and\s+)?(locations?|places?)\b", "entity_extractor"),
            (r"\bextract\b.*\b(people|persons?|organizations?|orgs?|locations?|places?)\b", "entity_extractor"),
            (r"\bconvert\b.*\bchecklist\b|\binto\b.*\bchecklist\b", "checklist_generator"),
            (r"\boutline\b", "outline_generator"),
            (r"\bcsv\b.*\bsummar|\bsummarize csv\b|\bsummarise csv\b", "csv_summarizer"),
            (r"\bfind\s+x\b|\bsolve\b.*\bx\b|[0-9]\s*\*\s*x|[0-9]x\b", "equation_solver"),
            (r"\bkeep\s+[-+]?\d+(?:\.\d+)?\s+to\s+[-+]?\d+(?:\.\d+)?\b", "range_filter"),
            (r"\bformat citation\b|\bcitation\b", "citation_formatter"),
            (r"\bpaper question\b|\banswer this paper\b", "paper_qa"),
            (r"\bformat\b.*\btable\b|\borganize\b.*\btable\b|\bput\b.*\btable\b|\bshow\b.*\btable\b", "table_formatter"),
            (r"\btitle\b|\bgive\b.*\btitle\b", "title_generator"),
            (r"\bquestions?\b|\bstudy questions?\b", "question_generator"),
            (r"\bchecklist\b", "checklist_generator"),
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
