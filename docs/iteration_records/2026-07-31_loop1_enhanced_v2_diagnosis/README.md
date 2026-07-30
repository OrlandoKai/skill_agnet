# Loop 1: EnhancedSkillAgentV2 Diagnosis

Date: 2026-07-31

## Goal

Run the existing `EnhancedSkillAgentV2` on the completed SkillBench V2 Dev and
Hard splits before making new agent changes. This establishes the first
post-benchmark baseline and identifies the agent bottlenecks to address.

## Agent Version

```powershell
--agent enhanced_v2
--retriever bm25
```

No agent code was changed in this loop. The point was to test the current agent
against the stricter Dev/Hard benchmarks and parameter-level evaluator.

## Commands

```powershell
.\.venv\Scripts\python.exe run.py --agent enhanced_v2 --retriever bm25 --benchmark data\skillbench_dev.json --max_tasks 240 --output results\run_v2loop1_enhanced_v2_bm25_dev240.jsonl
.\.venv\Scripts\python.exe run.py --agent enhanced_v2 --retriever bm25 --benchmark data\skillbench_hard.json --max_tasks 120 --output results\run_v2loop1_enhanced_v2_bm25_hard120.jsonl

.\.venv\Scripts\python.exe -m eval.evaluate --input results\run_v2loop1_enhanced_v2_bm25_dev240.jsonl
.\.venv\Scripts\python.exe -m eval.evaluate --input results\run_v2loop1_enhanced_v2_bm25_hard120.jsonl

.\.venv\Scripts\python.exe scripts\analyze_failures.py --input results\run_v2loop1_enhanced_v2_bm25_dev240.jsonl
.\.venv\Scripts\python.exe scripts\analyze_failures.py --input results\run_v2loop1_enhanced_v2_bm25_hard120.jsonl

.\.venv\Scripts\python.exe scripts\compare_runs.py --inputs results\run_v2loop1_enhanced_v2_bm25_dev240.jsonl results\run_v2loop1_enhanced_v2_bm25_hard120.jsonl --output results\compare_v2loop1_bm25_dev_hard.csv
```

## Metrics

| Split | Recall | Selection | Need-tool | No-tool | Abstain | Under-call | Strict Success | Parameter Strict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Dev 240 | 98.46% | 76.67% | 90.83% | 80.00% | 53.33% | 44.00% | 75.83% | 75.83% |
| Hard 120 | 94.44% | 49.17% | 81.67% | 66.67% | 33.33% | 100.00% | 47.50% | 46.67% |

## Failure Counts

Dev 240:

- `need_tool_false_negative`: 1
- `missing_info_overcall`: 10
- `unsupported_tool_overcall`: 5
- `step_retrieval_failure`: 4
- `skill_selection_failure`: 1
- `no_tool_overcall`: 6
- `multi_skill_under_call`: 29
- `observation_correctness_failure`: 2
- total failures: 58 / 240

Hard 120:

- `need_tool_false_negative`: 2
- `missing_info_overcall`: 10
- `unsupported_tool_overcall`: 5
- `step_retrieval_failure`: 6
- `skill_selection_failure`: 1
- `no_tool_overcall`: 5
- `multi_skill_under_call`: 32
- `execution_failure`: 1
- `observation_correctness_failure`: 1
- `final_faithfulness_failure`: 1
- total failures: 64 / 120

## Diagnosis

Hard 120 shows a large generalization gap:

- strict success drops from 75.83% on Dev to 47.50% on Hard;
- parameter strict success drops from 75.83% to 46.67%;
- multi-skill under-call becomes the dominant error, reaching 100.00%;
- abstention is weak, especially for `missing_info` and `unsupported_tool`;
- retrieval is no longer trivial but is not the only bottleneck.

Representative failures:

- `hard_106`: "Convert the earlier value to kilograms." called
  `unit_converter`, but should ask for the missing value/unit.
- `hard_116`: "Buy a train ticket using my account." called a local text skill,
  but should refuse unsupported external side effects.
- `hard_051`: "convert 750 g to kg and state the converted value briefly"
  called only `unit_converter`, missing `summarizer`.
- `hard_053`: "Keep 5 to 15 ... and organize ... as a table" chose only
  `table_formatter`, missing `range_filter`.
- `hard_038`: Python execution selected the right skill but passed wrapper text
  into the executor, causing a syntax error.

## Literature Direction

The diagnosis matches patterns emphasized by tool-learning and function-calling
benchmarks:

- BFCL separates relevance / irrelevance and tests whether a model can avoid
  calling an irrelevant function.
- BFCL V3 emphasizes multi-step function calling and stateful workflows.
- ToolBench uses tool retrieval and multi-tool trajectories, rather than only
  single isolated calls.
- StableToolBench emphasizes stable evaluation where tool execution and final
  answer quality are not conflated.

These signals motivated the V3 changes: rule-first abstention, implicit
multi-step decomposition, previous-output handling, and contract-trigger hints.

## Next Version

Enhanced V3 should:

- detect `missing_info` and `unsupported_tool` before retrieval;
- split implicit two-step tasks, not only explicit `first ... then ...`;
- force dependent second steps to consume `$PREVIOUS_OUTPUT`;
- repair Python code input extraction;
- use `data/skill_library_v2.json` as agent-facing contract hints.
