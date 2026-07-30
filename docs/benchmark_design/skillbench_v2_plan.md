# SkillBench V2 Dataset Plan

## Decision

Keep the existing 120-task dataset as the seed of `SkillBench-Dev`, and build a
larger three-split benchmark:

- `SkillBench-Dev`: 240 tasks
- `SkillBench-Hard`: 120 tasks
- `SkillBench-Hidden`: 80 tasks

Do not replace the current dataset. The current 120 tasks preserve the
historical Full/BM25/Embedding/Enhanced V2 comparisons and are useful for
development and ablation debugging.

## Why This Is Better Than Replacing the Dataset

- Existing 120-task results remain comparable.
- External benchmark categories can be added without losing previous evidence.
- The project can clearly separate development, main evaluation, and one-shot
  hidden testing.
- It reduces the risk that Enhanced V2 is only optimized for one visible test
  file.

## External References Used

The plan is based on small downloaded samples from:

- MetaTool: tool-use awareness, similar-tool choice, multi-tool queries.
- BFCL: simple calls, multiple calls, irrelevance, missing function, missing
  parameter.
- API-Bank: level-1 single call, level-2 retrieve+call, level-3 planning.
- MTEB ToolBench: query-to-tool retrieval corpus and qrels format.

See `docs/benchmark_design/external_reference_analysis.md` for parsed counts and
schema details.

## Proposed Files

```text
data/
  skillbench_dev.json
  skillbench_hard.json
  skillbench_hidden.json
  skillbench_mini.json          # keep for backward compatibility
  skillbench_heldout.json       # keep as first held-out prototype
```

`skillbench_dev.json` should include the current 120 tasks plus 120 new
development tasks. `skillbench_hard.json` and `skillbench_hidden.json` should be
freshly written and frozen once created.

## Split Design

### SkillBench-Dev: 240 Tasks

Purpose: development, prompt iteration, rule debugging, ablation.

Suggested distribution:

- 100 single-skill tasks
- 70 multi-skill tasks
- 40 no-tool tasks
- 30 missing-info or unsupported-tool tasks

Composition:

- Keep current 120 tasks.
- Add 120 tasks adapted from public benchmark categories.
- It is acceptable to inspect failures on Dev and improve the agent.

### SkillBench-Hard: 120 Tasks

Purpose: main reported benchmark.

Suggested distribution:

- 30 single-skill minimal-pair tasks
- 25 argument-heavy single-skill tasks
- 30 implicit multi-skill tasks
- 20 hard no-tool / irrelevance tasks
- 15 missing-info or unsupported-tool tasks

Rules:

- Do not copy public benchmark samples directly.
- Avoid obvious templates such as `first ... then ...`.
- Every tool task should include `expected_checks`.
- No-tool tasks should include distracting words like `calculate`, `summarize`,
  `translate`, `extract`, or `format`, while still requiring no tool.

### SkillBench-Hidden: 80 Tasks

Purpose: final one-shot generalization check.

Suggested distribution:

- 25 single-skill tasks
- 25 multi-skill tasks
- 15 no-tool tasks
- 15 missing-info or unsupported-tool tasks

Rules:

- Do not use Hidden for prompt or rule development.
- Run it only after Dev and Hard results are stable.
- Keep Hidden examples visually and lexically different from Dev/Hard.

## Required Schema

Each task should keep the current fields:

```json
{
  "task_id": "hard_001",
  "instruction": "...",
  "gold_skills": ["..."],
  "expected_answer": "...",
  "task_type": "single_skill | multi_skill | no_tool | missing_info | unsupported_tool",
  "notes": "..."
}
```

For tool tasks, add strict checks:

```json
{
  "expected_checks": {
    "arguments": [
      {
        "skill": "percentage_calculator",
        "contains": ["30", "120"],
        "not_contains": ["30% of 30"]
      }
    ],
    "observations": [
      {
        "skill": "percentage_calculator",
        "contains": ["25"]
      }
    ],
    "final_answer": {
      "contains": ["25"],
      "not_contains": ["30"]
    },
    "faithfulness": true
  }
}
```

For missing-info tasks, use:

```json
{
  "task_type": "missing_info",
  "gold_skills": [],
  "expected_answer": "ask for the missing value/unit/list/context",
  "expected_checks": {
    "final_answer": {
      "contains": ["missing", "need", "please provide"],
      "not_contains": ["Result", "Converted", "Summary"]
    },
    "faithfulness": true
  }
}
```

## Task Category Mapping

| Public benchmark idea | SkillBench V2 category | Example local target |
|---|---|---|
| MetaTool tool-use awareness | no-tool / need-tool | decide whether any skill is needed |
| MetaTool multi-tool query | implicit multi-skill | sequence planning without explicit `then` |
| BFCL irrelevance | hard no-tool | reject irrelevant retrieved skills |
| BFCL missing parameter | missing_info | ask for missing unit/value/list |
| BFCL missing function | unsupported_tool | say no registered skill can do it |
| API-Bank level-1 | single_skill | one skill with complete input |
| API-Bank level-2 | retrieve+call | select among similar skills |
| API-Bank level-3 | plan+call | multi-skill task with dependencies |
| MTEB ToolBench qrels | retrieval labels | query-to-skill-library relevance |

## Priority Task Families

### 1. Minimal Pairs

Same surface wording, different gold behavior.

- "What does calculate mean in tool agents?" -> no tool
- "Calculate 18 * 7." -> `calculator`
- "What percentage is 18 of 72?" -> `percentage_calculator`
- "Find the ratio of 18 to 72." -> `ratio_calculator`

### 2. Missing Arguments

- "Convert this value to meters." -> no skill, ask for value and source unit
- "Sort the list I mentioned earlier." -> no skill, ask for list
- "Extract the dates from the document." -> no skill, ask for document text

### 3. Implicit Multi-Skill

- "Turn this meeting note into action items and present them as a table."
  -> `todo_extractor`, `table_formatter`
- "Give this paragraph a concise headline and list the core terms in it."
  -> `title_generator`, `keyword_extractor`
- "Make the complaint polite and check whether it remains negative."
  -> `tone_converter`, `sentiment_analyzer`

### 4. Argument-Heavy Skill Calls

- Percentage, unit conversion, equation solving, regex extraction, CSV
  summarization, JSON validation.
- These tasks must check argument correctness separately from skill selection.

### 5. Observation Faithfulness

- Some skills should intentionally return `Unsupported` or an error-like output.
- The final answer should report the failure instead of hallucinating a normal
  answer.

## Implementation Steps

1. Copy current `data/skillbench_mini.json` to `data/skillbench_dev.json`.
2. Append 120 new Dev tasks with `dev_121` to `dev_240` IDs.
3. Create `data/skillbench_hard.json` with 120 fresh tasks.
4. Create `data/skillbench_hidden.json` with 80 final frozen tasks.
5. Update `scripts/inspect_benchmark.py` to support the new task types:
   `missing_info` and `unsupported_tool`.
6. Update evaluation so missing-info / unsupported-tool tasks are judged as
   correct only if no skill is called and the final answer asks for clarification
   or reports unsupported capability.
7. Run Dev frequently; run Hard only for method selection; run Hidden only once
   for final reporting.

## Recommendation for the Paper/Report

Describe the dataset as:

> SkillBench V2 is a diagnostic benchmark adapted from established tool-use
> evaluation taxonomies. It tests skill retrieval, skill selection, tool-use
> awareness, multi-skill planning, argument correctness, observation correctness,
> and final-answer faithfulness.

This framing is stronger than presenting it as a purely self-written dataset.
