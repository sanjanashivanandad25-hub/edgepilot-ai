# Stage 1 — Safe, exact benchmark matching

This is an **additive patch**. It does NOT overwrite your existing recommender,
CLI, Qualcomm adapter, tests, `.env` or benchmark evidence files.

## File placement

From your existing project root (`edgepilot_person2_handoff/`) extract the patch.
It contains these NEW files:

- `ai_engine/benchmark_registry.py` — loads reviewed Qualcomm evidence records.
- `ai_engine/benchmarked.py` — enriched entrypoint, preserving the original API.
- `ai_engine/benchmark_cli.py` — test CLI with auto benchmark selection.
- `tests/test_benchmark_registry.py` — eight tests.
- `examples/request_s25_match.json`, `examples/request_unmatched_benchmark.json`.
- `docs/STAGE_1_BENCHMARK_MATCHING.md`.

## Existing evidence required

These are YOUR previously created data files; the patch will not create or change them:

```
benchmarks/mobilenet_v2_evidence.json
benchmarks/mobilenet_v2_s25_workbench_evidence.json
```

The Workbench S25 evidence file must use a *plain* URL for `source_reference`, e.g.
`https://workbench.aihub.qualcomm.com/jobs/jp8r0e0xg/`, not markdown `[text](url)`.

If your evidence files have different names, rename them to end with `_evidence.json`.

## Run and verify

```
python3 -m unittest discover -s tests -v
python3 -m ai_engine.benchmark_cli --input examples/request_s25_match.json --benchmark-dir benchmarks > /tmp/s25_match.json
python3 -m ai_engine.benchmark_cli --input examples/request_unmatched_benchmark.json --benchmark-dir benchmarks > /tmp/unmatched.json
```

Inspect result safely:

```
python3 - <<'PY'
import json
for filename in ['/tmp/s25_match.json', '/tmp/unmatched.json']:
    with open(filename) as file: r=json.load(file)
    b=r['details']['benchmark']
    print(filename, b['status'], b.get('inference_latency_ms'))
    print('Recommended:',r['recommended_tier'],'End-to-end latency:',r['estimates']['latency_ms'])
PY
```

Expected: S25 => `matched 0.45` (from YOUR file); other_model => `no_match None`.
Scores do not change: inference-only latency does not imply end-to-end latency.

## Person 3 Python integration

```python
from ai_engine.benchmark_registry import read_catalog
from ai_engine.benchmarked import recommend_with_benchmarks

catalog = read_catalog('benchmarks')  # load at server startup
response = recommend_with_benchmarks(request_json, benchmark_catalog=catalog)
```

The original response keys remain unchanged. Only `details.benchmark` and
`details.benchmark_used_to_score_tier` are added. Person 1 may show the provenance
and model inference time as a separate metric, NEVER as E2E latency.

## What this stage explicitly does NOT do

- It does not compute total latency, prices, or new tier scores from model inference time.
- It does not independently authenticate the published Qualcomm source record.
  Retain the full original catalog output or source link as proof.
- It does not yet pass selected benchmark evidence into the Qualcomm LLM prompt.
  That is Stage 4, and is necessary before AI-generated benchmark explanations.
- Do NOT pass the old pinned `--metrics benchmarks/s25_tier_metrics.json` to this new
  CLI; its point is to select metrics automatically based on the workload.
- The original `python3 -m ai_engine.cli` command remains unchanged.

## Future steps

Stage 2: feasibility + weighted scoring upgrade.
Stage 3: Person 3 E2E latency and cost interface.
Stage 4: evidence-grounded Qualcomm explanations.
Stage 5: what-if simulations and decision boundaries.
Stage 6: hybrid architectures and Pareto analysis.
Stage 7: systematic tests, performance and security.
Stage 8: Person 1 / Person 3 handoff.
