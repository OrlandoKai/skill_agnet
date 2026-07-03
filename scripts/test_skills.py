import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from skills.skill_registry import call_skill, list_skills


TEST_INPUTS = {
    "calculator": "12 * (3 + 4)",
    "unit_converter": "10 cm to m",
    "summarizer": "Skill retrieval finds useful tools. Skill calling executes them. The agent observes results.",
    "translator_zh_en": "你好，人工智能智能体系统",
    "translator_en_zh": "hello skill retrieval agent",
    "keyword_extractor": "Skill retrieval and skill calling are important for agent systems.",
    "text_rewriter": "skill calling helps agents use tools",
    "sentiment_analyzer": "This is a good and useful baseline.",
    "paper_qa": "What is the core contribution of this paper?",
    "python_executor": "x = 2 + 3\nx * 10",
}


def main() -> None:
    failures = []
    for skill_name in list_skills():
        output = call_skill(skill_name, TEST_INPUTS[skill_name])
        ok = isinstance(output, str) and bool(output.strip())
        status = "[OK]" if ok else "[FAIL]"
        print(f"{status} {skill_name}: {output}")
        if not ok:
            failures.append(skill_name)

    if failures:
        raise SystemExit(f"Failed skills: {', '.join(failures)}")


if __name__ == "__main__":
    main()
