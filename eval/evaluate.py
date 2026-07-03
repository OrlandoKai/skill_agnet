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


def skill_selection_correct(row: dict) -> bool:
    gold = row.get("gold_skills", [])
    called = set(called_skill_names(row))
    if row.get("task_type") == "no_tool" or not gold:
        return len(called) == 0
    return all(skill in called for skill in gold)


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
    selection_values = [skill_selection_correct(row) for row in rows]
    success_values = [task_success(row) for row in rows]
    invalid_values = [bool(row.get("invalid_call", False)) for row in rows]
    step_values = [len(called_skill_names(row)) for row in rows]

    return {
        "num_tasks": num_tasks,
        "skill_recall": _mean(recall_values),
        "skill_selection_acc": _mean(selection_values),
        "task_success_rate": _mean(success_values),
        "invalid_call_rate": _mean(invalid_values),
        "avg_steps": _mean(step_values),
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


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()


if __name__ == "__main__":
    main()
