# EdgePilot Stage 6 — Hybrid architecture, Pareto trade-offs, break-even

**Person 2 handoff.** This is an **additive** Stage 6 upgrade for a Stage 5 project. It does not replace the existing `recommender.py`, `explain.py`, `scenarios.py`, benchmark records, `.env`, or the four-tier decision process.

## Scope and evidence rules

1. The primary recommendation and scores continue to cover **on_device, far_edge, regional_edge, cloud**. Stage 6 does not add "hybrid" as a fifth tier.
2. The Pareto frontier uses only **application end-to-end latency in milliseconds** and **monthly cost in INR**, with independent evidence sources. It never uses `inference_latency_ms` as total latency.
3. The frontier is **partial** when any eligible tier lacks either comparable metric. If inputs are estimated, the frontier is provisional. Demo fixtures are synthetic.
4. Hybrid is a **candidate requiring validation**, not a verified deployable architecture. It requires explicit remote-processing permission, local model memory fit, a working network, and an eligible remote tier. Its local inference must function independently of optional remote analytics. Never claim an unverified privacy/anonymity guarantee.
5. Break-even uses **separately supplied, workload-matched linear curves**, not the one-point monthly cost estimate. It is an approximation unless Person 3 has independently verified the unit economics and limits. The calculated curve values are **not fed back automatically** into the four-tier suitability ranking.
6. No cloud deployment, model execution, purchases, or infrastructure changes are performed by this module.

## Install

From the `edgepilot_person2_handoff` project root (existing venv), after downloading the ZIP:

```bash
unzip -n ~/Downloads/edgepilot_stage6_optimization_patch.zip -d .
python3 -m unittest discover -s tests -v
```

The ZIP only adds `ai_engine/optimization.py`, `ai_engine/optimization_cli.py`, `tests/test_stage6_optimization.py`, example JSON, this document, and the Stage 6 cost-curve JSON Schema. It does not replace existing files. It is designed for the Stage 5 patch. The integrated test suite has 158 tests (128 existing + 30 new) in the verified project snapshot; local totals may differ if you've added tests.

## Example command: complete Stage 6 analysis

```bash
python3 -m ai_engine.optimization_cli \
  --input examples/stage6_hybrid_request_DEMO.json \
  --benchmark-dir benchmarks \
  --metrics examples/stage6_pareto_tradeoff_metrics_DEMO.json \
  --cost-curves examples/stage6_cost_curves_DEMO.json \
  > /tmp/stage6_result.json
```

View concise results:

```bash
python3 - <<'PY'
import json
r = json.load(open('/tmp/stage6_result.json'))
o = r['details']['optimization']
print('Core recommendation:', r['recommended_tier'])
print('Qualcomm benchmark:', r['details']['benchmark']['status'])
print('Pareto:', o['pareto']['status'], o['pareto']['non_dominated_tiers'])
print('Hybrid:', o['hybrid']['status'], o['hybrid'].get('remote_analytics_tier'))
print('Cheapest modeled at reference volume:', o['cost_break_even']['cheapest_eligible_at_reference'])
for x in o['cost_break_even']['pairwise_break_even_points']:
    if x['tiers'] == ['on_device','far_edge']:
        print('Modeled break-even on-device/far edge:', x['monthly_requests'])
PY
```

The intentionally synthetic examples illustrate trade-offs. Expected: S25 MobileNetV2 benchmark matched, Pareto `provisional_estimates` (and possible `contains_demo_inputs=true`), hybrid `candidate_requires_validation`, a modeled on_device/far_edge crossover near 8,571.43 monthly requests. This is not an actual price quote or observed deployment threshold.

### Show missing-data safety

```bash
python3 -m ai_engine.optimization_cli \
  --input examples/stage6_hybrid_request_DEMO.json \
  --benchmark-dir benchmarks \
  > /tmp/stage6_no_metrics.json
```

The Pareto status must be `insufficient_comparable_data` and break-even `not_available` with no invented numbers.

### Show hybrid policy safety

Copy `stage6_hybrid_request_DEMO.json` and change `"allow_remote_processing": true` to `false`. The `details.optimization.hybrid.status` must change to `not_proposed`.

## Person 3 — stable Python integration

```python
from ai_engine.optimization import optimize_deployment, analyze_optimization

# Direct end-to-end call; include matching Stage 3 cost/latency metrics.
result = optimize_deployment(
    request_json,
    benchmark_catalog=benchmark_catalog,
    metrics_by_tier=cost_latency_metrics_for_the_request,
    cost_curves=curves_for_the_same_workload,  # or omit
)

# Alternative when the existing backend has already calculated the recommendation:
optimization = analyze_optimization(
    request_json,
    already_calculated_recommendation,
    cost_curves=curves_for_the_same_workload,
)
already_calculated_recommendation['details']['optimization'] = optimization
```

Suggested optional `POST /api/optimize` endpoint. Or add `details.optimization` to the existing `/api/recommend` response. **Person 3 owns routing, authentication, rate limiting, quote sourcing, cost-model assumptions, network modeling, data residency verification, and caching.**

### Person 3 cost curve contract

See `schemas/stage6_cost_curves.schema.json` and `examples/stage6_cost_curves_DEMO.json`.

Top-level:

- `scenario_id`: stable provenance identifier for the Person 3 cost model.
- `workload_match`: equality match to present workload identifiers (e.g. application/model/device/runtime/precision). Reject mismatches rather than reusing stale costs.
- `reference_monthly_requests`: explicit monthly volume. **Do not infer monthly requests from concurrent users.**
- `tiers`: any subset of the four required tiers, each containing:
  - `fixed_monthly_inr`: fixed INR per month.
  - `per_1000_requests_inr`: variable INR per thousand requests.
  - `min_monthly_requests`, `max_monthly_requests`: range in which the pricing model applies.
  - `source`: `estimated`, `quoted`, or `measured` with `source_reference` and assumptions (mandatory for estimated).

For volume `N`, monthly cost `C(N) = fixed_monthly_inr + per_1000_requests_inr * N / 1000`. Pairwise intersections outside common valid ranges are excluded. An intersection is **not necessarily the volume at which an alternative becomes the global cheapest**, because other tiers may exist. Price sources must be comparable (same geographic region, included service features, tax handling, billing period, utilization assumption). No cloud, energy, or device hardware pricing is guessed by Person 2.

## Person 1 — UI integration

Read `response.details.optimization`:

- `pareto.non_dominated_tiers` + `pareto.compared_tiers`: plot latency vs cost scatter **with provenance labels**. Show `status` and explain missing data. The display is provisional whenever any input is an estimate.
- `hybrid.nodes` + `hybrid.connections`: render optional architecture in React Flow, distinct from the original `response.architecture`. Show `validation_checks` and make the async analytics path visually optional.
- `cost_break_even.pairwise_break_even_points`: mark candidate intersections on a cost-vs-volume line chart; always display `valid_volume_range` and source disclaimer.
- `cost_break_even.estimated_cost_at_reference_inr`: show modeled values at the supplied monthly volume, not provider invoices.
- `recommended_tier` / `scores` remain authoritative for the four-tier result. Do **not** color a hybrid candidate as a verified winning tier.

## How to combine with Stage 4 and 5

- Stage 4: show LLM explanation in an independent section via `explain_recommendation(...)`. Stage 6 calculations are deterministic and do not generate new natural-language numerical claims.
- Stage 5: when hardware, traffic, model, or network conditions change, regenerate Person 3 metrics **and cost curves** before running Stage 6. Reusing stale curve data is prohibited; mismatched workload identifiers are rejected, and request volume is independently supplied.
- New Stage 6 metadata is additive; original JSON keys remain unchanged.

## Acceptance checks

1. Existing Stage 1-5 tests still pass.
2. Pareto dominated vs nondominated matches the hand-calculated example, including missing-data behavior.
3. Hybrid is disabled when remote processing is prohibited, network is unavailable, or local memory is insufficient.
4. S25's 0.45 ms measured **inference-only** benchmark is preserved without being mislabeled as E2E.
5. Break-even uses only declared curves and rejects mismatched model/device identifiers, invalid prices, bad intervals, and undocumented estimated sources.
6. No API keys or `.env` in the ZIP. No additional dependencies for these modules.
