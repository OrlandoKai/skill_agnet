# Skill Contract V2 Plan

## Goal

SkillBench V2 needs stricter benchmark labels, but it also needs a stronger
skill data layer. The current `data/skill_library.json` only has:

```text
name, description, input_schema, examples, keywords
```

This is enough for a minimal retriever, but not enough for:

- missing-info tasks
- unsupported-tool tasks
- hard negative skill selection
- multi-skill dependency planning
- argument correctness evaluation
- observation correctness evaluation
- final-answer faithfulness

Therefore SkillBench V2 should introduce `Skill Contract V2`: a richer skill
metadata format aligned with BFCL-style function schemas, API-Bank-style call
traces, MetaTool-style natural intents, and ToolBench-style retrieval documents.

## Core Decision

Do **not** add many new skills immediately.

Recommended direction:

1. Keep the current 40 skill names fixed for V2 Phase 1.
2. Upgrade `skill_library.json` into a richer contract file.
3. Fix only the high-risk skill implementations whose current outputs would
   create false benchmark failures.
4. Add new skills only after Dev/Hard/Hidden results show that skill coverage,
   not calling quality, is the bottleneck.

Rationale:

- Existing 40 skills already cover the main near-neighbor families.
- Current failures are mostly sequence planning, input construction, and
  observation correctness, not lack of skill count.
- Adding many skills now would make error attribution harder.
- Freezing skill names preserves comparability with previous 120-task
  experiments.

## Recommended Files

Keep backward compatibility:

```text
data/
  skill_library.json              # current format, kept for old scripts
  skill_library_v2.json           # richer Skill Contract V2 format
```

Later, after all code paths support V2:

```text
data/
  skill_library_legacy.json
  skill_library.json              # promoted V2 format
```

Do not replace the current file until retrievers, agents, and benchmark
inspectors all support the richer schema.

## Skill Contract V2 Schema

Each skill should become:

```json
{
  "name": "unit_converter",
  "version": "2.0",
  "status": "active",
  "category": "numeric_conversion",
  "description": "Convert a numeric value from one supported unit to another.",
  "capability_scope": {
    "can_do": [
      "convert cm to m",
      "convert m to cm",
      "convert kg to g",
      "convert Celsius to Fahrenheit"
    ],
    "cannot_do": [
      "currency conversion",
      "timezone conversion",
      "unit conversion when value or units are missing"
    ]
  },
  "input_contract": {
    "input_type": "text",
    "required_information": ["numeric_value", "source_unit", "target_unit"],
    "optional_information": [],
    "requires_complete_input": true,
    "can_use_previous_output": false,
    "missing_info_behavior": "return NONE and ask for the missing value or unit"
  },
  "argument_slots": [
    {
      "name": "numeric_value",
      "type": "number",
      "required": true,
      "patterns": ["250", "3.5"]
    },
    {
      "name": "source_unit",
      "type": "enum",
      "required": true,
      "values": ["cm", "m", "km", "g", "kg", "C", "F"]
    },
    {
      "name": "target_unit",
      "type": "enum",
      "required": true,
      "values": ["cm", "m", "km", "g", "kg", "C", "F"]
    }
  ],
  "output_contract": {
    "success_prefix": "Converted:",
    "success_contains": ["source_value", "target_value", "target_unit"],
    "error_prefixes": ["Error:", "Unsupported conversion:"],
    "faithfulness_rule": "final answer must preserve the converted value or report the error"
  },
  "retrieval_contract": {
    "trigger_phrases": ["convert", "to meters", "cm to m", "kg to g"],
    "anti_trigger_phrases": ["currency", "timezone", "what does convert mean"],
    "hard_negative_skills": ["calculator", "percentage_calculator", "ratio_calculator"],
    "retrieval_text": "Convert numeric physical units such as cm to m, m to cm, kg to g, g to kg, Celsius to Fahrenheit."
  },
  "calling_contract": {
    "selection_rules": [
      "Use this skill only when value, source unit, and target unit are present.",
      "Do not use calculator for unit conversion."
    ],
    "input_builder_hints": [
      "Preserve the original numeric value and units.",
      "Do not rewrite an incomplete request into a completed conversion."
    ],
    "previous_output_policy": "never"
  },
  "examples": {
    "positive": [
      {
        "instruction": "A note says 250 cm; convert it to meters.",
        "input": "250 cm to m",
        "output_contains": ["2.5", "m"]
      }
    ],
    "negative": [
      {
        "instruction": "Convert this value to meters.",
        "why_not": "missing numeric value and source unit"
      }
    ],
    "minimal_pairs": [
      {
        "instruction": "Calculate 250 / 100.",
        "correct_skill": "calculator"
      }
    ]
  },
  "benchmark_support": {
    "task_types": ["single_skill", "missing_info", "multi_skill"],
    "recommended_splits": ["dev", "hard", "hidden"],
    "expected_check_templates": {
      "arguments": ["numeric_value", "source_unit", "target_unit"],
      "observations": ["target_value", "target_unit"],
      "final_answer": ["target_value"]
    }
  }
}
```

## Mandatory New Fields

| Field | Why it is needed |
|---|---|
| `category` | Enables family-level coverage and near-neighbor analysis. |
| `capability_scope.can_do` | Clarifies valid use cases. |
| `capability_scope.cannot_do` | Supports no-tool, unsupported-tool, and hard negatives. |
| `input_contract.required_information` | Supports missing-info tasks. |
| `input_contract.requires_complete_input` | Prevents fabricated tool arguments. |
| `input_contract.can_use_previous_output` | Supports dependent multi-skill tasks. |
| `argument_slots` | Enables parameter-level correctness. |
| `output_contract` | Enables observation correctness and faithfulness. |
| `retrieval_contract.trigger_phrases` | Improves retriever text. |
| `retrieval_contract.anti_trigger_phrases` | Helps no-tool and false-positive analysis. |
| `retrieval_contract.hard_negative_skills` | Creates controlled confusing candidates. |
| `calling_contract.selection_rules` | Helps planner choose among similar skills. |
| `calling_contract.input_builder_hints` | Helps argument construction. |
| `examples.negative` | Distinguishes no-tool or wrong-tool cases. |
| `examples.minimal_pairs` | Creates SkillBench-Hard minimal pairs. |
| `benchmark_support.expected_check_templates` | Speeds up task generation and inspection. |

## Skill Categories

Assign every current skill to one category.

| Category | Skills |
|---|---|
| arithmetic_numeric | `calculator`, `percentage_calculator`, `ratio_calculator`, `equation_solver`, `statistics_calculator`, `number_sequence_analyzer` |
| conversion_time | `unit_converter`, `date_difference_calculator` |
| list_data_ops | `range_filter`, `list_sorter`, `deduplicator` |
| extraction | `keyword_extractor`, `regex_extractor`, `entity_extractor`, `todo_extractor`, `meeting_notes_extractor` |
| classification | `sentiment_analyzer`, `topic_classifier`, `intent_classifier`, `language_detector`, `readability_scorer` |
| transformation_generation | `summarizer`, `text_rewriter`, `grammar_corrector`, `tone_converter`, `title_generator`, `outline_generator`, `question_generator`, `checklist_generator`, `pros_cons_analyzer`, `argument_mapper`, `email_drafter` |
| structured_formatting | `json_validator`, `csv_summarizer`, `table_formatter`, `citation_formatter` |
| code_and_research | `python_executor`, `paper_qa` |

## Family-Level Contract Rules

### Arithmetic and Numeric Skills

Skills:

- `calculator`
- `percentage_calculator`
- `ratio_calculator`
- `equation_solver`
- `statistics_calculator`
- `number_sequence_analyzer`

Required contract additions:

- distinguish expression vs percentage vs ratio vs equation vs statistics vs sequence
- require explicit numbers
- define whether the skill accepts word problems
- define output value patterns

Hard negative rules:

- `calculator` is a hard negative for all other numeric skills.
- `statistics_calculator` should not handle one-off arithmetic.
- `equation_solver` requires an equals sign and a variable.
- `number_sequence_analyzer` requires a list that implies a pattern.

Benchmark implication:

- Every numeric family benchmark should include minimal pairs with the same
  numbers but different requested operations.

Example minimal pair set:

```text
Calculate 18 / 72.                 -> calculator
What percentage is 18 of 72?       -> percentage_calculator
Find the ratio of 18 to 72.        -> ratio_calculator
Solve 72*x = 18.                   -> equation_solver
Give the mean of 18 and 72.        -> statistics_calculator
Continue 18, 36, 54, 72.           -> number_sequence_analyzer
```

### Conversion and Date Skills

Skills:

- `unit_converter`
- `date_difference_calculator`

Required contract additions:

- unit converter requires value, source unit, target unit
- date difference requires two valid dates
- both should reject missing-info requests

Implementation risk:

- `unit_converter` currently fails on natural wording such as
  "A note says 250 cm; convert it to meters."

Required implementation fix:

- Support natural unit mentions and aliases:
  - meter/meters/m
  - centimeter/centimeters/cm
  - kilogram/kilograms/kg
  - gram/grams/g
  - Celsius/C
  - Fahrenheit/F

Benchmark implication:

- Include missing-info examples:
  - "Convert this value to meters."
  - "How many days apart are these dates?"

### Extraction Skills

Skills:

- `keyword_extractor`
- `regex_extractor`
- `entity_extractor`
- `todo_extractor`
- `meeting_notes_extractor`

Required contract additions:

- define extraction target
- define required input text
- define output entity types or pattern types
- define difference between statistical keywords, exact regex patterns, named entities, action items, and meeting fields

Hard negative rules:

- `keyword_extractor` is a hard negative for `entity_extractor`.
- `regex_extractor` is a hard negative for `keyword_extractor` when emails,
  dates, phones, or URLs are present.
- `meeting_notes_extractor` is a hard negative for `todo_extractor` when the
  task asks for decisions/actions/dates.

Benchmark implication:

- Use same source text with different asks:

```text
List frequent terms from this note.       -> keyword_extractor
Find the emails and dates in this note.   -> regex_extractor
Mark people, orgs, and locations.         -> entity_extractor
Pull action items.                        -> todo_extractor
Extract decisions, actions, and dates.    -> meeting_notes_extractor
```

### Classification Skills

Skills:

- `sentiment_analyzer`
- `topic_classifier`
- `intent_classifier`
- `language_detector`
- `readability_scorer`

Required contract additions:

- classify text, do not execute the classified intent
- distinguish intent classification from performing translation/calculation
- define expected label space

Hard negative rules:

- `intent_classifier` should not call the underlying intent skill.
- `language_detector` should not translate.
- `sentiment_analyzer` should not rewrite text.

Implementation risk:

- `language_detector` currently returns English for mixed "你好 skill agent" in
  some shell encodings and should output mixed when both Chinese and English are
  present.

Benchmark implication:

- Add tasks like:
  - "Classify the intent: please translate this into Chinese." -> `intent_classifier`, not translator
  - "Do not translate this; identify the language." -> `language_detector`

### Transformation and Generation Skills

Skills:

- `summarizer`
- `text_rewriter`
- `grammar_corrector`
- `tone_converter`
- `title_generator`
- `outline_generator`
- `question_generator`
- `checklist_generator`
- `pros_cons_analyzer`
- `argument_mapper`
- `email_drafter`

Required contract additions:

- define output format and purpose
- define whether the skill transforms existing text or generates new structure
- define previous-output compatibility

Hard negative rules:

- `summarizer` is a hard negative for `title_generator`, `outline_generator`,
  `question_generator`, and `checklist_generator`.
- `text_rewriter` is a hard negative for `grammar_corrector` and
  `tone_converter`.
- `email_drafter` is a hard negative for `tone_converter`.

Benchmark implication:

- Use negation and minimal pairs:

```text
Condense this paragraph.                     -> summarizer
Give this paragraph a headline.              -> title_generator
Make an outline for this topic.              -> outline_generator
Write study questions about this topic.      -> question_generator
Make a checklist for running this experiment.-> checklist_generator
Fix grammar in this sentence.                -> grammar_corrector
Make this sentence formal.                   -> tone_converter
Draft an email to Professor Lee.             -> email_drafter
```

### Structured Formatting Skills

Skills:

- `json_validator`
- `csv_summarizer`
- `table_formatter`
- `citation_formatter`

Required contract additions:

- define accepted input structure
- define whether the skill validates, summarizes, or formats
- define output prefix and checkable output fields

Implementation risks:

- `csv_summarizer` should extract CSV blocks from natural language wrappers.
- `table_formatter` should support `key=value` pairs better.

Hard negative rules:

- `json_validator` does not format JSON into tables.
- `csv_summarizer` does not format Markdown tables.
- `table_formatter` does not calculate numeric summaries.
- `citation_formatter` does not answer paper questions.

Benchmark implication:

- Include same input represented as JSON, CSV, and key-value text.

### Code and Research Skills

Skills:

- `python_executor`
- `paper_qa`

Required contract additions:

- `python_executor` should be explicitly restricted to safe, small,
  self-contained code.
- `paper_qa` should be marked as placeholder or excluded from Hard/Hidden until
  a paper corpus is available.

Recommended status:

```json
{
  "name": "paper_qa",
  "status": "dev_only_placeholder",
  "benchmark_support": {
    "recommended_splits": ["dev"],
    "exclude_from": ["hard", "hidden"]
  }
}
```

Rationale:

- Strict observation correctness is not meaningful for `paper_qa` while it
  returns a placeholder.
- Keeping it in Dev preserves current compatibility.

## Skills That Need Implementation Fixes Before V2 Hard/Hidden

### Must Fix

| Skill | Issue | Required fix |
|---|---|---|
| `unit_converter` | Natural wording often returns unsupported. | Parse value/source/target unit aliases. |
| `csv_summarizer` | Natural wrapper text may break row/column count. | Extract CSV block before parsing. |
| `translator_zh_en` | Too many placeholder outputs. | Expand fixed dictionary for benchmark vocabulary. |
| `translator_en_zh` | Needs stable benchmark vocabulary. | Expand fixed dictionary and normalize casing. |
| `language_detector` | Mixed language behavior is not explicit. | Return `mixed Chinese-English` when both are present. |

### Should Fix

| Skill | Issue | Suggested fix |
|---|---|---|
| `table_formatter` | `key=value` pairs become item rows. | Parse repeated `key=value` pairs into columns. |
| `percentage_calculator` | Some wordings require careful argument order. | Add patterns for `out of`, `from X to Y`, `what percentage`. |
| `regex_extractor` | Output schema should be stable. | Always output emails/dates/phones/urls fields. |
| `meeting_notes_extractor` | Needs stable decisions/actions/dates output. | Normalize output keys. |

### Do Not Expand Yet

| Skill | Reason |
|---|---|
| `python_executor` | It can become a universal bypass skill and obscure skill selection errors. |
| `paper_qa` | Placeholder behavior makes strict Hard/Hidden labels weak. |

## Potential New Skills for V2 Phase 2

Only add these after V2 Phase 1 shows that 40 skills are insufficient.

| Candidate skill | Why add | Main hard negatives |
|---|---|---|
| `currency_converter` | Adds conversion domain beyond physical units. | `unit_converter`, `calculator` |
| `timezone_converter` | Adds time conversion distinct from date difference. | `date_difference_calculator`, `unit_converter` |
| `markdown_formatter` | Distinguishes formatting from table formatting. | `table_formatter`, `text_rewriter` |
| `schema_extractor` | Extract fields/schema from JSON/CSV. | `json_validator`, `entity_extractor` |
| `code_explainer` | Separates code explanation from code execution. | `python_executor`, `summarizer` |
| `error_log_analyzer` | Tests regex vs summarization vs diagnosis. | `regex_extractor`, `summarizer`, `keyword_extractor` |
| `math_word_problem_solver` | Distinguishes word-problem solving from raw calculator. | `calculator`, `equation_solver` |
| `citation_extractor` | Extract citation metadata rather than format it. | `citation_formatter`, `paper_qa` |

Phase 2 warning:

- Adding these skills requires new skill implementations, new registry entries,
  new skill tests, and new benchmark coverage.
- Do not mix Phase 2 with the first V2 benchmark creation, or the experimental
  story will become harder to interpret.

## V2 Contract Examples by Skill Family

### Numeric Contract Example

```json
{
  "name": "percentage_calculator",
  "category": "arithmetic_numeric",
  "input_contract": {
    "required_information": ["part_or_base", "whole_or_percent"],
    "requires_complete_input": true,
    "can_use_previous_output": false
  },
  "argument_slots": [
    {"name": "part", "type": "number", "required": false},
    {"name": "whole", "type": "number", "required": false},
    {"name": "percent", "type": "number", "required": false}
  ],
  "retrieval_contract": {
    "trigger_phrases": ["percent", "percentage", "%", "out of", "increase", "discount"],
    "anti_trigger_phrases": ["ratio", "mean", "solve x"],
    "hard_negative_skills": ["calculator", "ratio_calculator", "statistics_calculator"]
  },
  "calling_contract": {
    "selection_rules": [
      "Use for percent-of and percentage-change.",
      "Do not use for ratio simplification."
    ],
    "input_builder_hints": [
      "Preserve both numbers and whether the wording is percent-of or part-of-whole."
    ]
  }
}
```

### Extraction Contract Example

```json
{
  "name": "regex_extractor",
  "category": "extraction",
  "input_contract": {
    "required_information": ["source_text", "pattern_type_or_obvious_patterns"],
    "requires_complete_input": true,
    "can_use_previous_output": true
  },
  "output_contract": {
    "success_prefix": "Regex matches:",
    "success_contains": ["emails=", "dates=", "phones=", "urls="],
    "error_prefixes": ["Error:"]
  },
  "retrieval_contract": {
    "trigger_phrases": ["email", "date", "phone", "url", "pattern", "contact"],
    "anti_trigger_phrases": ["keyword", "topic", "entity name"],
    "hard_negative_skills": ["keyword_extractor", "entity_extractor", "todo_extractor"]
  }
}
```

### Multi-Skill Dependency Contract Example

```json
{
  "name": "keyword_extractor",
  "category": "extraction",
  "input_contract": {
    "required_information": ["source_text"],
    "requires_complete_input": true,
    "can_use_previous_output": true
  },
  "calling_contract": {
    "previous_output_policy": "allowed",
    "selection_rules": [
      "If the instruction asks for keywords from a generated title, use the previous title output as input."
    ]
  },
  "benchmark_support": {
    "common_previous_skill": ["title_generator", "translator_zh_en", "summarizer"]
  }
}
```

## How Contracts Support SkillBench V2

| Benchmark need | Contract field |
|---|---|
| Need-tool decision | `capability_scope.cannot_do`, `anti_trigger_phrases` |
| Missing-info labels | `required_information`, `requires_complete_input` |
| Unsupported-tool labels | `status`, `cannot_do`, `failure_modes` |
| Retrieval qrels | `retrieval_text`, `trigger_phrases`, `hard_negative_skills` |
| Skill sequence labels | `can_use_previous_output`, `common_previous_skill` |
| Argument checks | `argument_slots`, `input_builder_hints` |
| Observation checks | `output_contract.success_contains` |
| Final faithfulness | `output_contract.faithfulness_rule` |

## Migration Plan

### Step 1: Create `skill_library_v2.json`

Generate a V2 record for all current 40 skills.

Do not change the current `skill_library.json` yet.

### Step 2: Update Inspectors

Extend `scripts/inspect_benchmark.py` or add
`scripts/inspect_skill_contracts.py` to check:

- all registered skills appear in V2
- no skill appears in V2 but not registry
- required fields exist
- hard negative skills exist
- examples reference valid skills
- placeholder skills are excluded from Hard/Hidden

### Step 3: Update Retrievers

Allow retrievers to build skill text from:

```text
name + description + can_do + cannot_do + trigger_phrases + examples.positive
```

Do not include too many negative examples directly in retrieval text, because
they may retrieve the wrong skill by lexical overlap. Keep negative examples for
planner prompts and benchmark generation.

### Step 4: Update Agent Prompt

For candidate skills, show:

- description
- required information
- cannot-do boundary
- hard negative warning
- input builder hints
- output schema

This should replace the current looser prompt contract.

### Step 5: Fix High-Risk Skills

Fix the Must Fix skills before creating Hard/Hidden:

1. `unit_converter`
2. `csv_summarizer`
3. `translator_zh_en`
4. `translator_en_zh`
5. `language_detector`

### Step 6: Create 60 New Dev Tasks

Use the first batch from the manufacturing protocol:

- 10 hard no-tool / irrelevance
- 10 missing-info
- 5 unsupported-tool
- 15 single-skill minimal pairs
- 10 argument-heavy single-skill
- 10 implicit multi-skill

These 60 tasks validate whether contracts are usable before making the full
240/120/80 split.

### Step 7: Only Then Generate Hard and Hidden

After Dev tasks pass inspection and smoke runs:

- create `skillbench_hard.json`
- create `skillbench_hidden.json`

Freeze Hard and Hidden once created.

## Concrete Phase 1 Deliverables

Recommended immediate deliverables:

1. `data/skill_library_v2.json`
2. `scripts/inspect_skill_contracts.py`
3. fixes for 5 Must Fix skills
4. `data/skillbench_dev_extra_60.json`
5. update `scripts/inspect_benchmark.py` to understand:
   - `missing_info`
   - `unsupported_tool`
   - `gold_sequence`
   - `benchmark_tags`
   - `hard_negative_skills`
6. update evaluation to treat missing-info and unsupported-tool as correct only
   when no tool is called and the final answer asks for clarification or states
   unsupported capability.

## Recommendation Summary

For SkillBench V2, skill data should be modified more than expanded.

Recommended strategy:

```text
Phase 1:
  40 fixed skills
  richer skill contracts
  high-risk implementation fixes
  60 new Dev tasks

Phase 2:
  full 240 Dev / 120 Hard / 80 Hidden

Phase 3:
  optional new skills only if coverage is the bottleneck
```

This keeps the research story clean:

> Better skill calling requires retrieval-aware skill contracts, not simply more
> tool names.
