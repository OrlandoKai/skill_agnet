# skill_agent_baseline

`skill_agent_baseline` is a minimal local Agent baseline for studying **Skill Retrieval and Skill Calling for Agent Systems**.

The first stage uses a local Llama2-7B-Chat q4 GGUF model through `llama-cpp-python`. It does not call remote APIs.

## Project Goal

Run the smallest complete Agent loop:

```text
task -> skill retrieval -> skill calling -> observation -> final answer -> evaluation
```

This baseline is intentionally simple. The first version focuses on a stable research scaffold, not on strong tool performance.

## Minimal Agent Flow

1. Receive a user task.
2. Retrieve candidate skills from `data/skill_library.json` with BM25.
3. Ask the local Llama model to select a skill and prepare skill input as JSON.
4. Call the selected skill through `skills/skill_registry.py`.
5. Treat the skill return value as the observation.
6. Ask the local Llama model to produce the final answer.
7. Run a simple evaluation and save the trace into `results/`.

## Directory Layout

```text
skill_agent_baseline/
  agents/       Agent orchestration logic
  data/         Skill library metadata
  docs/         Notes and design documents
  eval/         Minimal evaluation utilities
  model/        Local Llama wrapper
  results/      Saved run outputs
  retrievers/   Skill retrievers
  scripts/      Test scripts
  skills/       Callable skills and registry
```

## Install

```bash
pip install -r requirements.txt
```

The configured local model path is:

```text
D:\llm\models\llama2-7b-chat-q4_k_m-self.gguf
```

Edit `config.py` if the model moves or if you want to change context length or GPU layers.

## Recommended Python

Use the project virtual environment:

```bash
.\.venv\Scripts\python.exe
```

The commands below use `python` for readability. On this machine, replace it with `.\.venv\Scripts\python.exe` if the virtual environment is not activated.

Do not run multiple Llama baselines concurrently on an 8 GB laptop GPU. Run `full`, `bm25`, and `embedding` sequentially.

## Test Llama

Run from the project root:

```bash
python scripts/test_llama.py
```

Expected behavior: the script loads the local GGUF model and prints a short model response.

## Test Skills

Run from the project root:

```bash
python scripts/test_skills.py
```

Expected behavior: all 10 skills print `[OK]` and return non-empty strings.

## SkillBench-Mini Workflow

1. Test skills:

```bash
python scripts/test_skills.py
```

2. Inspect the benchmark:

```bash
python scripts/inspect_benchmark.py
```

3. Test retrievers:

```bash
python scripts/test_retrievers.py
```

4. Run the Full Skill Prompt baseline:

```bash
python run.py --retriever full --max_tasks 30 --output results/run_full.jsonl
```

5. Run the BM25 baseline:

```bash
python run.py --retriever bm25 --top_k 5 --max_tasks 30 --output results/run_bm25.jsonl
```

6. Run the embedding baseline:

```bash
python run.py --retriever embedding --top_k 5 --max_tasks 30 --output results/run_embedding.jsonl
```

7. Evaluate a run:

```bash
python -m eval.evaluate --input results/run_bm25.jsonl
```

8. Compare multiple runs:

```bash
python scripts/compare_runs.py --inputs results/run_full.jsonl results/run_bm25.jsonl results/run_embedding.jsonl
```

9. Analyze failures:

```bash
python scripts/analyze_failures.py --input results/run_bm25.jsonl
```

## Outputs

- `results/run_*.jsonl`: one Agent trace per line.
- `results/metrics_*.csv`: metrics for one run.
- `results/compare_results.csv`: method comparison table.
- `results/failure_cases_*.json`: categorized failed cases.

## Evaluation Metrics

- `skill_recall`: average fraction of gold skills retrieved.
- `skill_selection_acc`: whether the called skills contain the gold skills; no-tool tasks are correct when no skill is called.
- `task_success_rate`: rule-based answer success using expected numbers or keywords.
- `invalid_call_rate`: fraction of examples with invalid tool calls.
- `avg_steps`: average number of called skills.

## Next Steps

- Add hybrid retrieval and reranking baselines.
- Replace placeholder text skills with LLM-backed implementations.
- Improve multi-step planning and stopping.
- Add human-checked answer grading for final answer quality.
