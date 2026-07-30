import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from skills.skill_registry import call_skill, list_skills


TEST_INPUTS = {
    "calculator": "12 * (3 + 4)",
    "ratio_calculator": "simplify ratio 12:18",
    "equation_solver": "solve 2*x + 3 = 11",
    "number_sequence_analyzer": "sequence 2, 4, 6, 8",
    "percentage_calculator": "80 increased by 25%",
    "statistics_calculator": "mean and median of 2, 4, 8, 10",
    "date_difference_calculator": "days between 2026-07-01 and 2026-07-15",
    "range_filter": "filter 1, 5, 9, 12 between 3 and 10",
    "list_sorter": "sort 3, 1, 2 ascending",
    "deduplicator": "deduplicate apple, banana, apple",
    "json_validator": "{\"task\": \"retrieve\", \"top_k\": 5}",
    "csv_summarizer": "name,score\nbm25,0.8\nfull,0.6",
    "unit_converter": "10 cm to m",
    "summarizer": "Skill retrieval finds useful tools. Skill calling executes them. The agent observes results.",
    "language_detector": "hello skill agent",
    "readability_scorer": "This sentence is short. It is easy to read.",
    "title_generator": "Skill retrieval improves agent tool use.",
    "question_generator": "skill retrieval evaluation",
    "checklist_generator": "checklist for running a benchmark",
    "pros_cons_analyzer": "using BM25 as a baseline",
    "argument_mapper": "claim: BM25 is useful because it is simple",
    "email_drafter": "draft email to Lee about the benchmark meeting",
    "todo_extractor": "We need to run BM25. Todo: analyze failures.",
    "meeting_notes_extractor": "Decision: use BM25. Action: run benchmark by 2026-07-15.",
    "translator_zh_en": "你好，人工智能智能体系统",
    "translator_en_zh": "hello skill retrieval agent",
    "keyword_extractor": "Skill retrieval and skill calling are important for agent systems.",
    "regex_extractor": "Contact alice@example.com before 2026-07-15.",
    "entity_extractor": "Alice visited OpenAI in Beijing.",
    "topic_classifier": "The model trains on a retrieval dataset for an agent system.",
    "intent_classifier": "Please summarize this paragraph.",
    "text_rewriter": "skill calling helps agents use tools",
    "grammar_corrector": "she go to school",
    "tone_converter": "make it formal: send me the file",
    "outline_generator": "outline for skill retrieval experiments",
    "sentiment_analyzer": "This is a good and useful baseline.",
    "paper_qa": "What is the core contribution of this paper?",
    "citation_formatter": "author: Smith year: 2024 title: Skill Retrieval",
    "table_formatter": "method: BM25; score: 0.8",
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
