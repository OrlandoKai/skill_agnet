import argparse
import json
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from skills.skill_registry import list_skills


CONTRACT_PATH = PROJECT_ROOT / "data" / "skill_library_v2.json"
LEGACY_PATH = PROJECT_ROOT / "data" / "skill_library.json"

REQUIRED_TOP_FIELDS = {
    "name",
    "version",
    "status",
    "category",
    "description",
    "capability_scope",
    "input_contract",
    "argument_slots",
    "output_contract",
    "retrieval_contract",
    "calling_contract",
    "examples",
    "benchmark_support",
}

REQUIRED_INPUT_FIELDS = {
    "required_information",
    "requires_complete_input",
    "can_use_previous_output",
    "missing_info_behavior",
}

REQUIRED_RETRIEVAL_FIELDS = {
    "trigger_phrases",
    "anti_trigger_phrases",
    "hard_negative_skills",
    "retrieval_text",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect Skill Contract V2 metadata.")
    parser.add_argument("--contracts", default=str(CONTRACT_PATH))
    parser.add_argument("--legacy", default=str(LEGACY_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    contracts = load_json(Path(args.contracts))
    legacy = load_json(Path(args.legacy))
    errors: list[str] = []

    if not isinstance(contracts, list):
        raise SystemExit("Contract file must be a JSON list.")

    contract_names = [item.get("name") for item in contracts if isinstance(item, dict)]
    duplicate_names = [name for name, count in Counter(contract_names).items() if count > 1]
    if duplicate_names:
        errors.append(f"Duplicate contract names: {duplicate_names}")

    registry_names = set(list_skills())
    legacy_names = {item["name"] for item in legacy}
    contract_name_set = set(contract_names)

    if contract_name_set != registry_names:
        errors.append(
            "Contract names and registry names differ: "
            f"contract_only={sorted(contract_name_set - registry_names)}, "
            f"registry_only={sorted(registry_names - contract_name_set)}"
        )
    if contract_name_set != legacy_names:
        errors.append(
            "Contract names and legacy skill_library names differ: "
            f"contract_only={sorted(contract_name_set - legacy_names)}, "
            f"legacy_only={sorted(legacy_names - contract_name_set)}"
        )

    for index, contract in enumerate(contracts, start=1):
        validate_contract(index, contract, registry_names, errors)

    categories = Counter(contract.get("category", "") for contract in contracts)
    statuses = Counter(contract.get("status", "") for contract in contracts)

    print(f"contracts_path: {Path(args.contracts)}")
    print(f"contract_count: {len(contracts)}")
    print(f"categories: {dict(categories)}")
    print(f"statuses: {dict(statuses)}")

    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)

    print("\nSkill contract inspection passed.")


def validate_contract(index: int, contract: dict, registry_names: set[str], errors: list[str]) -> None:
    if not isinstance(contract, dict):
        errors.append(f"Contract row {index} must be an object")
        return
    name = contract.get("name", f"<row {index}>")
    missing = REQUIRED_TOP_FIELDS - set(contract)
    if missing:
        errors.append(f"{name} missing top-level fields: {sorted(missing)}")

    capability = contract.get("capability_scope", {})
    if not isinstance(capability, dict) or not capability.get("can_do") or not capability.get("cannot_do"):
        errors.append(f"{name} capability_scope must include non-empty can_do and cannot_do")

    input_contract = contract.get("input_contract", {})
    if not isinstance(input_contract, dict):
        errors.append(f"{name} input_contract must be an object")
    else:
        missing_input = REQUIRED_INPUT_FIELDS - set(input_contract)
        if missing_input:
            errors.append(f"{name} input_contract missing fields: {sorted(missing_input)}")
        if not input_contract.get("required_information"):
            errors.append(f"{name} input_contract.required_information cannot be empty")

    argument_slots = contract.get("argument_slots", [])
    if not isinstance(argument_slots, list) or not argument_slots:
        errors.append(f"{name} argument_slots must be a non-empty list")
    else:
        for slot in argument_slots:
            if not isinstance(slot, dict) or not slot.get("name") or "required" not in slot:
                errors.append(f"{name} has malformed argument slot: {slot}")

    retrieval = contract.get("retrieval_contract", {})
    if not isinstance(retrieval, dict):
        errors.append(f"{name} retrieval_contract must be an object")
    else:
        missing_retrieval = REQUIRED_RETRIEVAL_FIELDS - set(retrieval)
        if missing_retrieval:
            errors.append(f"{name} retrieval_contract missing fields: {sorted(missing_retrieval)}")
        for negative in retrieval.get("hard_negative_skills", []):
            if negative not in registry_names:
                errors.append(f"{name} has unknown hard negative skill: {negative}")
        if len(str(retrieval.get("retrieval_text", "")).strip()) < 20:
            errors.append(f"{name} retrieval_text is too short")

    calling = contract.get("calling_contract", {})
    if not isinstance(calling, dict) or not calling.get("selection_rules") or not calling.get("input_builder_hints"):
        errors.append(f"{name} calling_contract must include selection_rules and input_builder_hints")

    examples = contract.get("examples", {})
    if not isinstance(examples, dict) or not examples.get("positive") or not examples.get("negative"):
        errors.append(f"{name} examples must include positive and negative examples")

    benchmark_support = contract.get("benchmark_support", {})
    if not isinstance(benchmark_support, dict) or not benchmark_support.get("expected_check_templates"):
        errors.append(f"{name} benchmark_support.expected_check_templates is required")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
