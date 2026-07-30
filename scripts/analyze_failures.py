import argparse
import json
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from eval.evaluate import (
    answer_content_correct,
    argument_correct,
    called_skill_names,
    final_answer_faithfulness_correct,
    invalid_plan,
    load_jsonl,
    multi_skill_under_call,
    need_tool_false_negative,
    observation_correct,
    parameter_strict_success,
    plan_repaired,
    retrieved_skill_names,
    step_retrieval_failure,
    skill_recall_for_row,
    skill_sequence_correct,
    skill_selection_correct,
    strict_task_success,
    unnecessary_tool_call,
    wrong_skill_order,
)


def classify_failure(row: dict) -> str | None:
    gold = row.get("gold_skills", [])
    called = called_skill_names(row)
    task_type = row.get("task_type", "")

    if isinstance(row.get("need_tool_decision"), dict) and need_tool_false_negative(row):
        return "need_tool_false_negative"

    if task_type == "missing_info" and called:
        return "missing_info_overcall"

    if task_type == "unsupported_tool" and called:
        return "unsupported_tool_overcall"

    if task_type == "missing_info" and not called and not answer_content_correct(row):
        return "missing_info_no_clarification"

    if task_type == "unsupported_tool" and not called and not answer_content_correct(row):
        return "unsupported_tool_no_refusal"

    if invalid_plan(row):
        return "invalid_plan"

    if row.get("invalid_call", False):
        return "invalid_call"

    if unnecessary_tool_call(row):
        return "no_tool_overcall"

    if row.get("retrieved_by_step") and step_retrieval_failure(row):
        return "step_retrieval_failure"

    if gold and skill_recall_for_row(row) != 1.0:
        return "retrieval_failure"

    if plan_repaired(row) and gold and not skill_sequence_correct(row):
        return "planner_repair_failure"

    if gold and not skill_selection_correct(row):
        if multi_skill_under_call(row):
            return "multi_skill_under_call"
        return "skill_selection_failure"

    if wrong_skill_order(row):
        return "wrong_skill_order"

    if gold and not skill_sequence_correct(row):
        return "skill_selection_failure"

    if has_execution_error(row):
        return "execution_failure"

    if gold and skill_sequence_correct(row) and argument_correct(row) is False:
        return "argument_construction_failure"

    if gold and skill_sequence_correct(row) and observation_correct(row) is False:
        return "observation_correctness_failure"

    if final_answer_faithfulness_correct(row) is False:
        return "final_faithfulness_failure"

    if gold and skill_sequence_correct(row) and not answer_content_correct(row):
        if row.get("final_answer_source") == "rule_observation":
            return "input_construction_failure"
        return "final_grounding_failure"

    if not answer_content_correct(row) or not strict_task_success(row) or not parameter_strict_success(row):
        return "final_answer_hallucination"

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
        "task_type": row.get("task_type", ""),
        "instruction": row.get("instruction", ""),
        "gold_skills": row.get("gold_skills", []),
        "retrieved_skills": retrieved_skill_names(row),
        "subtasks": row.get("subtasks", []),
        "retrieved_by_step": row.get("retrieved_by_step", []),
        "need_tool_decision": row.get("need_tool_decision", {}),
        "planned_skills": row.get("planned_skills", []),
        "planned_steps": row.get("planned_steps", []),
        "plan_valid": row.get("plan_valid", None),
        "plan_repaired": row.get("plan_repaired", None),
        "called_skills": called_skill_names(row),
        "observations": row.get("observations", []),
        "final_answer": row.get("final_answer", ""),
        "expected_checks": row.get("expected_checks", {}),
        "final_answer_source": row.get("final_answer_source", ""),
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
        "need_tool_false_negative",
        "missing_info_overcall",
        "unsupported_tool_overcall",
        "missing_info_no_clarification",
        "unsupported_tool_no_refusal",
        "invalid_plan",
        "step_retrieval_failure",
        "planner_repair_failure",
        "retrieval_failure",
        "skill_selection_failure",
        "no_tool_overcall",
        "multi_skill_under_call",
        "wrong_skill_order",
        "invalid_call",
        "execution_failure",
        "argument_construction_failure",
        "observation_correctness_failure",
        "final_faithfulness_failure",
        "input_construction_failure",
        "final_grounding_failure",
        "final_answer_hallucination",
    ]:
        print(f"{failure_type}: {counts.get(failure_type, 0)}")
    print(f"\nTotal failures: {len(cases)} / {len(rows)}")
    print(f"Saved failure cases JSON: {output_path}")


if __name__ == "__main__":
    main()
