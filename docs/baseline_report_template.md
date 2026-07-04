# Skill Agent Baseline Experimental Report

## Project Goal

This project builds a minimal local baseline for studying **Skill Retrieval and Skill Calling for Agent Systems**.

The target loop is:

```text
task -> skill retrieval -> skill calling -> observation -> final answer -> evaluation
```

The current implementation uses a local Llama2-7B-Chat q4 GGUF model through `llama-cpp-python`, without remote API calls.

## Minimal Agent Pipeline

1. Receive a task from SkillBench-Mini.
2. Retrieve candidate skills with a selected retriever.
3. Ask local Llama2-7B-Chat to choose one candidate skill or `NONE`.
4. Execute the selected skill through `skills/skill_registry.py`.
5. Store the returned value as an observation.
6. Ask the model to generate the final answer from the task and observations.
7. Evaluate retrieval, selection, task success, invalid calls, and average steps.

## Skill Library Design

The v1 skill library contains 10 callable skills:

- `calculator`
- `unit_converter`
- `summarizer`
- `translator_zh_en`
- `translator_en_zh`
- `keyword_extractor`
- `text_rewriter`
- `sentiment_analyzer`
- `paper_qa`
- `python_executor`

Each skill has metadata in `data/skill_library.json`, including `name`, `description`, `input_schema`, `examples`, and `keywords`.

The first version intentionally keeps the skills simple and stable. Text skills are rule-based or placeholder implementations, while `calculator` and `python_executor` include restricted execution logic.

## SkillBench-Mini Design

SkillBench-Mini contains 30 tasks:

- 15 `single_skill` tasks
- 10 `multi_skill` tasks
- 5 `no_tool` tasks

The benchmark tests:

- whether the retriever can place gold skills into the candidate set;
- whether the model selects the correct skill from candidates;
- whether the agent avoids unnecessary tool use on no-tool tasks;
- whether simple multi-step skill calling works in a constrained loop.

## Baseline Methods

Three retriever baselines were evaluated:

- **Full Skill Prompt**: returns all skills as candidates.
- **BM25 Retriever**: lexical retrieval over skill descriptions, examples, and keywords.
- **Embedding Retriever**: `sentence-transformers/all-MiniLM-L6-v2` retrieval with cosine similarity.

The same local Llama2 model and agent loop were used for all three methods.

## Experimental Setup

Experiments were run on 2026-07-04 with:

- Local model: `D:\llm\models\llama2-7b-chat-q4_k_m-self.gguf`
- Inference backend: `llama-cpp-python`
- GPU setting: `N_GPU_LAYERS = -1`
- Benchmark size: 30 tasks
- Top-k for BM25 and Embedding: 5
- Max agent steps: 2

Commands:

```bash
.\.venv\Scripts\python.exe -B run.py --retriever full --max_tasks 30 --output results\run_full.jsonl
.\.venv\Scripts\python.exe -B run.py --retriever bm25 --top_k 5 --max_tasks 30 --output results\run_bm25.jsonl
.\.venv\Scripts\python.exe -B run.py --retriever embedding --top_k 5 --max_tasks 30 --output results\run_embedding.jsonl
.\.venv\Scripts\python.exe -B scripts\compare_runs.py --inputs results\run_full.jsonl results\run_bm25.jsonl results\run_embedding.jsonl
```

Generated artifacts:

- `results/run_full.jsonl`
- `results/run_bm25.jsonl`
- `results/run_embedding.jsonl`
- `results/metrics_run_full.csv`
- `results/metrics_run_bm25.csv`
- `results/metrics_run_embedding.csv`
- `results/compare_results.csv`
- `results/failure_cases_run_full.json`
- `results/failure_cases_run_bm25.json`
- `results/failure_cases_run_embedding.json`

## Evaluation Metrics

- **Skill Recall@k**: average gold skill recall in retrieved candidates.
- **Skill Selection Accuracy**: whether gold skills were called; for no-tool tasks, no tool call is counted as correct.
- **Task Success Rate**: rule-based final answer success using expected numbers or keywords.
- **Invalid Tool Call Rate**: fraction of invalid JSON parsing or nonexistent skill calls.
- **Average Steps**: average number of called skills.

## Experimental Results

| method | num_tasks | skill_recall | skill_selection_acc | task_success_rate | invalid_call_rate | avg_steps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| full | 30 | 1.0000 | 0.4000 | 0.9333 | 0.0000 | 1.2333 |
| bm25 | 30 | 1.0000 | 0.4000 | 1.0000 | 0.0000 | 1.1000 |
| embedding | 30 | 1.0000 | 0.5667 | 1.0000 | 0.0000 | 1.2333 |

### Result Interpretation

All three methods achieved perfect `Skill Recall@k`, which means the gold skills were always present in the retrieved candidate set. The main bottleneck is therefore not retrieval coverage in this small benchmark, but model-side skill selection and stopping.

The embedding retriever achieved the best skill selection accuracy at `0.5667`, outperforming both Full Prompt and BM25 at `0.4000`. This suggests that candidate ordering and semantic proximity help the local model choose the correct tool, even when retrieval recall is already saturated.

BM25 achieved the lowest average steps at `1.1000`, but this is not necessarily better: several multi-skill tasks stopped too early or selected only one of the required skills. The current task success metric is rule-based and can overestimate success when the final answer contains expected keywords despite incomplete tool selection.

No method produced invalid tool calls. This indicates that the JSON action prompt, parser repair, and candidate-skill validation are stable enough for the current baseline.

## Failure Analysis

Failure analysis was generated with:

```bash
.\.venv\Scripts\python.exe -B scripts\analyze_failures.py --input results\run_full.jsonl
.\.venv\Scripts\python.exe -B scripts\analyze_failures.py --input results\run_bm25.jsonl
.\.venv\Scripts\python.exe -B scripts\analyze_failures.py --input results\run_embedding.jsonl
```

| method | retrieval_failure | selection_failure | invalid_call | execution_failure | final_answer_failure | unnecessary_tool_call | total_failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full | 0 | 13 | 0 | 0 | 1 | 5 | 19 |
| bm25 | 0 | 13 | 0 | 0 | 0 | 5 | 18 |
| embedding | 0 | 8 | 0 | 0 | 0 | 5 | 13 |

### Main Failure Types

1. **Selection failure**

   The largest failure category is incorrect skill selection. Common examples include:

   - choosing `calculator` instead of `unit_converter`;
   - choosing `translator_zh_en` instead of `translator_en_zh`;
   - choosing `summarizer` instead of `paper_qa`;
   - calling only one skill for multi-skill tasks.

   This shows that candidate retrieval alone is insufficient. The action prompt needs stronger constraints, better examples, and possibly task-type-aware planning.

2. **Unnecessary tool calls**

   All three methods called tools on all 5 no-tool tasks. This is the clearest weakness of the current agent loop. The model tends to call a plausible text skill even when the task should be answered directly.

3. **Final answer failure**

   Full Prompt produced 1 final-answer failure. BM25 and Embedding had no final-answer failures under the current rule-based evaluator.

4. **No retrieval or execution failures**

   There were no retrieval failures, invalid calls, or execution failures. This confirms that the retriever interfaces, skill registry, JSON parser, and restricted skill execution are stable enough for a minimal baseline.

## Conclusions

The project successfully runs the minimal closed loop:

```text
task -> skill retrieval -> skill calling -> observation -> final answer -> evaluation
```

The baseline is stable: all runs completed, no invalid tool calls occurred, and results were saved as JSONL traces. The strongest method in this experiment is the embedding retriever, mainly because it improves skill selection accuracy while preserving perfect retrieval recall.

However, the main research bottleneck has shifted from retrieval coverage to decision quality:

- the model often selects the wrong skill from a valid candidate set;
- multi-skill tasks are often under-called;
- no-tool tasks trigger unnecessary tool use;
- the current rule-based task success metric is useful for smoke testing but too weak for final answer quality.

## Next Steps

1. Improve the action prompt with few-shot examples for:
   - no-tool tasks;
   - unit conversion vs arithmetic;
   - Chinese-to-English vs English-to-Chinese translation;
   - multi-skill decomposition.

2. Add a planner-style intermediate decision:
   - first decide `NEED_TOOL` vs `NO_TOOL`;
   - then choose one or more skills.

3. Add hybrid retrieval:
   - BM25 + embedding union;
   - reranking by local model or lightweight classifier.

4. Strengthen evaluation:
   - stricter multi-skill success checks;
   - separate final-answer correctness from skill-call correctness;
   - optional human or LLM-as-judge grading in later stages.

5. Expand SkillBench-Mini:
   - more no-tool tasks;
   - harder multi-step tasks;
   - more realistic paper QA and text transformation examples.
