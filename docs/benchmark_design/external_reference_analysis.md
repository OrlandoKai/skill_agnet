# External Reference Benchmark Analysis

This note summarizes small reference files downloaded under `data/external_references/` and proposes the next SkillBench split design.

## Downloaded References

### MetaTool
- `all_clean_data.csv`: rows/items/chars=20614; columns/keys: Query, Tool
- `multi_tool_query_golden.json`: rows/items/chars=497; columns/keys: query, tool
- `plugin_des.json`: rows/items/chars=199
- `plugin_info.json`: rows/items/chars=390
- Takeaway: Useful for tool-use awareness, similar-tool selection, and multi-tool query design.
- Takeaway: Plugin/tool descriptions are reusable as inspiration for richer skill contracts.

### BFCL
- `BFCL_v4_irrelevance.json`: rows/items/chars=240; columns/keys: function, id, question
- `BFCL_v4_multi_turn_miss_func.json`: rows/items/chars=200; columns/keys: excluded_function, id, initial_config, involved_classes, missed_function, path, question
- `BFCL_v4_multi_turn_miss_param.json`: rows/items/chars=200; columns/keys: excluded_function, id, initial_config, involved_classes, path, question
- `BFCL_v4_multiple.json`: rows/items/chars=200; columns/keys: function, id, question
- `BFCL_v4_simple_python.json`: rows/items/chars=400; columns/keys: function, id, question
- Takeaway: BFCL-style categories should be adopted directly as SkillBench-Hard slices.
- Takeaway: Irrelevance and missing parameter cases are stronger than generic no-tool chat.

### API-Bank
- `all_apis.csv`: rows/items/chars=101; columns/keys: id, 类型, 应用场景, API名称, 参数, 路径, 类名, input_parameters
- `Calculator-level-1-1.jsonl`: rows/items/chars=4; columns/keys: role, text
- `Calculator-level-3-1.jsonl`: rows/items/chars=5; columns/keys: role, text
- `Calculator-QueryHistoryToday-level-2-1.jsonl`: rows/items/chars=8; columns/keys: role, text
- `Translate-level-1-1.jsonl`: rows/items/chars=4; columns/keys: role, text
- `Meeting Schedule.txt`: rows/items/chars=888
- Takeaway: API-Bank's level-1/2/3 split maps cleanly to single skill, retrieve+call, and plan+call.
- Takeaway: Dialogues include API call traces, useful for expected skill sequence and argument checks.

### MTEB ToolBench retrieval
- `ToolBench-corpus.parquet`: rows/items/chars=13862; columns/keys: id, text, title
- `ToolBench-qrels.parquet`: rows/items/chars=2629; columns/keys: query-id, corpus-id, score
- `ToolBench-queries.parquet`: rows/items/chars=1100; columns/keys: id, text
- Takeaway: Useful as a lightweight retrieval reference: query, corpus/tool documents, and qrels.
- Takeaway: Can guide skill_library description style and query-tool relevance labeling.

## Recommendation

**Decision:** Keep current 120-task SkillBench-Mini as SkillBench-Dev seed, then expand to 240 Dev / 120 Hard / 80 Hidden.

Do **not** replace the current benchmark. Rename/freeze it as the Dev seed and expand around it.

### Why Keep Current Data
- The current 120 tasks preserve experiment continuity and already expose baseline-to-enhanced progress.
- Replacing them would destroy comparability with existing Full/BM25/Embedding/Enhanced V2 results.

### Why Expand
- External benchmarks emphasize missing parameters, irrelevance/no-tool, multi-call planning, and argument correctness.
- The current held-out set is useful but still partly template-like and too small for final claims.

## Proposed Splits

### SkillBench-Dev (240 tasks)
- Source: Current 120 tasks + 120 new development tasks.
- Use: Prompt/rule development and ablation debugging.
- single_skill: 100
- multi_skill: 70
- no_tool: 40
- missing_info_or_unsupported: 30

### SkillBench-Hard (120 tasks)
- Source: Fresh tasks adapted from external benchmark categories, not copied.
- Use: Main reported benchmark.
- single_skill_minimal_pair: 30
- argument_heavy_single_skill: 25
- implicit_multi_skill: 30
- hard_no_tool_irrelevance: 20
- missing_info_or_unsupported: 15

### SkillBench-Hidden (80 tasks)
- Source: Final frozen test set written after method design.
- Use: One-shot final generalization check.
- single_skill: 25
- multi_skill: 25
- no_tool: 15
- missing_info_or_unsupported: 15

## Design Principles for New Tasks

- Use external benchmark categories, but rewrite every task for the local 40-skill library.
- Add `expected_checks` to every tool task: arguments, observations, final answer, and faithfulness.
- Include minimal pairs where surface wording is similar but gold skills differ.
- Include irrelevance and missing-argument cases where the correct behavior is `NONE` or clarification.
- Avoid optimizing the agent on Hard/Hidden; use Dev only for rule and prompt iteration.