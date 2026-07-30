import json
from pathlib import Path

try:
    from build_skillbench_v2 import SINGLE_SPECS
except ModuleNotFoundError:
    from scripts.build_skillbench_v2 import SINGLE_SPECS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_LIBRARY_PATH = PROJECT_ROOT / "data" / "skill_library.json"
CONTRACT_PATH = PROJECT_ROOT / "data" / "skill_library_v2.json"


REQUIRED_INFO = {
    "calculator": ["arithmetic_expression"],
    "percentage_calculator": ["part_or_base", "whole_or_percent"],
    "ratio_calculator": ["first_quantity", "second_quantity"],
    "equation_solver": ["linear_equation_with_x"],
    "statistics_calculator": ["numeric_values"],
    "number_sequence_analyzer": ["numeric_sequence"],
    "unit_converter": ["numeric_value", "source_unit", "target_unit"],
    "date_difference_calculator": ["first_date", "second_date"],
    "range_filter": ["values", "lower_bound", "upper_bound"],
    "list_sorter": ["items"],
    "deduplicator": ["items"],
    "json_validator": ["json_string"],
    "csv_summarizer": ["csv_rows"],
    "language_detector": ["source_text"],
    "readability_scorer": ["source_text"],
    "title_generator": ["source_text_or_topic"],
    "question_generator": ["source_text_or_topic"],
    "checklist_generator": ["task_or_topic"],
    "pros_cons_analyzer": ["topic_or_option"],
    "argument_mapper": ["claim_or_argument"],
    "email_drafter": ["recipient_or_topic"],
    "todo_extractor": ["source_text"],
    "meeting_notes_extractor": ["meeting_note_text"],
    "translator_zh_en": ["chinese_source_text"],
    "translator_en_zh": ["english_source_text"],
    "keyword_extractor": ["source_text"],
    "regex_extractor": ["source_text_with_patterns"],
    "entity_extractor": ["source_text"],
    "topic_classifier": ["source_text"],
    "intent_classifier": ["source_text"],
    "sentiment_analyzer": ["source_text"],
    "text_rewriter": ["source_text"],
    "grammar_corrector": ["source_text"],
    "tone_converter": ["source_text", "target_tone"],
    "outline_generator": ["topic_or_source_text"],
    "summarizer": ["source_text"],
    "paper_qa": ["paper_question"],
    "citation_formatter": ["citation_metadata"],
    "table_formatter": ["structured_items_or_key_values"],
    "python_executor": ["safe_python_code"],
}


CAN_USE_PREVIOUS_OUTPUT = {
    "summarizer",
    "text_rewriter",
    "keyword_extractor",
    "table_formatter",
    "title_generator",
    "question_generator",
    "checklist_generator",
    "sentiment_analyzer",
    "tone_converter",
    "readability_scorer",
    "language_detector",
    "email_drafter",
    "todo_extractor",
}


UNSUPPORTED_SCOPE = {
    "unit_converter": ["currency conversion", "timezone conversion", "conversion with missing value or unit"],
    "python_executor": ["file IO", "network requests", "system commands", "unsafe imports"],
    "paper_qa": ["answering from a real paper corpus before one is loaded"],
    "email_drafter": ["sending real emails", "accessing a mailbox"],
    "json_validator": ["fixing invalid JSON automatically"],
    "csv_summarizer": ["fetching external CSV files"],
}


def main() -> None:
    legacy = json.loads(SKILL_LIBRARY_PATH.read_text(encoding="utf-8"))
    specs = {spec["skill"]: spec for spec in SINGLE_SPECS}
    contracts = [build_contract(skill, specs.get(skill["name"], {})) for skill in legacy]
    CONTRACT_PATH.write_text(
        json.dumps(contracts, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(contracts)} contracts to {CONTRACT_PATH}")


def build_contract(skill: dict, spec: dict) -> dict:
    name = skill["name"]
    category = spec.get("category", infer_category(name))
    required = REQUIRED_INFO.get(name, ["source_text"])
    keywords = skill.get("keywords", [])
    examples = skill.get("examples", [])
    hard_negatives = spec.get("hard_negatives", [])
    can_use_previous = name in CAN_USE_PREVIOUS_OUTPUT
    status = "active_placeholder" if name == "paper_qa" else "active"
    cannot_do = UNSUPPORTED_SCOPE.get(name, [])
    cannot_do.extend([
        "operate when required input information is missing",
        "perform external side effects unless explicitly implemented as a local skill",
    ])

    return {
        "name": name,
        "version": "2.0",
        "status": status,
        "category": category,
        "description": skill.get("description", ""),
        "capability_scope": {
            "can_do": unique([skill.get("description", ""), spec.get("instruction", ""), *examples]),
            "cannot_do": unique(cannot_do),
        },
        "input_contract": {
            "input_type": "text",
            "required_information": required,
            "optional_information": [],
            "requires_complete_input": True,
            "can_use_previous_output": can_use_previous,
            "missing_info_behavior": "return NONE and ask for the missing information before calling this skill",
        },
        "argument_slots": [
            {
                "name": item,
                "type": infer_slot_type(item),
                "required": True,
                "patterns": slot_patterns(item, spec),
            }
            for item in required
        ],
        "output_contract": {
            "success_prefix": infer_success_prefix(name),
            "success_contains": spec.get("observations", []),
            "error_prefixes": ["Error:", "Unsupported"],
            "faithfulness_rule": "The final answer must preserve successful observation values or report the tool error.",
        },
        "retrieval_contract": {
            "trigger_phrases": unique([name.replace("_", " "), *keywords, *extract_example_triggers(examples)]),
            "anti_trigger_phrases": anti_triggers(name),
            "hard_negative_skills": hard_negatives,
            "retrieval_text": build_retrieval_text(name, skill, spec, keywords),
        },
        "calling_contract": {
            "selection_rules": selection_rules(name, required, hard_negatives),
            "input_builder_hints": input_builder_hints(name, required),
            "previous_output_policy": "allowed" if can_use_previous else "never",
        },
        "examples": {
            "positive": [
                {
                    "instruction": spec.get("instruction", examples[0] if examples else skill.get("description", "")),
                    "input": spec.get("instruction", ""),
                    "output_contains": spec.get("observations", []),
                }
            ],
            "negative": [
                {
                    "instruction": missing_info_example(name),
                    "why_not": "missing required information: " + ", ".join(required),
                }
            ],
            "minimal_pairs": [
                {"wrong_skill": negative, "why_negative": f"confusable with {name} but has different contract"}
                for negative in hard_negatives[:3]
            ],
        },
        "benchmark_support": {
            "task_types": ["single_skill", "multi_skill", "missing_info"],
            "recommended_splits": ["dev", "hard", "hidden"],
            "expected_check_templates": {
                "arguments": required,
                "observations": spec.get("observations", []),
                "final_answer": spec.get("observations", [])[:1],
            },
        },
    }


def infer_category(name: str) -> str:
    if name in {"calculator", "percentage_calculator", "ratio_calculator", "equation_solver", "statistics_calculator", "number_sequence_analyzer"}:
        return "arithmetic_numeric"
    if name in {"unit_converter", "date_difference_calculator"}:
        return "conversion_time"
    if name in {"range_filter", "list_sorter", "deduplicator"}:
        return "list_data_ops"
    if name in {"keyword_extractor", "regex_extractor", "entity_extractor", "todo_extractor", "meeting_notes_extractor"}:
        return "extraction"
    if name in {"sentiment_analyzer", "topic_classifier", "intent_classifier", "language_detector", "readability_scorer"}:
        return "classification"
    if name in {"json_validator", "csv_summarizer", "table_formatter", "citation_formatter"}:
        return "structured_formatting"
    if name in {"python_executor", "paper_qa"}:
        return "code_and_research"
    return "transformation_generation"


def infer_slot_type(slot_name: str) -> str:
    if any(token in slot_name for token in ["value", "quantity", "percent", "bound"]):
        return "number"
    if "date" in slot_name:
        return "date"
    if "unit" in slot_name or "tone" in slot_name:
        return "enum_or_text"
    if "code" in slot_name:
        return "code"
    return "text"


def slot_patterns(slot_name: str, spec: dict) -> list[str]:
    if "unit" in slot_name:
        return ["cm", "m", "kg", "g", "C", "F"]
    if "date" in slot_name:
        return ["2026-03-01"]
    return [str(item) for item in spec.get("arguments", [])[:3]] or [slot_name]


def infer_success_prefix(name: str) -> str:
    prefix = {
        "calculator": "",
        "percentage_calculator": "Percentage:",
        "ratio_calculator": "Ratio:",
        "equation_solver": "Equation solution:",
        "statistics_calculator": "Statistics:",
        "number_sequence_analyzer": "Sequence:",
        "unit_converter": "",
        "date_difference_calculator": "Date difference:",
        "json_validator": "JSON",
        "csv_summarizer": "CSV summary:",
        "table_formatter": "Table:",
        "python_executor": "",
    }
    return prefix.get(name, name.replace("_", " ").title().replace(" ", "") + ":")


def extract_example_triggers(examples: list) -> list[str]:
    triggers = []
    for example in examples:
        text = example if isinstance(example, str) else json.dumps(example, ensure_ascii=False)
        triggers.extend(str(text).split()[:4])
    return triggers


def anti_triggers(name: str) -> list[str]:
    generic = ["what does this skill mean", "explain conceptually", "missing input"]
    custom = {
        "calculator": ["percentage", "ratio", "solve x", "mean"],
        "percentage_calculator": ["ratio", "mean", "raw arithmetic expression"],
        "translator_zh_en": ["into Chinese", "detect language"],
        "translator_en_zh": ["into English", "detect language"],
        "keyword_extractor": ["named entities", "emails and dates", "todos"],
        "entity_extractor": ["keywords", "emails", "dates"],
        "json_validator": ["format as table", "summarize csv"],
        "table_formatter": ["validate json", "summarize csv"],
        "python_executor": ["explain code conceptually", "run unsafe code"],
    }
    return custom.get(name, []) + generic


def selection_rules(name: str, required: list[str], hard_negatives: list[str]) -> list[str]:
    rules = [f"Use {name} only when the request provides: {', '.join(required)}."]
    if hard_negatives:
        rules.append("Do not choose hard negatives when their contract is more specific: " + ", ".join(hard_negatives[:4]) + ".")
    rules.append("If required information is missing, choose NONE and ask for clarification.")
    return rules


def input_builder_hints(name: str, required: list[str]) -> list[str]:
    hints = ["Preserve all numbers, labels, units, dates, and source text needed by the skill."]
    if name in {"summarizer", "keyword_extractor", "table_formatter", "title_generator"}:
        hints.append("For dependent multi-skill calls, use $PREVIOUS_OUTPUT when the instruction refers to the previous result.")
    if name in {"percentage_calculator", "ratio_calculator", "unit_converter", "equation_solver"}:
        hints.append("Do not rewrite the user request into an assertion with changed argument order.")
    if name == "python_executor":
        hints.append("Only pass small, self-contained, safe Python code.")
    return hints


def missing_info_example(name: str) -> str:
    return {
        "unit_converter": "Convert this value to meters.",
        "percentage_calculator": "Calculate the percentage.",
        "equation_solver": "Solve for x.",
        "summarizer": "Summarize the passage.",
        "json_validator": "Validate this JSON.",
    }.get(name, f"Use {name} on the earlier text.")


def build_retrieval_text(name: str, skill: dict, spec: dict, keywords: list[str]) -> str:
    parts = [
        name,
        skill.get("description", ""),
        spec.get("instruction", ""),
        " ".join(keywords),
        "required: " + ", ".join(REQUIRED_INFO.get(name, ["source_text"])),
    ]
    return " ".join(part for part in parts if part).strip()


def unique(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


if __name__ == "__main__":
    main()
