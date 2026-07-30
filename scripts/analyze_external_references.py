"""Analyze small external tool-use benchmark references.

This script summarizes downloaded reference files under
data/external_references/. It does not modify benchmark data; it only writes
analysis artifacts that can guide SkillBench split design.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REF_DIR = ROOT / "data" / "external_references"
OUT_JSON = REF_DIR / "external_reference_analysis.json"
OUT_MD = ROOT / "docs" / "benchmark_design" / "external_reference_analysis.md"


def read_json_or_jsonl(path: Path) -> list[Any]:
    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        data = json.loads(stripped)
        return data if isinstance(data, list) else [data]
    rows = []
    for line in stripped.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def sample_keys(rows: list[Any]) -> list[str]:
    for row in rows:
        if isinstance(row, dict):
            return sorted(row.keys())
    return []


def analyze_metatool() -> dict[str, Any]:
    base = REF_DIR / "metatool"
    result: dict[str, Any] = {"files": {}}

    csv_path = base / "all_clean_data.csv"
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        result["files"]["all_clean_data.csv"] = {
            "rows": len(rows),
            "columns": reader.fieldnames or [],
            "sample": rows[:3],
        }
        for key in ["Tool", "tool", "label", "Label", "Tools", "api_name"]:
            if rows and key in rows[0]:
                result["files"]["all_clean_data.csv"][f"{key}_top10"] = Counter(
                    row.get(key, "") for row in rows
                ).most_common(10)

    multi_path = base / "multi_tool_query_golden.json"
    if multi_path.exists():
        rows = read_json_or_jsonl(multi_path)
        result["files"]["multi_tool_query_golden.json"] = {
            "rows": len(rows),
            "keys": sample_keys(rows),
            "sample": rows[:3],
        }

    for name in ["plugin_des.json", "plugin_info.json"]:
        path = base / name
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                count = len(data)
                sample = list(data.items())[:3]
            elif isinstance(data, list):
                count = len(data)
                sample = data[:3]
            else:
                count = 1
                sample = [data]
            result["files"][name] = {
                "items": count,
                "sample": sample,
            }

    result["takeaways"] = [
        "Useful for tool-use awareness, similar-tool selection, and multi-tool query design.",
        "Plugin/tool descriptions are reusable as inspiration for richer skill contracts.",
    ]
    return result


def analyze_bfcl() -> dict[str, Any]:
    base = REF_DIR / "bfcl"
    result: dict[str, Any] = {"files": {}}
    for path in sorted(base.glob("BFCL_*.json")):
        rows = read_json_or_jsonl(path)
        result["files"][path.name] = {
            "rows": len(rows),
            "keys": sample_keys(rows),
            "sample": rows[:2],
        }
    result["category_mapping"] = {
        "simple": "single-skill call with exact arguments",
        "multiple": "multi-skill sequence or multiple independent calls",
        "irrelevance": "no-tool or irrelevant-tool rejection",
        "multi_turn_miss_param": "missing argument / ask clarification",
        "multi_turn_miss_func": "missing skill / unsupported task abstention",
    }
    result["takeaways"] = [
        "BFCL-style categories should be adopted directly as SkillBench-Hard slices.",
        "Irrelevance and missing parameter cases are stronger than generic no-tool chat.",
    ]
    return result


def analyze_api_bank() -> dict[str, Any]:
    base = REF_DIR / "api_bank"
    result: dict[str, Any] = {"files": {}}
    apis_path = base / "all_apis.csv"
    if apis_path.exists():
        with apis_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        result["files"]["all_apis.csv"] = {
            "rows": len(rows),
            "columns": reader.fieldnames or [],
            "sample": rows[:3],
        }

    for path in sorted(base.glob("*.jsonl")):
        rows = read_json_or_jsonl(path)
        result["files"][path.name] = {
            "rows": len(rows),
            "keys": sample_keys(rows),
            "sample": rows[:2],
        }

    for path in sorted(base.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        result["files"][path.name] = {
            "chars": len(text),
            "preview": text[:500],
        }

    result["takeaways"] = [
        "API-Bank's level-1/2/3 split maps cleanly to single skill, retrieve+call, and plan+call.",
        "Dialogues include API call traces, useful for expected skill sequence and argument checks.",
    ]
    return result


def analyze_mteb_toolbench() -> dict[str, Any]:
    base = REF_DIR / "mteb_toolbench"
    result: dict[str, Any] = {"files": {}}
    for path in sorted(base.glob("*.parquet")):
        df = pd.read_parquet(path)
        result["files"][path.name] = {
            "rows": int(len(df)),
            "columns": list(df.columns),
            "sample": df.head(3).to_dict(orient="records"),
        }
    result["takeaways"] = [
        "Useful as a lightweight retrieval reference: query, corpus/tool documents, and qrels.",
        "Can guide skill_library description style and query-tool relevance labeling.",
    ]
    return result


def build_recommendation(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": "Keep current 120-task SkillBench-Mini as SkillBench-Dev seed, then expand to 240 Dev / 120 Hard / 80 Hidden.",
        "why_not_replace": [
            "The current 120 tasks preserve experiment continuity and already expose baseline-to-enhanced progress.",
            "Replacing them would destroy comparability with existing Full/BM25/Embedding/Enhanced V2 results.",
        ],
        "why_expand": [
            "External benchmarks emphasize missing parameters, irrelevance/no-tool, multi-call planning, and argument correctness.",
            "The current held-out set is useful but still partly template-like and too small for final claims.",
        ],
        "recommended_splits": {
            "SkillBench-Dev": {
                "size": 240,
                "source": "Current 120 tasks + 120 new development tasks.",
                "use": "Prompt/rule development and ablation debugging.",
                "distribution": {
                    "single_skill": 100,
                    "multi_skill": 70,
                    "no_tool": 40,
                    "missing_info_or_unsupported": 30,
                },
            },
            "SkillBench-Hard": {
                "size": 120,
                "source": "Fresh tasks adapted from external benchmark categories, not copied.",
                "use": "Main reported benchmark.",
                "distribution": {
                    "single_skill_minimal_pair": 30,
                    "argument_heavy_single_skill": 25,
                    "implicit_multi_skill": 30,
                    "hard_no_tool_irrelevance": 20,
                    "missing_info_or_unsupported": 15,
                },
            },
            "SkillBench-Hidden": {
                "size": 80,
                "source": "Final frozen test set written after method design.",
                "use": "One-shot final generalization check.",
                "distribution": {
                    "single_skill": 25,
                    "multi_skill": 25,
                    "no_tool": 15,
                    "missing_info_or_unsupported": 15,
                },
            },
        },
    }


def write_markdown(analysis: dict[str, Any]) -> None:
    rec = analysis["recommendation"]
    lines = [
        "# External Reference Benchmark Analysis",
        "",
        "This note summarizes small reference files downloaded under `data/external_references/` and proposes the next SkillBench split design.",
        "",
        "## Downloaded References",
        "",
    ]
    for source, payload in analysis["sources"].items():
        lines.append(f"### {source}")
        for file_name, meta in payload.get("files", {}).items():
            rows = meta.get("rows", meta.get("items", meta.get("chars", "")))
            cols = ", ".join(meta.get("columns", meta.get("keys", []))[:8])
            detail = f" rows/items/chars={rows}" if rows != "" else ""
            lines.append(f"- `{file_name}`:{detail}" + (f"; columns/keys: {cols}" if cols else ""))
        for item in payload.get("takeaways", []):
            lines.append(f"- Takeaway: {item}")
        lines.append("")

    lines.extend(
        [
            "## Recommendation",
            "",
            f"**Decision:** {rec['decision']}",
            "",
            "Do **not** replace the current benchmark. Rename/freeze it as the Dev seed and expand around it.",
            "",
            "### Why Keep Current Data",
        ]
    )
    lines.extend(f"- {x}" for x in rec["why_not_replace"])
    lines.extend(["", "### Why Expand"])
    lines.extend(f"- {x}" for x in rec["why_expand"])
    lines.extend(["", "## Proposed Splits", ""])

    for split, spec in rec["recommended_splits"].items():
        lines.append(f"### {split} ({spec['size']} tasks)")
        lines.append(f"- Source: {spec['source']}")
        lines.append(f"- Use: {spec['use']}")
        for k, v in spec["distribution"].items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    lines.extend(
        [
            "## Design Principles for New Tasks",
            "",
            "- Use external benchmark categories, but rewrite every task for the local 40-skill library.",
            "- Add `expected_checks` to every tool task: arguments, observations, final answer, and faithfulness.",
            "- Include minimal pairs where surface wording is similar but gold skills differ.",
            "- Include irrelevance and missing-argument cases where the correct behavior is `NONE` or clarification.",
            "- Avoid optimizing the agent on Hard/Hidden; use Dev only for rule and prompt iteration.",
        ]
    )

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    analysis = {
        "sources": {
            "MetaTool": analyze_metatool(),
            "BFCL": analyze_bfcl(),
            "API-Bank": analyze_api_bank(),
            "MTEB ToolBench retrieval": analyze_mteb_toolbench(),
        }
    }
    analysis["recommendation"] = build_recommendation(analysis)
    OUT_JSON.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(analysis)
    print(f"Saved JSON analysis: {OUT_JSON}")
    print(f"Saved Markdown analysis: {OUT_MD}")


if __name__ == "__main__":
    main()
