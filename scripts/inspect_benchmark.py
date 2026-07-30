import json
import sys
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
EXPECTED_COUNTS = {"single_skill": 60, "multi_skill": 40, "no_tool": 20}
EXPECTED_SKILL_COUNT = 40
VALID_TASK_TYPES = set(EXPECTED_COUNTS)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    errors = []
    benchmark = load_json(BENCHMARK_PATH)
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
        if task_type == "no_tool" and gold_skills:
            errors.append(f"{item['task_id']} no_tool must have empty gold_skills")

    for task_type, expected in EXPECTED_COUNTS.items():
        if counts[task_type] != expected:
            errors.append(
                f"Expected {expected} {task_type} tasks, found {counts[task_type]}"
            )

    print(f"benchmark_path: {BENCHMARK_PATH}")
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


if __name__ == "__main__":
    main()
