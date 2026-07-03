from .basic_tools import (
    calculator,
    keyword_extractor,
    paper_qa,
    python_executor,
    sentiment_analyzer,
    summarizer,
    text_rewriter,
    translator_en_zh,
    translator_zh_en,
    unit_converter,
)


SKILL_REGISTRY = {
    "calculator": calculator,
    "unit_converter": unit_converter,
    "summarizer": summarizer,
    "translator_zh_en": translator_zh_en,
    "translator_en_zh": translator_en_zh,
    "keyword_extractor": keyword_extractor,
    "text_rewriter": text_rewriter,
    "sentiment_analyzer": sentiment_analyzer,
    "paper_qa": paper_qa,
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
