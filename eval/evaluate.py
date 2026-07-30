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


ABSTAIN_TASK_TYPES = {"no_tool", "missing_info", "unsupported_tool"}


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
    if row.get("task_type") in ABSTAIN_TASK_TYPES or not gold:
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
    gold_needs_tool = bool(row.get("gold_skills", [])) and row.get("task_type") not in ABSTAIN_TASK_TYPES
    predicted_needs_tool = predicted_need_tool(row)
    return gold_needs_tool == predicted_needs_tool


def need_tool_false_negative(row: dict) -> bool:
    gold_needs_tool = bool(row.get("gold_skills", [])) and row.get("task_type") not in ABSTAIN_TASK_TYPES
    return gold_needs_tool and not predicted_need_tool(row)


def no_tool_correct(row: dict) -> bool | None:
    if row.get("task_type") != "no_tool":
        return None
    return not called_skill_names(row) and not bool(row.get("invalid_call", False))


def abstain_correct(row: dict) -> bool | None:
    if row.get("task_type") not in ABSTAIN_TASK_TYPES:
        return None
    return not called_skill_names(row) and not bool(row.get("invalid_call", False))


def unnecessary_tool_call(row: dict) -> bool:
    return row.get("task_type") == "no_tool" and bool(called_skill_names(row))


def abstain_tool_call(row: dict) -> bool:
    return row.get("task_type") in ABSTAIN_TASK_TYPES and bool(called_skill_names(row))


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

    if task_type in ABSTAIN_TASK_TYPES or not gold:
        return len(called) == 0
    if task_type == "single_skill":
        return all(skill in called for skill in gold)
    if task_type == "multi_skill":
        return _is_ordered_subsequence(gold, called)
    return all(skill in called for skill in gold)


def exact_skill_sequence_correct(row: dict) -> bool:
    gold = row.get("gold_skills", [])
    called = called_skill_names(row)
    if row.get("task_type") in ABSTAIN_TASK_TYPES or not gold:
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

    if row.get("task_type") in ABSTAIN_TASK_TYPES:
        return abstain_correct(row) is True and answer_content_correct(row)

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
    if row.get("task_type") in ABSTAIN_TASK_TYPES:
        checks = _expected_checks(row)
        final_check = checks.get("final_answer", {})
        if final_check:
            return _text_matches_check(final_answer, final_check)
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
    if row.get("task_type") in ABSTAIN_TASK_TYPES:
        return abstain_correct(row) is True and bool(str(row.get("final_answer", "")).strip()) and answer_content_correct(row)
    return skill_sequence_correct(row) and answer_content_correct(row)


def argument_correct(row: dict) -> bool | None:
    checks = _expected_checks(row).get("arguments", [])
    if not checks:
        return None
    return all(_check_skill_text(row, check, "input") for check in checks)


def observation_correct(row: dict) -> bool | None:
    checks = _expected_checks(row).get("observations", [])
    if not checks:
        return None
    return all(_check_skill_text(row, check, "output") for check in checks)


def final_answer_faithfulness_correct(row: dict) -> bool | None:
    checks = _expected_checks(row)
    final_check = checks.get("final_answer", {})
    needs_faithfulness = bool(checks.get("faithfulness", False))
    if not final_check and not needs_faithfulness:
        return None

    final_answer = str(row.get("final_answer", ""))
    if final_check and not _text_matches_check(final_answer, final_check):
        return False

    if not needs_faithfulness:
        return True

    observations = row.get("observations", [])
    outputs = [str(item.get("output", "")) for item in observations if isinstance(item, dict)]
    has_error = any(_is_error_text(output) for output in outputs)
    final_lower = final_answer.lower()

    if has_error:
        return any(word in final_lower for word in ["error", "failed", "unable", "could not"])

    if outputs and any(word in final_lower for word in ["unable", "failed", "could not"]):
        return False

    observation_checks = checks.get("observations", [])
    if observation_checks:
        expected_tokens = []
        for check in observation_checks:
            expected_tokens.extend(str(value) for value in check.get("contains", []))
        if expected_tokens and not any(
            _contains_normalized(final_answer, token) for token in expected_tokens
        ):
            return False

    return True


def parameter_strict_success(row: dict) -> bool:
    checks = _expected_checks(row)
    if not checks:
        return strict_task_success(row)
    if row.get("invalid_call"):
        return False
    if row.get("task_type") in ABSTAIN_TASK_TYPES:
        return abstain_correct(row) is True and bool(str(row.get("final_answer", "")).strip()) and answer_content_correct(row)

    argument_value = argument_correct(row)
    observation_value = observation_correct(row)
    faithfulness_value = final_answer_faithfulness_correct(row)
    return (
        exact_skill_sequence_correct(row)
        and (argument_value is not False)
        and (observation_value is not False)
        and (faithfulness_value is not False)
    )


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
    abstain_values = [
        value for value in (abstain_correct(row) for row in rows) if value is not None
    ]
    unnecessary_values = [unnecessary_tool_call(row) for row in rows if row.get("task_type") == "no_tool"]
    abstain_tool_call_values = [
        abstain_tool_call(row) for row in rows if row.get("task_type") in ABSTAIN_TASK_TYPES
    ]
    sequence_values = [skill_sequence_correct(row) for row in rows]
    exact_sequence_values = [exact_skill_sequence_correct(row) for row in rows]
    argument_values = [
        value for value in (argument_correct(row) for row in rows) if value is not None
    ]
    observation_values = [
        value for value in (observation_correct(row) for row in rows) if value is not None
    ]
    faithfulness_values = [
        value
        for value in (final_answer_faithfulness_correct(row) for row in rows)
        if value is not None
    ]
    multi_rows = [row for row in rows if row.get("task_type") == "multi_skill"]
    under_call_values = [multi_skill_under_call(row) for row in multi_rows]
    wrong_order_values = [wrong_skill_order(row) for row in multi_rows]
    success_values = [task_success(row) for row in rows]
    strict_success_values = [strict_task_success(row) for row in rows]
    parameter_strict_values = [parameter_strict_success(row) for row in rows]
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
        "abstain_acc": _mean(abstain_values),
        "unnecessary_tool_call_rate": _mean(unnecessary_values),
        "abstain_tool_call_rate": _mean(abstain_tool_call_values),
        "skill_sequence_acc": _mean(sequence_values),
        "exact_skill_sequence_acc": _mean(exact_sequence_values),
        "argument_acc": _mean(argument_values),
        "observation_acc": _mean(observation_values),
        "final_answer_faithfulness_acc": _mean(faithfulness_values),
        "under_call_rate": _mean(under_call_values),
        "wrong_order_rate": _mean(wrong_order_values),
        "task_success_rate": _mean(success_values),
        "strict_task_success_rate": _mean(strict_success_values),
        "parameter_strict_success_rate": _mean(parameter_strict_values),
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


def _expected_checks(row: dict) -> dict:
    checks = row.get("expected_checks", {})
    return checks if isinstance(checks, dict) else {}


def _check_skill_text(row: dict, check: dict, field: str) -> bool:
    if not isinstance(check, dict):
        return False
    skill_name = str(check.get("skill", "")).strip()
    values = _candidate_skill_texts(row, skill_name, field)
    if not values:
        return False
    return any(_text_matches_check(value, check) for value in values)


def _candidate_skill_texts(row: dict, skill_name: str, field: str) -> list[str]:
    values = []
    for observation in row.get("observations", []):
        if not isinstance(observation, dict):
            continue
        if skill_name and observation.get("skill") != skill_name:
            continue
        values.append(str(observation.get(field, "")))

    if field == "input":
        for step in row.get("planned_steps", []):
            if not isinstance(step, dict):
                continue
            if skill_name and step.get("skill") != skill_name:
                continue
            values.append(str(step.get("input", "")))

    return [value for value in values if value.strip()]


def _text_matches_check(text: str, check: dict) -> bool:
    for needle in check.get("contains", []):
        if not _contains_normalized(text, str(needle)):
            return False
    for needle in check.get("not_contains", []):
        if _contains_normalized(text, str(needle)):
            return False
    for pattern in check.get("regex", []):
        if not re.search(str(pattern), str(text), flags=re.IGNORECASE):
            return False
    return True


def _contains_normalized(text: str, needle: str) -> bool:
    text_norm = _normalize_for_check(text)
    needle_norm = _normalize_for_check(needle)
    return needle_norm in text_norm


def _normalize_for_check(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def _is_error_text(text: str) -> bool:
    lowered = str(text).lower()
    return lowered.startswith("error:") or "unsupported" in lowered or "failed" in lowered


if __name__ == "__main__":
    main()
