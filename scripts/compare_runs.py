import argparse
import csv
from pathlib import Path


import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from eval.evaluate import compute_metrics, load_jsonl


def method_name(path: str | Path) -> str:
    stem = Path(path).stem
    for prefix in ("run_", "smoke_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix) :]
    for suffix in ("_baseline",):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    if stem.endswith("_120"):
        stem = stem[:-4]
    return stem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare multiple SkillBench-Mini runs.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Input JSONL run files.")
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "results" / "compare_results.csv"),
        help="Output comparison CSV path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = []
    for input_path in args.inputs:
        metrics = compute_metrics(load_jsonl(input_path))
        rows.append({"method": method_name(input_path), **metrics})

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "method",
        "num_tasks",
        "skill_recall",
        "step_retrieval_recall",
        "skill_selection_acc",
        "need_tool_acc",
        "no_tool_acc",
        "abstain_acc",
        "unnecessary_tool_call_rate",
        "abstain_tool_call_rate",
        "skill_sequence_acc",
        "exact_skill_sequence_acc",
        "argument_acc",
        "observation_acc",
        "final_answer_faithfulness_acc",
        "under_call_rate",
        "wrong_order_rate",
        "task_success_rate",
        "strict_task_success_rate",
        "parameter_strict_success_rate",
        "invalid_call_rate",
        "avg_steps",
        "plan_repair_rate",
        "input_repair_rate",
        "final_answer_rule_observation_rate",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(
            {field: row.get(field, "") for field in fieldnames}
            for row in rows
        )

    print_comparison(rows, fieldnames)
    print(f"\nSaved comparison CSV: {output_path}")


def print_comparison(rows: list[dict], fieldnames: list[str]) -> None:
    widths = {
        field: max(len(field), *(len(format_value(row.get(field, ""))) for row in rows))
        for field in fieldnames
    }
    header = " | ".join(field.ljust(widths[field]) for field in fieldnames)
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            " | ".join(
                format_value(row.get(field, "")).ljust(widths[field])
                for field in fieldnames
            )
        )


def format_value(value) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


if __name__ == "__main__":
    main()
