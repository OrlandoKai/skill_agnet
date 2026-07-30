# External Tool-Use Benchmark References

This folder stores small reference files downloaded from public tool-use and
retrieval benchmarks. These files are for benchmark-design analysis only. They
are not used directly as SkillBench tasks.

## Sources

- `metatool/`: MetaTool reference files for tool-use awareness, tool selection,
  and multi-tool query design.
- `bfcl/`: Selected BFCL v4 files for function calling, irrelevance, missing
  function, and missing parameter categories.
- `api_bank/`: API-Bank API metadata plus several level-1/2/3 examples.
- `mteb_toolbench/`: Lightweight ToolBench retrieval parquet files from MTEB.

## Generated Analysis

- `external_reference_analysis.json`: machine-readable summary.
- `../../docs/benchmark_design/external_reference_analysis.md`: human-readable
  analysis and split recommendation.

## Use Policy

Use these public datasets to borrow evaluation taxonomy and schema ideas, not to
copy tasks verbatim. New SkillBench tasks should be rewritten for the local
40-skill library and should include strict `expected_checks`.
