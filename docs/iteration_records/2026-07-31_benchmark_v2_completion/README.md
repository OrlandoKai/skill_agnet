# Benchmark V2 Completion Record

Date: 2026-07-31

## Scope

This record tracks the first completed benchmark-construction step for the
SkillBench V2 workstream.

The goal of this step was to move from the partial Dev trial batch to a complete
benchmark suite:

- SkillBench-Dev: 240 tasks
- SkillBench-Hard: 120 tasks
- SkillBench-Hidden: 80 tasks

The Agent implementation was not changed in this step.

## Files Added

- `scripts/build_skillbench_v2.py`
- `scripts/build_skill_contracts_v2.py`
- `scripts/inspect_skill_contracts.py`
- `data/skillbench_hard.json`
- `data/skillbench_hidden.json`
- `data/skillbench_hidden_answer_key.json`
- `data/skill_library_v2.json`
- `docs/iteration_records/2026-07-31_benchmark_v2_completion/README.md`

## Files Updated

- `data/skillbench_dev.json`
- `docs/benchmark_design/skill_contract_v2_plan.md`
- `skills/basic_tools.py`

## Benchmark Distribution

| Split | single_skill | multi_skill | no_tool | missing_info | unsupported_tool | total |
|---|---:|---:|---:|---:|---:|---:|
| Dev | 120 | 75 | 30 | 10 | 5 | 240 |
| Hard | 50 | 40 | 15 | 10 | 5 | 120 |
| Hidden | 30 | 25 | 15 | 7 | 3 | 80 |

All splits cover the current 40 registered skills.

## Design Notes

- `skillbench_mini.json` remains unchanged as the historical 120-task baseline.
- `skillbench_dev.json` preserves the original 120 seed tasks and the first
  `dev_121` to `dev_180` trial batch, then adds `dev_181` to `dev_240`.
- Hard and Hidden use `hard_001` to `hard_120` and `hidden_001` to `hidden_080`.
- Hidden is still stored in a runnable internal format for local experiments;
  `skillbench_hidden_answer_key.json` keeps the answer-key fields separated for
  future blind-test use.
- New tasks include `expected_checks` for argument, observation, and final-answer
  checks where applicable.

## Verification Commands

```powershell
.\.venv\Scripts\python.exe scripts\build_skillbench_v2.py
.\.venv\Scripts\python.exe scripts\inspect_benchmark.py --benchmark data\skillbench_dev.json --expected_single 120 --expected_multi 75 --expected_no_tool 30 --expected_missing_info 10 --expected_unsupported_tool 5 --require_expected_checks
.\.venv\Scripts\python.exe scripts\inspect_benchmark.py --benchmark data\skillbench_hard.json --expected_single 50 --expected_multi 40 --expected_no_tool 15 --expected_missing_info 10 --expected_unsupported_tool 5 --require_expected_checks
.\.venv\Scripts\python.exe scripts\inspect_benchmark.py --benchmark data\skillbench_hidden.json --expected_single 30 --expected_multi 25 --expected_no_tool 15 --expected_missing_info 7 --expected_unsupported_tool 3 --require_expected_checks
```

All three inspections passed on 2026-07-31.

## Skill Contract V2

This step also generated the first executable Skill Contract V2 file:

```text
data/skill_library_v2.json
```

The contract inspector checks:

- V2 contract names match `skill_registry.py`.
- V2 contract names match legacy `skill_library.json`.
- required contract fields are present.
- hard negative skills point to registered skills.
- every contract has input, retrieval, calling, examples, and benchmark support
  sections.

Verification command:

```powershell
.\.venv\Scripts\python.exe scripts\build_skill_contracts_v2.py
.\.venv\Scripts\python.exe scripts\inspect_skill_contracts.py
```

The inspection passed with 40 contracts:

```text
active: 39
active_placeholder: 1
```

## Rule Skill Fixes

The following high-risk rule skills were patched because they directly affect
argument-level and observation-level evaluation:

- `unit_converter`: added natural unit aliases and natural wording parsing.
- `percentage_calculator`: added `out of` and `rose/increased by X%` handling.
- `csv_summarizer`: extracts CSV blocks from natural-language wrappers.
- `language_detector`: returns `mixed Chinese-English` when both scripts appear.
- `table_formatter`: supports `key=value` pairs in addition to `key: value`.

Regression command:

```powershell
.\.venv\Scripts\python.exe scripts\test_skills.py
```

All 40 skills returned `[OK]`.

## Immediate Implication

The next step is the first complete experiment loop:

1. Run current Enhanced V2 on Dev and Hard.
2. Analyze failures by retrieval, need-tool, sequence, argument, observation,
   and final-answer faithfulness.
3. Use the literature notes and external references to design Agent V3.
4. Run the same experiment again and record the delta.
