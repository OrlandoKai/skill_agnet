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
2. Retrieve candidate skills from `data/skill_library.json` with Full Prompt, BM25, or embedding retrieval.
3. Ask the local Llama model to select a skill and prepare skill input as JSON.
4. Call the selected skill through `skills/skill_registry.py`.
5. Treat the skill return value as the observation.
6. Ask the local Llama model to produce the final answer.
7. Run a simple evaluation and save the trace into `results/`.

The original `MinimalSkillAgent` is kept as the baseline. The optional
`EnhancedSkillAgent` adds:

- a `NEED_TOOL / NO_TOOL` gate before retrieval and skill calling
- a two-step skill planner for multi-skill tasks
- skill input contracts built from descriptions, schemas, examples, and hard rules
- observation-grounded final answer generation

`EnhancedSkillAgentV2` further targets the post-no-tool bottlenecks:

- step-aware retrieval for multi-skill tasks
- deterministic planner repair and candidate fallback
- skill-specific input construction
- rule-based final answers from successful observations

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

Expected behavior: all 40 skills print `[OK]` and return non-empty strings.

The skill library includes semantically similar but functionally different tools, such as `calculator`, `ratio_calculator`, `equation_solver`, `statistics_calculator`, `keyword_extractor`, `regex_extractor`, `entity_extractor`, `todo_extractor`, `summarizer`, `title_generator`, `outline_generator`, `meeting_notes_extractor`, `text_rewriter`, `grammar_corrector`, `tone_converter`, and `email_drafter`.

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
python run.py --retriever full --max_tasks 120 --output results/run_full.jsonl
```

5. Run the BM25 baseline:

```bash
python run.py --retriever bm25 --top_k 5 --max_tasks 120 --output results/run_bm25.jsonl
```

6. Run the embedding baseline:

```bash
python run.py --retriever embedding --top_k 5 --max_tasks 120 --output results/run_embedding.jsonl
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

10. Run the enhanced BM25 Agent:

```bash
python run.py --agent enhanced --retriever bm25 --top_k 5 --max_steps 2 --max_tasks 120 --output results/run_enhanced_bm25_120.jsonl
```

11. Run the enhanced embedding Agent:

```bash
python run.py --agent enhanced --retriever embedding --top_k 5 --max_steps 2 --max_tasks 120 --output results/run_enhanced_embedding_120.jsonl
```

12. Run the enhanced V2 BM25 Agent:

```bash
python run.py --agent enhanced_v2 --retriever bm25 --top_k 5 --max_steps 2 --max_tasks 120 --output results/run_enhanced_v2_bm25_120.jsonl
```

13. Run the enhanced V2 embedding Agent:

```bash
python run.py --agent enhanced_v2 --retriever embedding --top_k 5 --max_steps 2 --max_tasks 120 --output results/run_enhanced_v2_embedding_120.jsonl
```

## Streamlit UI

Run the local interactive workbench from the project root:

```bash
.\.venv\Scripts\streamlit.exe run app.py
```

The UI includes seven pages: `总览`, `Benchmark`, `检索器实验`, `Agent 运行`, `评估指标`, `失败分析`, and `自由问答`.

The `自由问答` page supports direct local Llama2 chat and Skill Agent mode. Chat sessions are saved automatically under `results/chat_sessions/`; the chat title uses the first user prompt and is truncated when it is too long.

## Outputs

- `results/run_*.jsonl`: one Agent trace per line.
- `results/metrics_*.csv`: metrics for one run.
- `results/compare_results.csv`: method comparison table.
- `results/failure_cases_*.json`: categorized failed cases.
- `results/chat_sessions/*.json`: saved UI chat sessions.

## SkillBench-Mini v3

The benchmark now contains 120 tasks and 40 callable skills:

- 60 `single_skill` tasks
- 40 `multi_skill` tasks
- 20 `no_tool` tasks

The expanded hard subset uses semantically similar skills with different functions, so retrieval and calling must distinguish cases such as arithmetic vs ratio vs equation solving, keyword vs regex vs entity vs todo extraction, summary vs title vs outline vs meeting-note extraction, grammar correction vs tone conversion vs email drafting, and table formatting vs JSON validation vs CSV summarization.

This version is intentionally more difficult than the original 60-task benchmark. It is designed to show that high skill retrieval recall does not guarantee correct skill selection, ordering, stopping, or no-tool behavior.

## Evaluation Metrics

- `skill_recall`: average fraction of gold skills retrieved.
- `skill_selection_acc`: whether the called skills contain the gold skills; no-tool tasks are correct when no skill is called.
- `need_tool_acc`: whether the Agent correctly decides if tool use is needed.
- `no_tool_acc`: accuracy on no-tool tasks.
- `unnecessary_tool_call_rate`: no-tool tasks where a tool was still called.
- `skill_sequence_acc`: whether actual called skills cover the expected sequence.
- `under_call_rate`: multi-skill tasks where the Agent missed required skills.
- `task_success_rate`: rule-based answer success using expected numbers or keywords.
- `strict_task_success_rate`: stricter success requiring valid calls, correct sequence, and answer content.
- `invalid_call_rate`: fraction of examples with invalid tool calls.
- `avg_steps`: average number of called skills.

## Next Steps

- Add hybrid retrieval and reranking baselines.
- Replace placeholder text skills with LLM-backed implementations.
- Improve multi-step planning and stopping.
- Add human-checked answer grading for final answer quality.
