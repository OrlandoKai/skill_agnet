import argparse
import csv
import json
import re
from pathlib import Path


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "both",
    "by",
    "for",
    "in",
    "is",
    "it",
    "of",
    "or",
    "should",
    "that",
    "the",
    "to",
    "with",
}


def load_jsonl(path: str | Path) -> list[dict]:
    path = Path(path)
    rows = []
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no} of {path}: {exc}") from exc
    return rows


def retrieved_skill_names(row: dict) -> list[str]:
    return [
        str(skill.get("name", ""))
        for skill in row.get("retrieved_skills", [])
        if isinstance(skill, dict) and skill.get("name")
    ]


def called_skill_names(row: dict) -> list[str]:
    return [
        str(skill)
        for skill in row.get("called_skills", [])
        if str(skill).strip() and str(skill).upper() != "NONE"
    ]


def skill_recall_for_row(row: dict) -> float | None:
    gold = row.get("gold_skills", [])
    if not gold:
        return None
    retrieved = set(retrieved_skill_names(row))
    hits = sum(1 for skill in gold if skill in retrieved)
    return hits / len(gold)


def step_retrieval_recall_for_row(row: dict) -> float | None:
    gold = row.get("gold_skills", [])
    retrieved_by_step = row.get("retrieved_by_step", [])
    if not gold or not isinstance(retrieved_by_step, list):
        return None
    if not retrieved_by_step:
        return skill_recall_for_row(row)

    hits = 0
    for index, gold_skill in enumerate(gold):
        step_index = min(index, len(retrieved_by_step) - 1)
        step = retrieved_by_step[step_index]
        step_skills = {
            skill.get("name", "")
            for skill in step.get("retrieved_skills", [])
            if isinstance(skill, dict)
        }
        if gold_skill in step_skills:
            hits += 1
    return hits / len(gold)


def step_retrieval_failure(row: dict) -> bool:
    value = step_retrieval_recall_for_row(row)
    return value is not None and value < 1.0


def skill_selection_correct(row: dict) -> bool:
    gold = row.get("gold_skills", [])
    called = set(called_skill_names(row))
    if row.get("task_type") == "no_tool" or not gold:
        return len(called) == 0
    return all(skill in called for skill in gold)


def predicted_need_tool(row: dict) -> bool:
    decision = row.get("need_tool_decision")
    if isinstance(decision, dict) and "need_tool" in decision:
        parsed = _coerce_bool(decision.get("need_tool"))
        if parsed is not None:
            return parsed
    return bool(called_skill_names(row))


def need_tool_correct(row: dict) -> bool:
    gold_needs_tool = bool(row.get("gold_skills", [])) and row.get("task_type") != "no_tool"
    predicted_needs_tool = predicted_need_tool(row)
    return gold_needs_tool == predicted_needs_tool


def need_tool_false_negative(row: dict) -> bool:
    gold_needs_tool = bool(row.get("gold_skills", [])) and row.get("task_type") != "no_tool"
    return gold_needs_tool and not predicted_need_tool(row)


def no_tool_correct(row: dict) -> bool | None:
    if row.get("task_type") != "no_tool":
        return None
    return not called_skill_names(row) and not bool(row.get("invalid_call", False))


def unnecessary_tool_call(row: dict) -> bool:
    return row.get("task_type") == "no_tool" and bool(called_skill_names(row))


def invalid_plan(row: dict) -> bool:
    return row.get("plan_valid") is False


def plan_repaired(row: dict) -> bool:
    return bool(row.get("plan_repaired", False))


def input_repaired(row: dict) -> bool:
    for step in row.get("planned_steps", []):
        if isinstance(step, dict) and step.get("input_source") in {
            "rule",
            "previous_output",
            "repaired",
        }:
            return True
    return False


def skill_sequence_correct(row: dict) -> bool:
    gold = row.get("gold_skills", [])
    called = called_skill_names(row)
    task_type = row.get("task_type", "")

    if task_type == "no_tool" or not gold:
        return len(called) == 0
    if task_type == "single_skill":
        return all(skill in called for skill in gold)
    if task_type == "multi_skill":
        return _is_ordered_subsequence(gold, called)
    return all(skill in called for skill in gold)


def exact_skill_sequence_correct(row: dict) -> bool:
    gold = row.get("gold_skills", [])
    called = called_skill_names(row)
    if row.get("task_type") == "no_tool" or not gold:
        return len(called) == 0
    return called == gold


def multi_skill_under_call(row: dict) -> bool:
    if row.get("task_type") != "multi_skill":
        return False
    gold = row.get("gold_skills", [])
    called = called_skill_names(row)
    return len(called) < len(gold) or any(skill not in called for skill in gold)


def wrong_skill_order(row: dict) -> bool:
    if row.get("task_type") != "multi_skill":
        return False
    gold = row.get("gold_skills", [])
    called = called_skill_names(row)
    return all(skill in called for skill in gold) and not _is_ordered_subsequence(gold, called)


def task_success(row: dict) -> bool:
    if row.get("invalid_call"):
        return False

    final_answer = str(row.get("final_answer", "")).strip()
    if not final_answer:
        return False

    if row.get("task_type") == "no_tool":
        return True

    expected = str(row.get("expected_answer", "")).strip()
    if not expected:
        return True

    numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", expected)
    normalized_final = _normalize_text(final_answer)
    if numbers:
        return all(number in normalized_final for number in numbers)

    keywords = extract_keywords(expected)
    if not keywords:
        return expected.lower() in final_answer.lower()

    hits = sum(1 for keyword in keywords if keyword in normalized_final)
    required = 1 if len(keywords) <= 3 else max(1, len(keywords) // 2)
    return hits >= required


def answer_content_correct(row: dict) -> bool:
    final_answer = str(row.get("final_answer", "")).strip()
    if not final_answer:
        return False
    if row.get("task_type") == "no_tool":
        return True

    expected = str(row.get("expected_answer", "")).strip()
    if not expected:
        return True

    numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", expected)
    normalized_final = _normalize_text(final_answer)
    if numbers:
        return all(number in normalized_final for number in numbers)

    keywords = extract_keywords(expected)
    if not keywords:
        return expected.lower() in final_answer.lower()

    hits = sum(1 for keyword in keywords if keyword in normalized_final)
    required = 1 if len(keywords) <= 3 else max(1, len(keywords) // 2)
    return hits >= required


def strict_task_success(row: dict) -> bool:
    if row.get("invalid_call"):
        return False
    if row.get("task_type") == "no_tool":
        return no_tool_correct(row) is True and bool(str(row.get("final_answer", "")).strip())
    return skill_sequence_correct(row) and answer_content_correct(row)


def extract_keywords(text: str) -> list[str]:
    normalized = _normalize_text(text)
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+|[\u4e00-\u9fff]{2,}", normalized)
    keywords = []
    for token in tokens:
        lowered = token.lower()
        if lowered not in STOPWORDS and lowered not in keywords:
            keywords.append(lowered)
    return keywords


def compute_metrics(rows: list[dict]) -> dict:
    num_tasks = len(rows)
    recall_values = [
        value for value in (skill_recall_for_row(row) for row in rows) if value is not None
    ]
    step_recall_values = [
        value
        for value in (step_retrieval_recall_for_row(row) for row in rows)
        if value is not None
    ]
    selection_values = [skill_selection_correct(row) for row in rows]
    need_tool_values = [need_tool_correct(row) for row in rows]
    no_tool_values = [
        value for value in (no_tool_correct(row) for row in rows) if value is not None
    ]
    unnecessary_values = [unnecessary_tool_call(row) for row in rows if row.get("task_type") == "no_tool"]
    sequence_values = [skill_sequence_correct(row) for row in rows]
    exact_sequence_values = [exact_skill_sequence_correct(row) for row in rows]
    multi_rows = [row for row in rows if row.get("task_type") == "multi_skill"]
    under_call_values = [multi_skill_under_call(row) for row in multi_rows]
    wrong_order_values = [wrong_skill_order(row) for row in multi_rows]
    success_values = [task_success(row) for row in rows]
    strict_success_values = [strict_task_success(row) for row in rows]
    invalid_values = [bool(row.get("invalid_call", False)) for row in rows]
    step_values = [len(called_skill_names(row)) for row in rows]
    plan_repair_values = [plan_repaired(row) for row in rows if "plan_repaired" in row]
    input_repair_values = [input_repaired(row) for row in rows if row.get("planned_steps")]
    final_sources = [str(row.get("final_answer_source", "")) for row in rows]

    return {
        "num_tasks": num_tasks,
        "skill_recall": _mean(recall_values),
        "step_retrieval_recall": _mean(step_recall_values),
        "skill_selection_acc": _mean(selection_values),
        "need_tool_acc": _mean(need_tool_values),
        "no_tool_acc": _mean(no_tool_values),
        "unnecessary_tool_call_rate": _mean(unnecessary_values),
        "skill_sequence_acc": _mean(sequence_values),
        "exact_skill_sequence_acc": _mean(exact_sequence_values),
        "under_call_rate": _mean(under_call_values),
        "wrong_order_rate": _mean(wrong_order_values),
        "task_success_rate": _mean(success_values),
        "strict_task_success_rate": _mean(strict_success_values),
        "invalid_call_rate": _mean(invalid_values),
        "avg_steps": _mean(step_values),
        "plan_repair_rate": _mean(plan_repair_values),
        "input_repair_rate": _mean(input_repair_values),
        "final_answer_rule_observation_rate": _rate(final_sources, "rule_observation"),
        "final_answer_llm_grounded_rate": _rate(final_sources, "llm_grounded"),
        "final_answer_direct_answer_rate": _rate(final_sources, "direct_answer"),
        "final_answer_tool_error_rate": _rate(final_sources, "tool_error"),
    }


def save_metrics_csv(metrics: dict, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(metrics.keys()))
        writer.writeheader()
        writer.writerow(metrics)
    return output_path


def default_metrics_path(input_path: str | Path) -> Path:
    input_path = Path(input_path)
    return input_path.parent / f"metrics_{input_path.stem}.csv"


def print_metrics(metrics: dict) -> None:
    print("Evaluation metrics")
    print("------------------")
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}")
        else:
            print(f"{key}: {value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a SkillBench-Mini JSONL run.")
    parser.add_argument("--input", required=True, help="Input results JSONL path.")
    parser.add_argument("--output", help="Output metrics CSV path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_jsonl(args.input)
    metrics = compute_metrics(rows)
    output_path = Path(args.output) if args.output else default_metrics_path(args.input)
    save_metrics_csv(metrics, output_path)
    print_metrics(metrics)
    print(f"\nSaved metrics CSV: {output_path}")


def _mean(values) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(float(value) for value in values) / len(values)


def _rate(values, expected: str) -> float:
    values = [value for value in values if value]
    if not values:
        return 0.0
    return sum(1 for value in values if value == expected) / len(values)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def _coerce_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return None


def _is_ordered_subsequence(expected: list[str], actual: list[str]) -> bool:
    if not expected:
        return not actual
    position = 0
    for skill in actual:
        if position < len(expected) and skill == expected[position]:
            position += 1
    return position == len(expected)


if __name__ == "__main__":
    main()
