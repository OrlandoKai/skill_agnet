# Loop 4: EnhancedSkillAgentV5

Date: 2026-07-31

## Goal

Enhanced V4 solved most high-level agent-control failures on Hard, but several
remaining cases were still caused by similar-skill ambiguity and fragile input
cleanup.

Enhanced V5 is the third concrete agent modification after the V2 diagnosis. It
focuses on small but targeted fixes rather than changing the whole pipeline.

## Changes

Added `agents/enhanced_agent_v5.py` and registered:

```powershell
--agent enhanced_v5
```

Main changes:

- Force translation direction:
  - `translate ... into Chinese` -> `translator_en_zh`
  - `translate ... into English` -> `translator_zh_en`
- Add plural entity triggers:
  - `people`, `organizations`, `locations` -> `entity_extractor`
- Add implicit decomposition for:
  - `convert ... into a checklist`
  - `turn ... into a checklist`
- Prioritize `keyword_extractor` when the second step says extract keywords
  from a citation.
- Keep `outline_generator` as the first step when the request asks for an
  outline and then a checklist.
- Clean CSV inputs so wrapper text such as "The request is easy to confuse..."
  does not become a fake CSV row.

## Commands

```powershell
.\.venv\Scripts\python.exe run.py --agent enhanced_v5 --retriever bm25 --benchmark data\skillbench_dev.json --max_tasks 240 --output results\run_v2loop4_enhanced_v5_bm25_dev240.jsonl
.\.venv\Scripts\python.exe run.py --agent enhanced_v5 --retriever bm25 --benchmark data\skillbench_hard.json --max_tasks 120 --output results\run_v2loop4_enhanced_v5_bm25_hard120.jsonl

.\.venv\Scripts\python.exe -m eval.evaluate --input results\run_v2loop4_enhanced_v5_bm25_dev240.jsonl
.\.venv\Scripts\python.exe -m eval.evaluate --input results\run_v2loop4_enhanced_v5_bm25_hard120.jsonl

.\.venv\Scripts\python.exe scripts\analyze_failures.py --input results\run_v2loop4_enhanced_v5_bm25_dev240.jsonl
.\.venv\Scripts\python.exe scripts\analyze_failures.py --input results\run_v2loop4_enhanced_v5_bm25_hard120.jsonl

.\.venv\Scripts\python.exe scripts\compare_runs.py --inputs results\run_v2loop1_enhanced_v2_bm25_dev240.jsonl results\run_v2loop2_enhanced_v3_bm25_dev240.jsonl results\run_v2loop3_enhanced_v4_bm25_dev240.jsonl results\run_v2loop4_enhanced_v5_bm25_dev240.jsonl results\run_v2loop1_enhanced_v2_bm25_hard120.jsonl results\run_v2loop2_enhanced_v3_bm25_hard120.jsonl results\run_v2loop3_enhanced_v4_bm25_hard120.jsonl results\run_v2loop4_enhanced_v5_bm25_hard120.jsonl --output results\compare_v2_v3_v4_v5_bm25_dev_hard.csv
```

## Metrics

| Split | Agent | Recall | Selection | Need-tool | Abstain | Under-call | Strict Success | Parameter Strict |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Dev 240 | Enhanced V2 | 98.46% | 76.67% | 90.83% | 53.33% | 44.00% | 75.83% | 75.83% |
| Dev 240 | Enhanced V3 | 98.72% | 85.42% | 96.25% | 84.44% | 21.33% | 84.58% | 77.08% |
| Dev 240 | Enhanced V4 | 99.23% | 90.83% | 96.67% | 84.44% | 10.67% | 90.00% | 80.83% |
| Dev 240 | Enhanced V5 | 99.23% | 90.83% | 96.67% | 84.44% | 10.67% | 90.00% | 81.25% |
| Hard 120 | Enhanced V2 | 94.44% | 49.17% | 81.67% | 33.33% | 100.00% | 47.50% | 46.67% |
| Hard 120 | Enhanced V3 | 91.11% | 81.67% | 93.33% | 100.00% | 37.50% | 80.00% | 64.17% |
| Hard 120 | Enhanced V4 | 100.00% | 96.67% | 100.00% | 100.00% | 5.00% | 95.00% | 67.50% |
| Hard 120 | Enhanced V5 | 100.00% | 98.33% | 100.00% | 100.00% | 2.50% | 96.67% | 69.17% |

## Failure Counts

Dev 240 V5:

- `need_tool_false_negative`: 1
- `missing_info_overcall`: 5
- `unsupported_tool_overcall`: 1
- `no_tool_overcall`: 1
- `step_retrieval_failure`: 1
- `skill_selection_failure`: 6
- `multi_skill_under_call`: 7
- `argument_construction_failure`: 20
- `observation_correctness_failure`: 3
- total failures: 45 / 240

Hard 120 V5:

- `need_tool_false_negative`: 0
- `missing_info_overcall`: 0
- `unsupported_tool_overcall`: 0
- `no_tool_overcall`: 0
- `step_retrieval_failure`: 0
- `skill_selection_failure`: 1
- `multi_skill_under_call`: 1
- `argument_construction_failure`: 31
- `observation_correctness_failure`: 2
- `final_faithfulness_failure`: 2
- total failures: 37 / 120

## Interpretation

V5 improves the remaining Hard control metrics:

- skill selection: 96.67% -> 98.33%
- exact sequence: 96.67% -> 98.33%
- under-call: 5.00% -> 2.50%
- strict success: 95.00% -> 96.67%
- parameter strict success: 67.50% -> 69.17%

The improvement is real but smaller than V3 and V4. This is expected: the
remaining failures are no longer mostly caused by the agent choosing the wrong
skill. They are mostly parameter-level and observation-level failures.

The main remaining bottleneck is:

```text
correct skill sequence != correct tool call
```

The agent often selects the right skill, but the executed input or the rule
skill output does not satisfy the stricter `expected_checks`.

## Literature Link

This matches the evaluation lessons from:

- BFCL V2/V3: function calling evaluation should test relevance, execution, and
  multi-turn/tool-call correctness instead of only whether a tool name appears.
- ToolBench and StableToolBench: stable tool evaluation should separate tool
  selection, tool execution, and final response correctness.

## Next Iteration

The next work should not be another small rule patch. It should move to
parameter-level contracts:

- add explicit argument schemas/checkers for high-risk skills;
- record parsed arguments before execution;
- evaluate argument correctness independently from final answer;
- improve skill outputs so observations are machine-checkable;
- consider a small contract-aware argument builder instead of free-form text
  inputs for every skill.
