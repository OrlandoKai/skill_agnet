import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from retrievers.bm25_retriever import BM25SkillRetriever
from retrievers.embedding_retriever import EmbeddingSkillRetriever
from retrievers.full_prompt_retriever import FullPromptRetriever


BENCHMARK_PATH = PROJECT_ROOT / "data" / "skillbench_mini.json"


def load_benchmark() -> list[dict]:
    return json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))


def hit_status(gold_skills: list[str], retrieved_names: list[str]) -> str:
    if not gold_skills:
        return "N/A"
    hits = [skill for skill in gold_skills if skill in retrieved_names]
    if len(hits) == len(gold_skills):
        return "HIT_ALL"
    if hits:
        return f"HIT_PARTIAL({','.join(hits)})"
    return "MISS"


def print_result(label: str, task: dict, retrieved: list[dict]) -> None:
    names = [skill["name"] for skill in retrieved]
    print(f"  {label}: {names} -> {hit_status(task['gold_skills'], names)}")


def main() -> None:
    tasks = load_benchmark()[:10]
    retrievers = [
        ("Full Prompt", FullPromptRetriever()),
        ("BM25 top-5", BM25SkillRetriever()),
    ]

    try:
        retrievers.append(("Embedding top-5", EmbeddingSkillRetriever()))
    except Exception as exc:
        print(f"[Embedding retriever unavailable] {exc}")

    for task in tasks:
        print("=" * 80)
        print(f"{task['task_id']}: {task['instruction']}")
        print(f"gold_skills: {task['gold_skills']}")
        for label, retriever in retrievers:
            top_k = 5 if label != "Full Prompt" else 999
            print_result(label, task, retriever.retrieve(task["instruction"], top_k=top_k))


if __name__ == "__main__":
    main()
