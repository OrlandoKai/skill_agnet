# Week 4 Experiment Record: Strict Evaluation on 120-task SkillBench-Mini

## Goal

本周目标是把项目从“能跑 baseline”推进到“评测可信、问题定位清楚”。

核心关注点：

- 补强 evaluation 指标，区分 retrieval、skill selection、tool-use decision、multi-skill sequence 和 final answer。
- 在扩展后的 40 skills / 120 tasks benchmark 上完整运行 Full Prompt、BM25、Embedding 三条 baseline。
- 分析 no-tool 误调用、多技能漏调、错误技能顺序、invalid call 和 final answer hallucination。

## Evaluation Updates

本次新增或补强的指标：

- `need_tool_acc`: 判断模型是否正确决定需要或不需要工具。
- `no_tool_acc`: 只看 no-tool 任务，完全不调用工具且无 invalid call 才算正确。
- `unnecessary_tool_call_rate`: no-tool 任务中误调用工具的比例。
- `skill_sequence_acc`: single-skill 要包含 gold skill，multi-skill 要按顺序覆盖全部 gold skills。
- `under_call_rate`: multi-skill 任务中漏调或少调 skill 的比例。
- `strict_task_success_rate`: 同时要求无 invalid call、skill sequence 正确、final answer 包含关键结果；no-tool 任务还要求不调用工具。

旧的 `task_success_rate` 保留，用来观察规则关键词评测可能带来的高估。

## Commands

```powershell
.\.venv\Scripts\python.exe run.py --retriever full --max_tasks 120 --output results\run_full_120.jsonl
.\.venv\Scripts\python.exe run.py --retriever bm25 --top_k 5 --max_tasks 120 --output results\run_bm25_120.jsonl
.\.venv\Scripts\python.exe run.py --retriever embedding --top_k 5 --max_tasks 120 --output results\run_embedding_120.jsonl

.\.venv\Scripts\python.exe -m eval.evaluate --input results\run_full_120.jsonl
.\.venv\Scripts\python.exe -m eval.evaluate --input results\run_bm25_120.jsonl
.\.venv\Scripts\python.exe -m eval.evaluate --input results\run_embedding_120.jsonl

.\.venv\Scripts\python.exe scripts\compare_runs.py --inputs results\run_full_120.jsonl results\run_bm25_120.jsonl results\run_embedding_120.jsonl --output results\compare_results_120.csv

.\.venv\Scripts\python.exe scripts\analyze_failures.py --input results\run_full_120.jsonl
.\.venv\Scripts\python.exe scripts\analyze_failures.py --input results\run_bm25_120.jsonl
.\.venv\Scripts\python.exe scripts\analyze_failures.py --input results\run_embedding_120.jsonl
```

## Main Results

| Method | Recall@5 | Selection Acc | Need Tool Acc | No-tool Acc | Unnecessary Tool Call | Sequence Acc | Under-call | Lenient Task Success | Strict Task Success | Invalid Call | Avg Steps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Full | 100.00% | 11.67% | 84.17% | 0.00% | 95.00% | 11.67% | 95.00% | 79.17% | 10.00% | 0.83% | 1.21 |
| BM25 | 91.50% | 45.00% | 82.50% | 0.00% | 100.00% | 44.17% | 82.50% | 90.00% | 40.00% | 0.83% | 1.08 |
| Embedding | 93.50% | 53.33% | 82.50% | 0.00% | 100.00% | 50.83% | 70.00% | 88.33% | 46.67% | 0.83% | 1.14 |

结果文件：

- `results/run_full_120.jsonl`
- `results/run_bm25_120.jsonl`
- `results/run_embedding_120.jsonl`
- `results/metrics_run_full_120.csv`
- `results/metrics_run_bm25_120.csv`
- `results/metrics_run_embedding_120.csv`
- `results/compare_results_120.csv`

## Key Findings

1. Retrieval 变得更有区分度，但仍不是最大瓶颈。
   Full Prompt 的 Recall 是 100%，但 Selection Acc 只有 11.67%。BM25 和 Embedding 的 Recall 分别是 91.50% 和 93.50%，说明扩展 benchmark 后检索已经不再完全 trivial，但 skill selection 和 tool-use decision 的问题更明显。

2. Full Prompt 候选太多，反而明显伤害 skill selection。
   Full Prompt 把所有 skill 都塞进候选集，Recall 最高，但 Selection Acc、Sequence Acc 和 Strict Success 都最低。这支持后续继续使用 retriever 缩小候选空间。

3. No-tool 是当前最差环节。
   三种方法的 No-tool Acc 都是 0%。BM25 和 Embedding 在 20 条 no-tool 任务上全部误调用工具，Full Prompt 也误调用了 19 条。这说明必须加入 NEED_TOOL / NO_TOOL 前置判断。

4. Multi-skill under-call 很严重。
   Under-call Rate: Full 95.00%，BM25 82.50%，Embedding 70.00%。即使检索到了候选 skill，模型也经常只调用一个 skill，或调用了错误组合。

5. 旧规则 Task Success 明显高估。
   BM25 的 Lenient Task Success 是 90.00%，但 Strict Task Success 只有 40.00%；Embedding 是 88.33% vs 46.67%。这说明只看关键词或数字命中不够，需要保留严格评测。

6. Embedding 是当前表现最好的 baseline。
   Embedding 的 Selection Acc、Sequence Acc、Strict Task Success 都最高，Under-call Rate 也最低。BM25 更轻量稳定，可以作为本地快速实验 baseline；Embedding 更适合作为后续主对比 baseline。

## Failure Counts

| Method | Retrieval Failure | Selection Failure | No-tool Overcall | Multi-skill Under-call | Wrong Order | Invalid Call | Execution Failure | Final Answer Hallucination | Total Failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Full | 0 | 49 | 19 | 38 | 0 | 1 | 1 | 0 | 108 |
| BM25 | 15 | 11 | 20 | 19 | 1 | 1 | 1 | 4 | 72 |
| Embedding | 11 | 5 | 20 | 19 | 3 | 1 | 1 | 4 | 64 |

失败分析文件：

- `results/failure_cases_run_full_120.json`
- `results/failure_cases_run_bm25_120.json`
- `results/failure_cases_run_embedding_120.json`

## Typical Failure Cases

1. `task_013`, retrieval failure, BM25
   Gold skill 是 `summarizer`，但 BM25 top-5 没有召回 summarizer，模型调用了 `json_validator`。说明相似或格式类 skill 会干扰文本任务检索。

2. `task_004`, skill selection failure, BM25
   Gold skill 是 `translator_zh_en`，候选中同时有 `translator_en_zh` 和 `translator_zh_en`，模型选错方向。说明 translation direction 需要更强 prompt 或 schema 约束。

3. `task_026`, no-tool overcall, BM25
   任务只是解释 benchmark 为什么要包含 easy/hard tasks，但模型调用了 `readability_scorer`。说明当前 Agent 缺少可靠的 NO_TOOL 停止机制。

4. `task_017`, multi-skill under-call / wrong skill selection, BM25
   任务要求先中译英，再提取关键词。模型调用了 `translator_en_zh` 和 `keyword_extractor`，方向错误导致后续 observation 也不可靠。

5. `task_100`, wrong skill order, BM25
   Gold sequence 是 `title_generator -> keyword_extractor`，模型实际调用 `keyword_extractor -> title_generator`。说明 multi-step 任务需要先规划步骤，而不是逐步贪心选择。

6. `task_068`, invalid call, BM25
   Gold skill 是 `csv_summarizer`，候选已召回，但模型没有形成有效调用，直接生成了 final answer。说明 JSON action parsing 和 fallback 仍需加强。

7. `task_032`, execution failure, BM25
   任务是计算 80 增加 25%，模型只把 `80` 传给 `percentage_calculator`，导致 skill 返回参数不足错误。说明 skill calling 不只是选 skill，还要正确构造 input。

8. `task_002`, final answer hallucination, BM25
   `unit_converter` 返回 unsupported conversion，但模型 final answer 生成了 `10 cm = 0 m`。说明 final answer prompt 需要要求忠实使用 observation，不能改写错误 observation 为虚假答案。

## Next Steps

1. 实现 NEED_TOOL / NO_TOOL 前置判断。
   在选具体 skill 前先让模型输出 `{ "need_tool": true/false }`，并加入 few-shot no-tool negative examples。

2. 增加 multi-skill planner。
   先生成最多 2 步的 skill plan，再逐步调用，评估 Skill Sequence Accuracy 和 Under-call Rate 是否改善。

3. 强化 action input 构造。
   对 percentage、unit conversion、regex、csv 等 skill 增加更明确的 input schema 和示例。

4. 加强 final answer grounding。
   如果 observation 是 error 或 unsupported，应让 final answer 明确报告失败，而不是编造结果。

5. 继续文献线。
   重点看 MetaTool、ToolBench、API-Bank、StableToolBench 中的 no-tool、wrong tool、tool-use decision 和 tool sequence 评测设定。
