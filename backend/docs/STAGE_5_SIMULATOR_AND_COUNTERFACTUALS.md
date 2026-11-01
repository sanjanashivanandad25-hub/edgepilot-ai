# Stage 5 — Scenario Simulator & Counterfactual Sensitivity

**Scope:** Additive Person 2 Python implementation; no API server, frontend, secrets, live model call, or cloud configuration is changed by this patch.

## What it adds

- `ai_engine/scenarios.py` — before vs after recommendation with **actual reranking**, feasibility transitions, score deltas, benchmark matching, and provenance-aware evidence handling.
- `ai_engine/counterfactuals.py` — sampled **one-variable-at-a-time** changes that truly switch the winner. No LLM or fabricated thresholds.
- `ai_engine/scenario_cli.py` — local demonstration entrypoint; optionally generate one Qualcomm explanation for the final scenario, never for every sensitivity sample.
- `tests/test_stage5_simulation.py` — repeatable, offline tests for regression, constraints, evidence invalidation, and flips.
- `examples/request_stage5_s25_hardware.json`, `examples/stage5_changes_*.json`, and demo metric file for local examples.

Your Stages 1–4 files are not replaced. Your private `.env`, actual S24/S25 evidence records, and custom Person 3 metrics are untouched.

## Installation

From `~/Desktop/edgepilot_person2_handoff` with your existing venv enabled:

```bash
# Recommended: create a source-control checkpoint first.
git status --short
# Download ZIP into ~/Downloads, then:
unzip -n ~/Downloads/edgepilot_stage5_what_if_patch.zip -d .
python3 -m unittest discover -s tests -v
```

If files already exist because you've applied this patch, use `unzip -l` to inspect first. `-n` avoids overwriting existing files.

The original Stage 4 project with Stage 5 patch passes 128 tests (96 pre-existing + 32 new tests).

## Example A — a genuine tier switch driven by RAM insufficiency

```bash
python3 -m ai_engine.scenario_cli \
  --input examples/request_stage5_s25_hardware.json \
  --changes examples/stage5_changes_memory_drop.json \
  --benchmark-dir benchmarks \
  --metrics examples/stage3_illustrative_metrics.json \
  --find-flips --fields device_available_ram_mb \
  > /tmp/edgepilot_stage5_memory.json
```

Print a compact summary:

```bash
python3 - <<'PY'
import json
r = json.load(open('/tmp/edgepilot_stage5_memory.json'))
c = r['comparison']
print('Old tier:', c['original_tier'])
print('New tier:', c['new_tier'])
print('Changed:', c['recommendation_changed'])
print('Feasibility changes:', list(c['feasibility_changes']))
print('Evidence handling:', c['metrics_handling']['mode'])
print('First sampled flip:', r['counterfactuals']['flips'][:1])
PY
```

Expected on the shipped demonstration profiles: initial `on_device`, revised `far_edge`, with on-device marked infeasible due to the declared memory shortfall. The demo memory requirement (256 MB) and available RAM (1024 MB initially, 128 MB afterward) are **illustrative inputs, not measured MobileNetV2 requirements**. Scores for all tiers are recalculated; **the scenario's old cost/E2E latency estimates are intentionally invalidated** because hardware changed.

## Example B — network outage

```bash
python3 -m ai_engine.scenario_cli \
  --input examples/request_stage5_s25_hardware.json \
  --changes examples/stage5_changes_network_outage.json \
  --benchmark-dir benchmarks \
  --metrics examples/stage3_illustrative_metrics.json \
  > /tmp/edgepilot_stage5_network.json
```

Remote tiers become infeasible because the scenario explicitly sets the network unavailable. **The winner need not change** if on-device already ranked first; the meaningful changes are the feasibility transitions and risks.

## Example C — changing budget (safe to reuse previously supplied cost estimates)

```bash
python3 -m ai_engine.scenario_cli \
  --input examples/request_stage5_s25_hardware.json \
  --changes examples/stage5_changes_cost_budget.json \
  --benchmark-dir benchmarks \
  --metrics examples/stage3_illustrative_metrics.json \
  > /tmp/edgepilot_stage5_budget.json
```

This changes the scoring against the new budget, but **does not fabricate new prices**. Old estimated costs are reused because deployment parameters did not change. An estimated budget violation changes scoring; it is not an observed/quoted hard constraint.

## Example D — network degraded + FRESH hypothetical model estimates

```bash
python3 -m ai_engine.scenario_cli \
  --input examples/request_stage5_s25_hardware.json \
  --changes examples/stage5_changes_network_degraded.json \
  --benchmark-dir benchmarks \
  --metrics examples/stage3_illustrative_metrics.json \
  --scenario-metrics examples/stage5_degraded_network_metrics_DEMO.json \
  > /tmp/edgepilot_stage5_degraded.json
```

This **separately supplied** scenario-specific metrics record models higher remote latency. It is labeled `estimated` and `SYNTHETIC`; it is not a live network measurement, cost quote, or Qualcomm profiling result.

If you omit `--scenario-metrics`, the old tier estimates are dropped (shown as unknown) because they are no longer credible for the new conditions. Person 3 needs to implement the calculations that produce these new estimates.

## Optional: one Qualcomm explanation of the new recommendation

```bash
set -a && source .env && set +a
python3 -m ai_engine.scenario_cli \
  --input examples/request_stage5_s25_hardware.json \
  --changes examples/stage5_changes_memory_drop.json \
  --benchmark-dir benchmarks \
  --qualcomm > /tmp/edgepilot_stage5_qualcomm.json
```

`--qualcomm` calls the existing Stage 4 grounded explainer **once for the final scenario**. All counterfactual scans run with no LLM calls. Use throttling/caching for public APIs; keep credentials server-side.

## Person 3 — Backend integration

```python
from ai_engine.scenarios import simulate_scenario
from ai_engine.counterfactuals import discover_flips
from ai_engine.benchmark_registry import read_catalog

catalog = read_catalog('benchmarks')  # load once, refresh only when records change

report = simulate_scenario(
    payload=request_json,              # original agreed {"workload": {...}}
    changes={"device_available_ram_mb": 128},
    benchmark_catalog=catalog,
    metrics_by_tier=original_metrics,   # Person 3's original E2E / cost evidence
    scenario_metrics_by_tier=None,     # or Person 3 recomputed scenario-specific metrics
)

flips = discover_flips(
    request_json,
    benchmark_catalog=catalog,
    metrics_by_tier=original_metrics,
    fields=['device_available_ram_mb', 'latency_requirement_ms', 'privacy_requirement'],
    max_evaluations=40,
    max_results=5,
)
```

Suggested (NOT automatically created) endpoints:

- `POST /api/simulate`: accepts `{ "request": {"workload":{...}}, "changes":{...}, "metrics_by_tier":{...} | null, "scenario_metrics_by_tier":{...} | null }` and returns `simulate_scenario(...)`.
- `POST /api/counterfactuals`: accepts `{ "request":{...}, "fields":[...], "target_tier":"cloud" | null }` and returns `discover_flips(...)`.

Do not let browser clients arbitrarily mark metrics as `measured` or `quoted`: those fields should come from controlled backend evidence pipelines. Validate payload size, rate-limit expensive searches, and hide Qualcomm credentials. Reuse a cached benchmark catalog. For sliders, call simulator without `llm` and debounce to avoid spamming Qualcomm.

**Existing `POST /api/recommend` contract stays unchanged.** The Stage 5 schema is additive.

## Person 1 — Frontend integration

Read the following fields from the result:

- `baseline` — complete original recommendation, including scores and architecture.
- `scenario` — complete recomputed recommendation.
- `comparison.original_tier`, `.new_tier`, `.recommendation_changed`.
- `comparison.changed_inputs` — show which sliders changed.
- `comparison.score_deltas[tier].before/after/delta` — four-tier bar comparison.
- `comparison.feasibility_changes[tier]` — badges like **excluded: insufficient RAM**.
- `comparison.metrics_handling.mode` — display **reused / invalidated / freshly recalculated** indicator.
- `comparison.explanation`, `.limitations` — confidence/provenance caveats.
- Optional `counterfactuals.flips[]` — clickable tested candidate configurations.

The response is designed to fit the existing dashboard without inventing metrics. Do **not** label heuristic rankings "confidence" percentages.

## Safety and methodological rules

1. Simulations are **hypothetical**, not actions that modify deployed infrastructure.
2. Changes to model, device, input scale, network, or available device memory **invalidate old workload-specific tier metrics** unless Person 3 supplies fresh scenario metrics. Privacy, deadline, and budget preference changes may reuse relevant existing measurements.
3. Qualcomm S25 MobileNetV2 **0.45 ms is model inference only**, not entire-application latency, and matching is exact across model, device, runtime, and precision.
4. Candidates found by sensitivity search are **sampled flips**, not minimal thresholds or proof that other combinations cannot flip.
5. Unknown E2E performance and cost remain `null` when no credible updated estimate is available.
6. The LLM is used to explain an already-computed recommendation; it **never changes ranking**.
7. A model/device RAM exclusion is a declared engineering assumption until available RAM and runtime memory need are actually verified for that specific workload.

## Next stage

Stage 6: architecture advisor (hybrid task partitioning) and multi-objective Pareto comparisons when comparable metric data is available. Keep four mandatory deployment tiers as primary ranked choices.
