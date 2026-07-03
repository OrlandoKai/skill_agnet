# Skill Agent Baseline Report Template

## Project Goal

Build a minimal local baseline for Skill Retrieval and Skill Calling in Agent Systems.

The target loop is:

```text
task -> skill retrieval -> skill calling -> observation -> final answer -> evaluation
```

## Minimal Agent Pipeline

1. Receive a task from SkillBench-Mini.
2. Retrieve candidate skills with a selected retriever.
3. Ask local Llama2-7B-Chat to choose one candidate skill or `NONE`.
4. Execute the skill through the registry.
5. Store observations.
6. Generate the final answer from the task and observations.
7. Evaluate retrieval, selection, success, invalid calls, and steps.

## Skill Library Design

The v1 skill library contains 10 skills:

- calculator
- unit_converter
- summarizer
- translator_zh_en
- translator_en_zh
- keyword_extractor
- text_rewriter
- sentiment_analyzer
- paper_qa
- python_executor

Each skill has metadata in `data/skill_library.json`: name, description, input schema, examples, and keywords.

## SkillBench-Mini Design

SkillBench-Mini contains 30 tasks:

- 15 single-skill tasks
- 10 multi-skill tasks
- 5 no-tool tasks

The benchmark tests retrieval quality, skill selection, unnecessary tool use, and minimal multi-step calling.

## Baseline Methods

- Full Skill Prompt: returns all skills as candidates.
- BM25 Retriever: lexical retrieval over skill descriptions, examples, and keywords.
- Embedding Retriever: sentence-transformer retrieval with cosine similarity.

## Evaluation Metrics

- Skill Recall@k: average gold skill recall in retrieved candidates.
- Skill Selection Accuracy: whether gold skills were called, or no tool was called for no-tool tasks.
- Task Success Rate: rule-based answer success using expected numbers or keywords.
- Invalid Tool Call Rate: fraction of invalid JSON or nonexistent skill calls.
- Average Steps: average number of called skills.

## Experimental Results

Fill this section after running:

```bash
python scripts/compare_runs.py --inputs results/run_full.jsonl results/run_bm25.jsonl results/run_embedding.jsonl
```

| method | skill_recall | skill_selection_acc | task_success_rate | invalid_call_rate | avg_steps |
| --- | ---: | ---: | ---: | ---: | ---: |
| full | TBD | TBD | TBD | TBD | TBD |
| bm25 | TBD | TBD | TBD | TBD | TBD |
| embedding | TBD | TBD | TBD | TBD | TBD |

## Failure Analysis

Use:

```bash
python scripts/analyze_failures.py --input results/run_bm25.jsonl
```

Report failures by type:

- retrieval_failure
- selection_failure
- invalid_call
- execution_failure
- final_answer_failure
- unnecessary_tool_call

## Next Steps

- Improve prompts for no-tool and multi-step stopping.
- Add hybrid retrieval and reranking.
- Add more realistic skills and domain tasks.
- Add stronger answer grading beyond keyword matching.
- Run repeated trials to estimate variance.
