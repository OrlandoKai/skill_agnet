import argparse
import json
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from eval.evaluate import (
    called_skill_names,
    load_jsonl,
    retrieved_skill_names,
    skill_recall_for_row,
    skill_selection_correct,
    task_success,
)


def classify_failure(row: dict) -> str | None:
    gold = row.get("gold_skills", [])
    called = called_skill_names(row)
    task_type = row.get("task_type", "")

    if row.get("invalid_call", False):
        return "invalid_call"

    if task_type == "no_tool" and called:
        return "unnecessary_tool_call"

    if gold and skill_recall_for_row(row) != 1.0:
        return "retrieval_failure"

    if gold and not skill_selection_correct(row):
        return "selection_failure"

    if has_execution_error(row):
        return "execution_failure"

    if not task_success(row):
        return "final_answer_failure"

    return None


def has_execution_error(row: dict) -> bool:
    for observation in row.get("observations", []):
        output = str(observation.get("output", ""))
        if output.lower().startswith("error:") or " failed:" in output.lower():
            return True
    return False


def failure_case(row: dict, failure_type: str) -> dict:
    return {
        "task_id": row.get("task_id", ""),
        "instruction": row.get("instruction", ""),
        "gold_skills": row.get("gold_skills", []),
        "retrieved_skills": retrieved_skill_names(row),
        "called_skills": called_skill_names(row),
        "observations": row.get("observations", []),
        "final_answer": row.get("final_answer", ""),
        "failure_type": failure_type,
        "raw_model_outputs": row.get("raw_model_outputs", []),
    }


def default_failure_path(input_path: str | Path) -> Path:
    input_path = Path(input_path)
    return input_path.parent / f"failure_cases_{input_path.stem}.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze failed SkillBench-Mini cases.")
    parser.add_argument("--input", required=True, help="Input results JSONL path.")
    parser.add_argument("--output", help="Output failure cases JSON path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_jsonl(args.input)
    cases = []
    counts = Counter()

    for row in rows:
        failure_type = classify_failure(row)
        if failure_type:
            counts[failure_type] += 1
            cases.append(failure_case(row, failure_type))

    output_path = Path(args.output) if args.output else default_failure_path(args.input)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "input": str(args.input),
        "num_tasks": len(rows),
        "num_failures": len(cases),
        "failure_counts": dict(counts),
        "failure_cases": cases,
    }
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Failure counts")
    print("--------------")
    for failure_type in [
        "retrieval_failure",
        "selection_failure",
        "invalid_call",
        "execution_failure",
        "final_answer_failure",
        "unnecessary_tool_call",
    ]:
        print(f"{failure_type}: {counts.get(failure_type, 0)}")
    print(f"\nTotal failures: {len(cases)} / {len(rows)}")
    print(f"Saved failure cases JSON: {output_path}")


if __name__ == "__main__":
    main()
