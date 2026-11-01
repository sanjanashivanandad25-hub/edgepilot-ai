# Phase 3 — Evidence capture and score calibration (Person 2)

## First pass: publishable, source-backed on-device profiling data

1. In a separate Python environment if needed, `python3 -m pip install qai-hub-models-cli`.
2. Inspect: `qai-hub-models info mobilenet_v2`.
3. Retrieve: `qai-hub-models perf mobilenet_v2`.
4. Preserve output: `mkdir -p benchmarks && qai-hub-models perf mobilenet_v2 > benchmarks/mobilenet_v2_published.txt`.
5. Select one result and note **model version, exact device/chipset, runtime, precision, inference latency, source URL or source report, and retrieval date**. Convert microseconds to milliseconds if needed (divide by 1000). Do NOT guess.
6. Record: `python3 scripts/record_profile.py`. The prompted values must match the same model/device/runtime benchmark row.
7. Verify engine acceptance: `python3 -m ai_engine.cli --input examples/request_v1.json --metrics benchmarks/tier_metrics.json`.
8. Run tests: `python3 -m unittest discover -s tests -v`.

The writer creates:
- `benchmarks/mobilenet_v2_evidence.json`: full provenance (model, device, runtime, precision, measurement, original source reference).
- `benchmarks/tier_metrics.json`: exact per-tier JSON accepted by the recommendation engine.

**Important**: The `inference_latency_ms` record is evidence of the model running on a specific device, NOT a guarantee for all apps, and does not set `estimates.latency_ms` or determine whether a 50 ms end-to-end requirement is satisfied. Never use a published benchmark for a different model/device as if measured for the user's workload.

## Optional deeper measurement: your own Workbench job

Qualcomm AI Hub Workbench is a separate developer service from the hosted Cloud AI Playground. If you have a Workbench account:

1. Create or retrieve token at https://workbench.aihub.qualcomm.com/ → Account → Settings → API Token.
2. Use Python 3.10 environment. `python3 -m pip install qai-hub` (or from Qualcomm's recommended environment).
3. `qai-hub configure --api_token <TOKEN>` (do not store token in source control). Protect shell history.
4. `qai-hub list-devices`.
5. If you want to submit a new model profiling job, follow the current official recipe in https://workbench.aihub.qualcomm.com/docs/hub/getting_started.html . Submit a compile/inference/profile job, capture its job URL, and inspect its profile result. This route can take account quota and compute resources. Don't submit a job without understanding provider costs/limits.
6. Run the record script again, with `source_type=qualcomm_workbench` and the actual job URL/ID, and preserve your profile log.

## Towards benchmark-informed recommendation changes

Ask Person 3 for scenario-specific measurements or transparently modeled estimates in INR and ms, with source provenance. For each tier:

- `latency_ms`: end-to-end application latency under same request/payload conditions; can change score, and if marked `measured` and exceeds mandatory deadline, blocks option.
- `monthly_cost_inr`: projected recurring cost for a stated usage volume; affects affordability score. Prices should include cloud transfer and hardware costs as appropriate.
- `model_compatible`: boolean only when actually verified for the specific model/target.

These go into the **same tier_metrics.json**, with `source` one of `measured`, `quoted`, or `estimated`, plus explicit `source_note`. Source is per tier in the current schema; do not put mixed measured-inference and estimated-monthly-cost data in the same tier record without agreeing on a provenance/schema extension.

For basic Phase 3, the proven Qualcomm on-device benchmark and an explicit unmeasured/modeled label for remote tiers are sufficient. Document that rankings are still primarily illustrative heuristics.
