from .basic_tools import (
    argument_mapper,
    calculator,
    checklist_generator,
    citation_formatter,
    csv_summarizer,
    date_difference_calculator,
    deduplicator,
    email_drafter,
    entity_extractor,
    equation_solver,
    grammar_corrector,
    intent_classifier,
    json_validator,
    keyword_extractor,
    language_detector,
    list_sorter,
    meeting_notes_extractor,
    outline_generator,
    paper_qa,
    percentage_calculator,
    python_executor,
    pros_cons_analyzer,
    question_generator,
    range_filter,
    ratio_calculator,
    readability_scorer,
    regex_extractor,
    sentiment_analyzer,
    summarizer,
    statistics_calculator,
    table_formatter,
    text_rewriter,
    title_generator,
    topic_classifier,
    tone_converter,
    todo_extractor,
    translator_en_zh,
    translator_zh_en,
    unit_converter,
    number_sequence_analyzer,
)


SKILL_REGISTRY = {
    "calculator": calculator,
    "ratio_calculator": ratio_calculator,
    "equation_solver": equation_solver,
    "number_sequence_analyzer": number_sequence_analyzer,
    "percentage_calculator": percentage_calculator,
    "statistics_calculator": statistics_calculator,
    "date_difference_calculator": date_difference_calculator,
    "range_filter": range_filter,
    "list_sorter": list_sorter,
    "deduplicator": deduplicator,
    "json_validator": json_validator,
    "csv_summarizer": csv_summarizer,
    "unit_converter": unit_converter,
    "summarizer": summarizer,
    "language_detector": language_detector,
    "readability_scorer": readability_scorer,
    "title_generator": title_generator,
    "question_generator": question_generator,
    "checklist_generator": checklist_generator,
    "pros_cons_analyzer": pros_cons_analyzer,
    "argument_mapper": argument_mapper,
    "email_drafter": email_drafter,
    "todo_extractor": todo_extractor,
    "meeting_notes_extractor": meeting_notes_extractor,
    "translator_zh_en": translator_zh_en,
    "translator_en_zh": translator_en_zh,
    "keyword_extractor": keyword_extractor,
    "regex_extractor": regex_extractor,
    "entity_extractor": entity_extractor,
    "topic_classifier": topic_classifier,
    "intent_classifier": intent_classifier,
    "text_rewriter": text_rewriter,
    "grammar_corrector": grammar_corrector,
    "tone_converter": tone_converter,
    "outline_generator": outline_generator,
    "sentiment_analyzer": sentiment_analyzer,
    "paper_qa": paper_qa,
    "citation_formatter": citation_formatter,
    "table_formatter": table_formatter,
    "python_executor": python_executor,
}


def get_skill(name: str):
    return SKILL_REGISTRY.get(name)


def list_skills() -> list[str]:
    return list(SKILL_REGISTRY.keys())


def call_skill(name: str, input_text: str) -> str:
    skill = get_skill(name)
    if skill is None:
        return f"Error: unknown skill: {name}"
    try:
        result = skill(input_text)
        return str(result)
    except Exception as exc:
        return f"Error: skill {name} failed: {exc}"
