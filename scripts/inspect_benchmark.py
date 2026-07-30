import json
import sys
import argparse
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = PROJECT_ROOT / "data" / "skillbench_mini.json"
SKILL_LIBRARY_PATH = PROJECT_ROOT / "data" / "skill_library.json"
sys.path.insert(0, str(PROJECT_ROOT))

from skills.skill_registry import list_skills

REQUIRED_FIELDS = {
    "task_id",
    "instruction",
    "gold_skills",
    "expected_answer",
    "task_type",
    "notes",
}
EXPECTED_COUNTS = {
    "single_skill": 60,
    "multi_skill": 40,
    "no_tool": 20,
    "missing_info": 0,
    "unsupported_tool": 0,
}
EXPECTED_SKILL_COUNT = 40
VALID_TASK_TYPES = set(EXPECTED_COUNTS)
ABSTAIN_TASK_TYPES = {"no_tool", "missing_info", "unsupported_tool"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a SkillBench benchmark JSON file.")
    parser.add_argument(
        "--benchmark",
        default=str(BENCHMARK_PATH),
        help="Benchmark JSON path.",
    )
    parser.add_argument("--expected_single", type=int, default=EXPECTED_COUNTS["single_skill"])
    parser.add_argument("--expected_multi", type=int, default=EXPECTED_COUNTS["multi_skill"])
    parser.add_argument("--expected_no_tool", type=int, default=EXPECTED_COUNTS["no_tool"])
    parser.add_argument(
        "--expected_missing_info",
        type=int,
        default=EXPECTED_COUNTS["missing_info"],
    )
    parser.add_argument(
        "--expected_unsupported_tool",
        type=int,
        default=EXPECTED_COUNTS["unsupported_tool"],
    )
    parser.add_argument(
        "--require_expected_checks",
        action="store_true",
        help="Require expected_checks on every tool task.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    errors = []
    benchmark_path = Path(args.benchmark)
    expected_counts = {
        "single_skill": args.expected_single,
        "multi_skill": args.expected_multi,
        "no_tool": args.expected_no_tool,
        "missing_info": args.expected_missing_info,
        "unsupported_tool": args.expected_unsupported_tool,
    }
    require_expected_checks = args.require_expected_checks

    benchmark = load_json(benchmark_path)
    skills = load_json(SKILL_LIBRARY_PATH)
    skill_names = {skill["name"] for skill in skills}
    registry_names = set(list_skills())

    if not isinstance(benchmark, list):
        raise SystemExit("Benchmark must be a JSON list.")
    if len(skill_names) != EXPECTED_SKILL_COUNT:
        errors.append(
            f"Expected {EXPECTED_SKILL_COUNT} skills in skill_library.json, found {len(skill_names)}"
        )
    if skill_names != registry_names:
        errors.append(
            "skill_library.json and skill_registry.py are out of sync: "
            f"library_only={sorted(skill_names - registry_names)}, "
            f"registry_only={sorted(registry_names - skill_names)}"
        )

    task_ids = [item.get("task_id") for item in benchmark if isinstance(item, dict)]
    duplicates = sorted(task_id for task_id, count in Counter(task_ids).items() if count > 1)
    if duplicates:
        errors.append(f"Duplicate task_id values: {duplicates}")

    counts = Counter()
    for index, item in enumerate(benchmark, start=1):
        missing = REQUIRED_FIELDS - set(item)
        if missing:
            errors.append(f"Row {index} missing fields: {sorted(missing)}")
            continue

        task_type = item["task_type"]
        counts[task_type] += 1
        if task_type not in VALID_TASK_TYPES:
            errors.append(f"{item['task_id']} has invalid task_type: {task_type}")

        gold_skills = item["gold_skills"]
        if not isinstance(gold_skills, list):
            errors.append(f"{item['task_id']} gold_skills must be a list")
            continue

        unknown = [skill for skill in gold_skills if skill not in skill_names]
        if unknown:
            errors.append(f"{item['task_id']} has unknown gold skills: {unknown}")

        if task_type == "single_skill" and len(gold_skills) != 1:
            errors.append(f"{item['task_id']} single_skill must have exactly 1 gold skill")
        if task_type == "multi_skill" and len(gold_skills) < 2:
            errors.append(f"{item['task_id']} multi_skill must have at least 2 gold skills")
        if task_type in ABSTAIN_TASK_TYPES and gold_skills:
            errors.append(f"{item['task_id']} {task_type} must have empty gold_skills")
        if task_type in {"missing_info", "unsupported_tool"} and item.get("gold_sequence", []) != []:
            errors.append(f"{item['task_id']} {task_type} must have empty gold_sequence")

        should_check_expected = require_expected_checks and (
            str(item.get("task_id", "")).startswith(("dev_", "hard_", "hidden_"))
            or benchmark_path.name in {"skillbench_heldout.json", "skillbench_hard.json", "skillbench_hidden.json"}
            or task_type in {"missing_info", "unsupported_tool"}
        )
        if should_check_expected:
            validate_expected_checks(item, task_type, errors)

    for task_type, expected in expected_counts.items():
        if counts[task_type] != expected:
            errors.append(
                f"Expected {expected} {task_type} tasks, found {counts[task_type]}"
            )

    if require_expected_checks:
        covered_skills = {
            skill
            for item in benchmark
            for skill in item.get("gold_skills", [])
            if isinstance(item, dict)
        }
        missing_coverage = sorted(skill_names - covered_skills)
        if missing_coverage:
            errors.append(f"Benchmark does not cover these skills: {missing_coverage}")

    print(f"benchmark_path: {benchmark_path}")
    print(f"total_tasks: {len(benchmark)}")
    print(f"counts: {dict(counts)}")
    print(f"skill_count: {len(skill_names)}")
    print(f"available_skills: {sorted(skill_names)}")

    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)

    print("\nBenchmark inspection passed.")


def validate_expected_checks(item: dict, task_type: str, errors: list[str]) -> None:
    checks = item.get("expected_checks")
    task_id = item.get("task_id", "<unknown>")
    if not isinstance(checks, dict):
        errors.append(f"{task_id} missing expected_checks")
        return

    final_check = checks.get("final_answer")
    if task_type in ABSTAIN_TASK_TYPES:
        if not isinstance(final_check, dict):
            errors.append(f"{task_id} abstain task missing expected_checks.final_answer")
        return

    for field in ("arguments", "observations"):
        values = checks.get(field)
        if not isinstance(values, list) or not values:
            errors.append(f"{task_id} tool task missing expected_checks.{field}")
        else:
            for index, value in enumerate(values, start=1):
                if not isinstance(value, dict) or not value.get("skill"):
                    errors.append(f"{task_id} expected_checks.{field}[{index}] missing skill")
    if not isinstance(final_check, dict):
        errors.append(f"{task_id} tool task missing expected_checks.final_answer")


if __name__ == "__main__":
    main()
