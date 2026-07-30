# SkillBench V2 Manufacturing Protocol

## Goal

SkillBench V2 should not be presented as a purely hand-written toy dataset. It
should be a diagnostic benchmark for skill retrieval and skill calling, designed
from established tool-use benchmark taxonomies and rewritten for the local
40-skill library.

The benchmark should test the full chain:

```text
need-tool decision -> skill retrieval -> skill selection -> skill sequence planning
-> argument construction -> skill execution -> observation correctness
-> final-answer faithfulness
```

## Source Analysis

Downloaded references are stored in `data/external_references/`. The useful
signal is not the original task text itself, but the task taxonomy, annotation
style, and evaluation target.

### MetaTool

Downloaded files:

- `all_clean_data.csv`: 20,614 single-tool queries with columns `Query`, `Tool`.
- `multi_tool_query_golden.json`: 497 multi-tool queries with fields `query`,
  `tool`.
- `plugin_des.json`: 199 plugin descriptions.
- `plugin_info.json`: 390 plugin/tool metadata items.

Useful signal:

- Natural user queries can map to tools without explicitly naming the tool.
- Multi-tool queries are often expressed as a single compound intent, not a
  step-by-step instruction.
- Tool descriptions should contain both functional boundaries and likely user
  intents.

How to adapt:

- Use MetaTool-like phrasing for natural instructions.
- Convert tool names to local skill names.
- Use multi-tool examples to design implicit multi-skill tasks.
- Do not copy original MetaTool queries verbatim.

### BFCL

Downloaded files:

- `BFCL_v4_simple_python.json`: 400 simple function-calling samples.
- `BFCL_v4_multiple.json`: 200 multi-function or candidate-confusion samples.
- `BFCL_v4_irrelevance.json`: 240 cases where available functions are
  irrelevant.
- `BFCL_v4_multi_turn_miss_param.json`: 200 missing-parameter cases.
- `BFCL_v4_multi_turn_miss_func.json`: 200 missing-function cases.

Useful signal:

- `irrelevance`: the model must not call a wrong tool just because a function is
  available.
- `missing parameter`: the model should ask for missing information instead of
  fabricating arguments.
- `missing function`: the model should say no registered skill can solve the
  task.
- `multiple`: candidate functions may be semantically close; argument schemas
  decide the correct tool.

How to adapt:

- Add hard no-tool tasks with distracting tool keywords.
- Add missing-info tasks where the correct skill exists but required input is
  absent.
- Add unsupported-tool tasks where no local skill can solve the request.
- Add near-neighbor candidate sets where several local skills appear plausible.

### API-Bank

Downloaded files:

- `all_apis.csv`: 101 API definitions.
- Level-1 examples: direct API calls such as Calculator and Translate.
- Level-2 examples: retrieval/search followed by API call.
- Level-3 examples: planning-style tasks, e.g. meeting scheduling.

Useful signal:

- The Level-1/2/3 hierarchy maps cleanly to SkillBench:
  - Level 1: single skill with direct arguments.
  - Level 2: retrieve the right skill, then call it.
  - Level 3: plan multiple dependent calls.
- API traces provide explicit `api_name`, `param_dict`, and `result`, which is
  analogous to `called_skills`, `input`, and `observations`.

How to adapt:

- For every SkillBench task, store expected arguments and expected observations.
- For multi-skill tasks, write an explicit `gold_sequence`.
- Separate "tool retrieval success" from "tool call success".

### MTEB ToolBench Retrieval

Downloaded files:

- `ToolBench-queries.parquet`: 1,100 queries.
- `ToolBench-corpus.parquet`: 13,862 tool/API documents.
- `ToolBench-qrels.parquet`: 2,629 query-tool relevance labels.

Useful signal:

- Retrieval benchmark data is naturally represented as query, corpus/tool doc,
  and qrels.
- Tool documents often include category, required parameters, optional
  parameters, name, and description.

How to adapt:

- Enrich `skill_library.json` with clearer skill contracts over time.
- Add explicit retrieval labels in each task:
  - `gold_skills`
  - `hard_negative_skills`
  - `acceptable_retrieval_skills` if needed
- Evaluate retrieval separately from calling.

## Core Decision

Keep the current 120-task `skillbench_mini.json` as the seed of
`SkillBench-Dev`. Do not replace it.

Build:

- `SkillBench-Dev`: 240 tasks
- `SkillBench-Hard`: 120 tasks
- `SkillBench-Hidden`: 80 tasks

Rationale:

- Current 120-task results preserve continuity with baseline, enhanced, and
  Enhanced V2 experiments.
- The current 120-task set is already partially optimized by the agent.
- Hard and Hidden must be fresh, frozen, and less template-like.

## File Layout

```text
data/
  skillbench_dev.json
  skillbench_hard.json
  skillbench_hidden.json
  skillbench_mini.json          # existing compatibility file
  skillbench_heldout.json       # existing prototype held-out file
```

Recommended naming:

- Dev task IDs: `dev_001` to `dev_240`
- Hard task IDs: `hard_001` to `hard_120`
- Hidden task IDs: `hidden_001` to `hidden_080`

Do not reuse the same instruction text across splits.

## Schema

Use a richer schema while keeping backward-compatible fields.

```json
{
  "task_id": "hard_001",
  "instruction": "...",
  "gold_skills": ["..."],
  "gold_sequence": ["..."],
  "expected_answer": "...",
  "task_type": "single_skill | multi_skill | no_tool | missing_info | unsupported_tool",
  "difficulty": "easy | medium | hard",
  "benchmark_tags": [
    "minimal_pair",
    "argument_heavy",
    "irrelevance",
    "implicit_multi_skill"
  ],
  "source_inspiration": "BFCL_irrelevance | BFCL_missing_param | MetaTool_multi_tool | APIBank_level3 | ToolBench_qrels | original",
  "hard_negative_skills": ["..."],
  "notes": "...",
  "expected_checks": {
    "arguments": [
      {
        "skill": "...",
        "contains": ["..."],
        "not_contains": ["..."]
      }
    ],
    "observations": [
      {
        "skill": "...",
        "contains": ["..."],
        "not_contains": ["..."]
      }
    ],
    "final_answer": {
      "contains": ["..."],
      "not_contains": ["..."]
    },
    "faithfulness": true
  }
}
```

### Required Fields by Task Type

| Task type | gold_skills | gold_sequence | expected_checks.arguments | expected_checks.observations |
|---|---|---|---|---|
| single_skill | one skill | one skill | required | required |
| multi_skill | two or more | ordered list | required per step | required per step |
| no_tool | empty | empty | not needed | not needed |
| missing_info | empty | empty | not needed | not needed |
| unsupported_tool | empty | empty | not needed | not needed |

For `missing_info`, final answer should ask for the missing parameter.

For `unsupported_tool`, final answer should state that no registered skill can
perform the request.

## Split Construction

### SkillBench-Dev: 240 Tasks

Use:

- Development.
- Prompt and rule iteration.
- Ablation debugging.

Composition:

- Current 120 tasks become `dev_001` to `dev_120`.
- Add 120 new Dev tasks from the categories below.

Suggested distribution:

| Category | Count |
|---|---:|
| single_skill | 100 |
| multi_skill | 70 |
| no_tool | 40 |
| missing_info_or_unsupported | 30 |

Development tasks may be inspected repeatedly. It is acceptable to improve the
agent based on Dev failures.

### SkillBench-Hard: 120 Tasks

Use:

- Main reported benchmark.
- Model and method selection.

Suggested distribution:

| Category | Count |
|---|---:|
| single_skill_minimal_pair | 30 |
| argument_heavy_single_skill | 25 |
| implicit_multi_skill | 30 |
| hard_no_tool_irrelevance | 20 |
| missing_info_or_unsupported | 15 |

Hard should be frozen before major method iteration. If a failure is found, do
not immediately patch rules against the exact wording. Patch only general
capabilities and re-test on Dev first.

### SkillBench-Hidden: 80 Tasks

Use:

- Final one-shot generalization check.

Suggested distribution:

| Category | Count |
|---|---:|
| single_skill | 25 |
| multi_skill | 25 |
| no_tool | 15 |
| missing_info_or_unsupported | 15 |

Hidden should not be used for prompt/rule iteration. Run it after Dev and Hard
are stable.

## Task Taxonomy

### A. Tool-Use Awareness

Inspired by MetaTool and BFCL irrelevance.

Purpose:

- Test whether the agent should call any skill.

Subtypes:

- direct no-tool conceptual question
- hard no-tool with tool keywords
- irrelevant candidate skill
- no-tool because the user asks about a word rather than asks to execute it

Examples:

```json
{
  "instruction": "What does the word calculate mean in tool-using agents?",
  "gold_skills": [],
  "task_type": "no_tool",
  "benchmark_tags": ["no_tool", "keyword_distractor"],
  "hard_negative_skills": ["calculator"]
}
```

```json
{
  "instruction": "I am not asking you to summarize this. Explain why summarization can lose details.",
  "gold_skills": [],
  "task_type": "no_tool",
  "benchmark_tags": ["no_tool", "negated_tool_request"],
  "hard_negative_skills": ["summarizer"]
}
```

### B. Missing Information

Inspired by BFCL missing-parameter cases.

Purpose:

- Test whether the agent fabricates skill inputs.

Examples:

```json
{
  "instruction": "Convert this value to meters.",
  "gold_skills": [],
  "task_type": "missing_info",
  "benchmark_tags": ["missing_argument", "unit_conversion"],
  "hard_negative_skills": ["unit_converter"],
  "expected_answer": "ask for value and source unit",
  "expected_checks": {
    "final_answer": {
      "contains": ["value", "unit"],
      "not_contains": ["Converted", "Result"]
    },
    "faithfulness": true
  }
}
```

```json
{
  "instruction": "Extract the dates from the document.",
  "gold_skills": [],
  "task_type": "missing_info",
  "benchmark_tags": ["missing_input_text", "regex"],
  "hard_negative_skills": ["regex_extractor"]
}
```

### C. Unsupported Tool

Inspired by BFCL missing-function cases.

Purpose:

- Test whether the agent refuses tasks outside the local skill library.

Examples:

```json
{
  "instruction": "Book me a real flight from Beijing to Shanghai for tomorrow morning.",
  "gold_skills": [],
  "task_type": "unsupported_tool",
  "benchmark_tags": ["unsupported_tool", "real_world_action"],
  "hard_negative_skills": ["email_drafter", "todo_extractor"]
}
```

```json
{
  "instruction": "Open my browser and download the latest stock data.",
  "gold_skills": [],
  "task_type": "unsupported_tool",
  "benchmark_tags": ["unsupported_tool", "system_action"],
  "hard_negative_skills": ["python_executor"]
}
```

### D. Single-Skill Minimal Pairs

Inspired by BFCL candidate confusion and MetaTool single-tool queries.

Purpose:

- Test semantic distinction among near-neighbor skills.

Families:

| Skill family | Near-neighbor skills |
|---|---|
| numeric | calculator, percentage_calculator, ratio_calculator, equation_solver, statistics_calculator, number_sequence_analyzer |
| extraction | keyword_extractor, regex_extractor, entity_extractor, todo_extractor, meeting_notes_extractor |
| generation | summarizer, title_generator, outline_generator, question_generator, checklist_generator |
| rewriting | text_rewriter, grammar_corrector, tone_converter, email_drafter |
| classification | sentiment_analyzer, topic_classifier, intent_classifier, language_detector |
| formatting | table_formatter, json_validator, csv_summarizer, citation_formatter |

Minimal pair example:

```text
What percentage is 18 of 72?          -> percentage_calculator
Find the ratio of 18 to 72.           -> ratio_calculator
Calculate 18 divided by 72.           -> calculator
Compute the mean of 18 and 72.        -> statistics_calculator
```

### E. Argument-Heavy Single Skill

Inspired by BFCL executable argument checks and API-Bank `param_dict`.

Purpose:

- Test whether skill input is constructed correctly.

Priority skills:

- percentage_calculator
- unit_converter
- equation_solver
- statistics_calculator
- regex_extractor
- json_validator
- csv_summarizer
- date_difference_calculator
- table_formatter

Example:

```json
{
  "instruction": "In the sentence '30 students passed out of 120', report the pass percentage.",
  "gold_skills": ["percentage_calculator"],
  "gold_sequence": ["percentage_calculator"],
  "task_type": "single_skill",
  "benchmark_tags": ["argument_heavy", "percentage"],
  "hard_negative_skills": ["calculator", "ratio_calculator"],
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
      "contains": ["25"]
    },
    "faithfulness": true
  }
}
```

### F. Implicit Multi-Skill

Inspired by MetaTool multi-tool queries and API-Bank Level-3 planning.

Purpose:

- Test whether the agent decomposes a compound intent without explicit
  `first/then`.

Avoid:

- "first ..., then ..."
- "step 1 ..., step 2 ..."
- listing exact skill names

Prefer:

- one natural user goal requiring multiple transformations
- dependent outputs where step 2 should consume step 1
- no explicit delimiter

Examples:

```json
{
  "instruction": "Turn this meeting note into action items and present them as a table: Alice will update retrieval. Bob will check evaluation.",
  "gold_skills": ["todo_extractor", "table_formatter"],
  "gold_sequence": ["todo_extractor", "table_formatter"],
  "task_type": "multi_skill",
  "benchmark_tags": ["implicit_multi_skill", "dependent_steps"],
  "expected_checks": {
    "arguments": [
      {
        "skill": "todo_extractor",
        "contains": ["Alice", "Bob"]
      },
      {
        "skill": "table_formatter",
        "contains": ["Alice", "Bob"]
      }
    ],
    "observations": [
      {
        "skill": "todo_extractor",
        "contains": ["Alice", "Bob"]
      },
      {
        "skill": "table_formatter",
        "contains": ["|"]
      }
    ],
    "final_answer": {
      "contains": ["|", "Alice", "Bob"]
    },
    "faithfulness": true
  }
}
```

```json
{
  "instruction": "Give this paragraph a concise headline and list the key terms in that headline: Skill retrieval narrows tools before execution.",
  "gold_skills": ["title_generator", "keyword_extractor"],
  "gold_sequence": ["title_generator", "keyword_extractor"],
  "task_type": "multi_skill",
  "benchmark_tags": ["implicit_multi_skill", "previous_output_dependency"],
  "hard_negative_skills": ["summarizer"]
}
```

### G. Observation Faithfulness

Purpose:

- Test whether the final answer follows observations and does not hallucinate.

Design:

- Some tool outputs should include unsupported conversion or error-like strings.
- The correct final answer should report the failure.
- Some tool outputs should be structured; final answer should preserve them.

Example:

```json
{
  "instruction": "Convert 12 parsecs to kilograms.",
  "gold_skills": ["unit_converter"],
  "task_type": "single_skill",
  "benchmark_tags": ["execution_failure", "faithfulness"],
  "expected_checks": {
    "observations": [
      {
        "skill": "unit_converter",
        "contains": ["Unsupported"]
      }
    ],
    "final_answer": {
      "contains": ["Unsupported"],
      "not_contains": ["12 kg"]
    },
    "faithfulness": true
  }
}
```

## Per-Skill Coverage Plan

Each of the 40 skills should appear in:

- at least 3 Dev tasks
- at least 2 Hard tasks
- at least 1 Hidden task

Each skill should have:

- one direct single-skill task
- one near-neighbor confusion task
- one argument or input-construction task if applicable
- one multi-skill appearance for high-value skills

High-value multi-skill participants:

- summarizer
- keyword_extractor
- table_formatter
- title_generator
- sentiment_analyzer
- tone_converter
- todo_extractor
- meeting_notes_extractor
- calculator
- percentage_calculator
- regex_extractor
- entity_extractor

## Anti-Template Rules

To reduce template artifacts:

- Do not use `first/then` in Hard/Hidden except in at most 10% of multi-skill
  cases.
- Do not start every numeric task with "Calculate".
- Do not use the exact skill name in the instruction unless the task is an
  intent-classification or no-tool keyword-distractor case.
- Use varied verbs:
  - summarize: condense, brief, compress, capture the point
  - translate: render, put into English/Chinese, express in
  - extract: find, pull out, identify, list
  - classify: label, decide the category, recognize the intent
  - format: organize, present as, lay out
- Include negation:
  - "Do not translate; just identify the language."
  - "I do not need a summary; write questions."
- Include irrelevant context around the important parameters.

## Quality Control Checklist

Every task should pass these checks before entering Hard or Hidden:

1. The instruction can be solved by the declared gold skill sequence.
2. No other skill sequence is equally valid unless documented as acceptable.
3. Required arguments are present for tool tasks.
4. Missing-info tasks genuinely lack required arguments.
5. No-tool tasks do not require execution.
6. Expected observations match the actual rule-based skill behavior.
7. Final answer checks are not too loose.
8. The task is not copied from a public dataset.
9. The task is not a near-duplicate of Dev if it is in Hard/Hidden.
10. The task uses current 40 registered skills only.

## Generation Workflow

### Phase 1: Build Category Blueprints

Create a spreadsheet or JSONL file with columns:

```text
category, source_inspiration, target_skill_family, gold_sequence,
hard_negative_skills, required_argument_slots, expected_observation_slots,
template_notes
```

Write 5 to 10 blueprints per category before writing final tasks.

### Phase 2: Draft Tasks

For each blueprint:

1. Write a natural user instruction.
2. Assign `gold_skills` and `gold_sequence`.
3. Add `hard_negative_skills`.
4. Add strict `expected_checks`.
5. Mark `source_inspiration`.
6. Mark `difficulty`.

### Phase 3: Execute Gold Skills Offline

For tool tasks:

1. Call the gold skill manually or with a script.
2. Record expected observation substrings.
3. Fix the task if the local rule-based skill cannot produce the expected
   output.

This is important because the benchmark should evaluate the agent, not expose
bugs in the benchmark labels.

### Phase 4: Near-Duplicate Filtering

Use simple lexical checks:

- Jaccard similarity over normalized tokens.
- Shared numeric values.
- Shared exact text snippets.
- Shared instruction prefix.

Hard and Hidden should not contain near-duplicates of Dev.

### Phase 5: Baseline Sanity Run

Run:

```powershell
.\.venv\Scripts\python.exe scripts\inspect_benchmark.py --benchmark data\skillbench_hard.json
.\.venv\Scripts\python.exe run.py --agent baseline --retriever bm25 --benchmark data\skillbench_hard.json --max_tasks 20 --output results\smoke_hard_baseline.jsonl
.\.venv\Scripts\python.exe run.py --agent enhanced_v2 --retriever bm25 --benchmark data\skillbench_hard.json --max_tasks 20 --output results\smoke_hard_v2.jsonl
```

The goal is not that V2 performs perfectly. The goal is to ensure the benchmark
runs and failures are meaningful.

## Expected Evaluation Metrics

The benchmark should report:

- Skill Recall@k
- Need Tool Accuracy
- No-tool Accuracy
- Unnecessary Tool Call Rate
- Skill Selection Accuracy
- Exact Skill Sequence Accuracy
- Under-call Rate
- Wrong Order Rate
- Argument Accuracy
- Observation Accuracy
- Final Answer Faithfulness Accuracy
- Parameter Strict Success Rate
- Invalid Call Rate
- Average Steps

For the paper/report, prioritize:

1. Need Tool Accuracy
2. Exact Skill Sequence Accuracy
3. Argument Accuracy
4. Observation Accuracy
5. Final Answer Faithfulness
6. Parameter Strict Success

These metrics make the project clearly about skill calling, not only retrieval.

## Recommended First Implementation Batch

Start with 60 new Dev tasks before writing all 320 new tasks:

| Category | Count |
|---|---:|
| hard no-tool / irrelevance | 10 |
| missing-info | 10 |
| unsupported-tool | 5 |
| single-skill minimal pairs | 15 |
| argument-heavy single-skill | 10 |
| implicit multi-skill | 10 |

After those 60 pass inspection and smoke runs, continue to the full
240/120/80 plan.

## Reporting Position

Use this wording:

> SkillBench V2 is a diagnostic benchmark constructed by adapting task
> categories from established tool-use benchmarks, including MetaTool, BFCL,
> API-Bank, and ToolBench retrieval data. It evaluates not only skill retrieval
> but also tool-use awareness, skill sequence planning, argument construction,
> observation correctness, and final-answer faithfulness.

This makes the dataset sound methodologically grounded rather than purely
self-authored.
