# Loop 2: EnhancedSkillAgentV3

Date: 2026-07-31

## Goal

After the first SkillBench V2 run, Enhanced V2 exposed three concrete bottlenecks:

- abstention failed for `missing_info` and `unsupported_tool`;
- implicit multi-skill tasks were often treated as single-tool tasks;
- second-step inputs were not reliably grounded in previous observations.

Enhanced V3 keeps Enhanced V2 intact and adds a separate version focused on contract-aware abstention and implicit two-step planning.

## Literature Signals Used

- BFCL evaluates whether a model should withhold function calls when no provided function is relevant, and separates relevance / irrelevance behavior. Source: https://gorilla.cs.berkeley.edu/blogs/12_bfcl_v2_live.html
- BFCL V3 emphasizes multi-turn and multi-step function calling evaluation. Source: https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html
- ToolBench uses single-tool and multi-tool scenarios, API retrieval, and decision-tree style annotations for complex tool-use trajectories. Source: https://github.com/OpenBMB/ToolBench
- StableToolBench argues for stable, reproducible tool-learning evaluation with simulated or cached tool behavior. Source: https://github.com/THUNLP-MT/StableToolBench

These sources support treating abstention, multi-step function planning, argument construction, and stable observation-grounded evaluation as separate subproblems.

## Changes

Added `agents/enhanced_agent_v3.py` and registered it in `run.py` as:

```powershell
--agent enhanced_v3
```

Main changes:

- Rule-first `missing_info` detection for references such as "earlier value", "that result", "the passage", and "the JSON I meant".
- Rule-first `unsupported_tool` detection for external side effects such as buying tickets, sending messages, GitHub release creation, live web search, uploads, reservations, or opening apps.
- Stronger conceptual no-tool detection for prompts that explicitly say not to compute, translate, extract, validate, or call tools.
- Implicit multi-step detection for natural compositions using `and`, e.g. "convert ... and state briefly", "extract ... and put in a table", "draft ... and make formal".
- V3 subtask normalization so dependent second steps usually consume `$PREVIOUS_OUTPUT`.
- Small input-builder repair for safe Python code extraction.
- Contract trigger hints from `data/skill_library_v2.json` are used as extra hints, while the original retriever remains unchanged.

## Commands

```powershell
.\.venv\Scripts\python.exe run.py --agent enhanced_v3 --retriever bm25 --benchmark data\skillbench_dev.json --max_tasks 240 --output results\run_v2loop2_enhanced_v3_bm25_dev240.jsonl
.\.venv\Scripts\python.exe run.py --agent enhanced_v3 --retriever bm25 --benchmark data\skillbench_hard.json --max_tasks 120 --output results\run_v2loop2_enhanced_v3_bm25_hard120.jsonl

.\.venv\Scripts\python.exe -m eval.evaluate --input results\run_v2loop2_enhanced_v3_bm25_dev240.jsonl
.\.venv\Scripts\python.exe -m eval.evaluate --input results\run_v2loop2_enhanced_v3_bm25_hard120.jsonl

.\.venv\Scripts\python.exe scripts\analyze_failures.py --input results\run_v2loop2_enhanced_v3_bm25_dev240.jsonl
.\.venv\Scripts\python.exe scripts\analyze_failures.py --input results\run_v2loop2_enhanced_v3_bm25_hard120.jsonl

.\.venv\Scripts\python.exe scripts\compare_runs.py --inputs results\run_v2loop1_enhanced_v2_bm25_dev240.jsonl results\run_v2loop2_enhanced_v3_bm25_dev240.jsonl results\run_v2loop1_enhanced_v2_bm25_hard120.jsonl results\run_v2loop2_enhanced_v3_bm25_hard120.jsonl --output results\compare_v2loop2_v2_vs_v3_bm25.csv
```

## Metrics

| Split | Agent | Recall | Selection | Need-tool | No-tool | Abstain | Under-call | Strict Success | Parameter Strict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Dev 240 | Enhanced V2 | 98.46% | 76.67% | 90.83% | 80.00% | 53.33% | 44.00% | 75.83% | 75.83% |
| Dev 240 | Enhanced V3 | 98.72% | 85.42% | 96.25% | 96.67% | 84.44% | 21.33% | 84.58% | 77.08% |
| Hard 120 | Enhanced V2 | 94.44% | 49.17% | 81.67% | 66.67% | 33.33% | 100.00% | 47.50% | 46.67% |
| Hard 120 | Enhanced V3 | 91.11% | 81.67% | 93.33% | 100.00% | 100.00% | 37.50% | 80.00% | 64.17% |

## Failure Counts

Dev 240 V3:

- `need_tool_false_negative`: 2
- `missing_info_overcall`: 5
- `unsupported_tool_overcall`: 1
- `no_tool_overcall`: 1
- `multi_skill_under_call`: 14
- `skill_selection_failure`: 11
- `argument_construction_failure`: 17
- total failures: 55 / 240

Hard 120 V3:

- `need_tool_false_negative`: 8
- `missing_info_overcall`: 0
- `unsupported_tool_overcall`: 0
- `no_tool_overcall`: 0
- `multi_skill_under_call`: 7
- `skill_selection_failure`: 7
- `argument_construction_failure`: 19
- total failures: 43 / 120

## Interpretation

V3 successfully fixes the most severe V2 issue on Hard:

- abstention rises from 33.33% to 100%;
- no-tool rises from 66.67% to 100%;
- strict success rises from 47.50% to 80.00%;
- under-call drops from 100.00% to 37.50%.

The main regression is retrieval/selection coverage:

- Hard Recall drops from 94.44% to 91.11%;
- 8 tool tasks become false negatives because the rule gate is too broad;
- some similarity groups still fail, such as `equation_solver` vs `calculator`, `csv_summarizer` vs `summarizer`, and generation tasks such as `title_generator` / `question_generator`.

The parameter-level metrics show that V3 improves task-level behavior more than argument-level correctness. Hard `argument_acc` remains 54.44%, so the next iteration should focus on argument-slot extraction and stricter contract use.

## Next Iteration

Enhanced V4 should:

- make the abstention gate less aggressive by requiring missing-info cues plus no concrete payload;
- whitelist supported tasks such as "draft an email to Professor Lee about ..." so they are not treated as missing-info;
- prioritize specific skills over generic ones in similarity groups:
  - `equation_solver` over `calculator`;
  - `csv_summarizer` over `summarizer`;
  - `title_generator` over conceptual no-tool for "give ... a title";
  - `question_generator` over `topic_classifier` when generating questions;
- improve argument extraction for checked tasks rather than only selecting the right skill sequence.
