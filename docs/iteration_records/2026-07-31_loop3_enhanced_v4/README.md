# Loop 3: EnhancedSkillAgentV4

Date: 2026-07-31

## Goal

Enhanced V3 fixed most abstention and implicit multi-step failures, but introduced false negatives because the rule gate treated phrases such as "without using a numbered plan" as "do not use tools".

Enhanced V4 narrows abstention rules and strengthens similar-skill selection.

## Changes

Added `agents/enhanced_agent_v4.py` and registered:

```powershell
--agent enhanced_v4
```

Main changes:

- Strip meta prefixes such as "without using a numbered plan" before no-tool detection.
- Require explicit "do not / without running tool / not asking you to" patterns for no-tool gating.
- Avoid treating composed tasks such as "draft ... and make it formal" as missing-info.
- Add priority hints for:
  - `equation_solver` over `calculator`;
  - `csv_summarizer` over `summarizer` / `table_formatter`;
  - `citation_formatter`;
  - `paper_qa`;
  - `outline_generator`;
  - `title_generator`;
  - `question_generator`;
  - `checklist_generator`;
  - `range_filter` for "keep X to Y from ..." expressions.
- Fix `range_filter` so "Keep 5 to 15 from 3, 5, 8, 15, 22" returns `5, 8, 15`.

## Commands

```powershell
.\.venv\Scripts\python.exe run.py --agent enhanced_v4 --retriever bm25 --benchmark data\skillbench_dev.json --max_tasks 240 --output results\run_v2loop3_enhanced_v4_bm25_dev240.jsonl
.\.venv\Scripts\python.exe run.py --agent enhanced_v4 --retriever bm25 --benchmark data\skillbench_hard.json --max_tasks 120 --output results\run_v2loop3_enhanced_v4_bm25_hard120.jsonl

.\.venv\Scripts\python.exe -m eval.evaluate --input results\run_v2loop3_enhanced_v4_bm25_dev240.jsonl
.\.venv\Scripts\python.exe -m eval.evaluate --input results\run_v2loop3_enhanced_v4_bm25_hard120.jsonl

.\.venv\Scripts\python.exe scripts\analyze_failures.py --input results\run_v2loop3_enhanced_v4_bm25_dev240.jsonl
.\.venv\Scripts\python.exe scripts\analyze_failures.py --input results\run_v2loop3_enhanced_v4_bm25_hard120.jsonl

.\.venv\Scripts\python.exe scripts\compare_runs.py --inputs results\run_v2loop1_enhanced_v2_bm25_dev240.jsonl results\run_v2loop2_enhanced_v3_bm25_dev240.jsonl results\run_v2loop3_enhanced_v4_bm25_dev240.jsonl results\run_v2loop1_enhanced_v2_bm25_hard120.jsonl results\run_v2loop2_enhanced_v3_bm25_hard120.jsonl results\run_v2loop3_enhanced_v4_bm25_hard120.jsonl --output results\compare_v2_v3_v4_bm25_dev_hard.csv
```

## Metrics

| Split | Agent | Recall | Selection | Need-tool | Abstain | Under-call | Strict Success | Parameter Strict |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Dev 240 | Enhanced V2 | 98.46% | 76.67% | 90.83% | 53.33% | 44.00% | 75.83% | 75.83% |
| Dev 240 | Enhanced V3 | 98.72% | 85.42% | 96.25% | 84.44% | 21.33% | 84.58% | 77.08% |
| Dev 240 | Enhanced V4 | 99.23% | 90.83% | 96.67% | 84.44% | 10.67% | 90.00% | 80.83% |
| Hard 120 | Enhanced V2 | 94.44% | 49.17% | 81.67% | 33.33% | 100.00% | 47.50% | 46.67% |
| Hard 120 | Enhanced V3 | 91.11% | 81.67% | 93.33% | 100.00% | 37.50% | 80.00% | 64.17% |
| Hard 120 | Enhanced V4 | 100.00% | 96.67% | 100.00% | 100.00% | 5.00% | 95.00% | 67.50% |

## Failure Counts

Dev 240 V4:

- `need_tool_false_negative`: 1
- `missing_info_overcall`: 5
- `unsupported_tool_overcall`: 1
- `no_tool_overcall`: 1
- `skill_selection_failure`: 6
- `multi_skill_under_call`: 7
- `argument_construction_failure`: 21
- total failures: 46 / 240

Hard 120 V4:

- `need_tool_false_negative`: 0
- `missing_info_overcall`: 0
- `unsupported_tool_overcall`: 0
- `no_tool_overcall`: 0
- `skill_selection_failure`: 2
- `multi_skill_under_call`: 2
- `argument_construction_failure`: 31
- total failures: 39 / 120

## Interpretation

V4 mostly solves the agent-control problem on Hard:

- Need-tool, no-tool, and abstention are all 100%.
- Skill recall and step retrieval recall are both 100%.
- Skill sequence accuracy reaches 96.67%.
- Strict success reaches 95.00%.

The remaining gap is parameter-level:

- Hard `argument_acc` is 61.11%;
- Hard `parameter_strict_success` is 67.50%;
- many remaining failures are cases where the selected skill sequence is correct, but the input/observation check is stricter than the current rule output.

Remaining concrete failures:

- `translator_en_zh` vs `translator_zh_en` when the instruction says "Translate into Chinese: ...";
- `entity_extractor` vs `keyword_extractor` for plural wording such as "people, organizations, and locations";
- `outline_generator -> checklist_generator` still under-calls in one case;
- `citation_formatter -> keyword_extractor` repeats `citation_formatter` in one case.

## Next Iteration

The next improvement should be less about high-level agent control and more about contract-level arguments:

- add explicit translation-direction priority rules;
- add plural entity trigger rules;
- move `extract keywords` above citation cues for second-step planning;
- make `outline` outrank `checklist` in first-step planning but keep `checklist` for conversion follow-up;
- improve `csv_summarizer` input cleanup so wrapper text does not become a CSV field.
