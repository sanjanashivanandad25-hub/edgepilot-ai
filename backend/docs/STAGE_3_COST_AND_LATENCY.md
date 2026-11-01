# EdgePilot — Stage 3: traceable end-to-end latency and monthly cost

Stage 3 is **an extension of your Stage 2 engine**, not a replacement. Existing `recommend(payload, metrics_by_tier=...)` and `recommend_with_benchmarks(...)` remain callable. The required `/api/recommend` contract is unchanged. Additional comparison and provenance data live under `details`.

## Installation

Back up your existing files first, then unzip `edgepilot_stage3_metrics_patch.zip` into the **root** of your working project. You do not need a new virtual environment, Qualcomm token, model job, or hardware profile. This patch has no new dependencies.

## Run tests

```bash
python3 -m unittest discover -s tests -v
```

Expected with Stages 1–3 installed and the original 50 tests intact: `Ran 76 tests` / `OK`.

## Run Stage 3 with both benchmark matching and tier estimates

```bash
python3 -m ai_engine.benchmark_cli \
  --input examples/request_s25_match.json \
  --benchmark-dir benchmarks \
  --metrics examples/stage3_illustrative_metrics.json \
  > /tmp/edgepilot_stage3.json
```

To check the new comparison view:

```bash
python3 - <<'PY'
import json
r = json.load(open('/tmp/edgepilot_stage3.json'))
print('Winner:', r['recommended_tier'])
print('Inference benchmark:', r['details']['benchmark']['status'])
for tier, values in r['details']['tier_estimates'].items():
    print(tier, values['latency_ms'], values['latency_source'],
          values['monthly_cost_inr'], values['cost_source'])
print('Winner provenance:', r['details']['metric_provenance'].get(r['recommended_tier']))
PY
```

**These sample tier estimates are SYNTHETIC DEMONSTRATION VALUES, not provider quotes or real E2E tests. Do not make factual performance or price claims from them.** They exist only to demonstrate the interface and scoring effect.

Your genuine `0.45 ms` Samsung S25 MobileNetV2 Workbench measurement is *model inference only*. It remains in `details.benchmark` separately, never substituted into `estimates.latency_ms` and never directly taken as deployment suitability. The synthetic on-device example explicitly *models* preprocessing and postprocessing alongside a 0.45 ms inference component; the resulting total remains an **estimate** until tested end-to-end.

## Person 3: metric evidence interface

`metrics_by_tier` is a dictionary keyed by `on_device`, `far_edge`, `regional_edge`, and `cloud`. Each tier may supply end-to-end latency and monthly cost **independently**:

```json
{
  "regional_edge": {
    "latency_ms": {
      "value": 42,
      "source": "measured",
      "source_reference": "<exact measurement record ID or URL>",
      "method": "end_to_end_instrumented_load_test",
      "scope": "end_to_end",
      "assumptions": []
    },
    "monthly_cost_inr": {
      "value": 870,
      "source": "estimated",
      "source_reference": "<your cost worksheet reference>",
      "method": "monthly_component_sum",
      "scope": "cost",
      "assumptions": ["Requests, hardware amortization and data transfer based on listed inputs"],
      "cost_components_inr": {"compute": 500, "data_transfer": 170, "operations": 200}
    }
  }
}
```

The values in that snippet are format examples, **not live evidence**. Person 3 must generate results for the **selected workload**, based on rates, usage assumptions, and the actual target location. Avoid hardcoded demo prices in production.

Required nested fields per metric:
- `value`: nonnegative monetary amount or positive latency in milliseconds; finite number.
- `source`: `measured`, `quoted`, or `estimated` (`demo` is ignored for scoring).
- `source_reference`: nonempty identifying reference; the module validates presence, not the external truthfulness of the claim.
- `method`: description of measurement, quote, or cost/network model.
- `scope`: `end_to_end` for `latency_ms`, `cost` for `monthly_cost_inr`.
- `assumptions`: list; required to be nonempty for `estimated` values.

Optional breakdown validation:
- `latency_components_ms`: all seven components for remote tiers (`preprocessing`, `upload`, `network_rtt`, `queue`, `inference`, `postprocessing`, `download`); three components for on-device (`preprocessing`, `inference`, `postprocessing`). The sum must equal `value` within ₹/ms rounding tolerance. These are *modeling components*, not necessarily measured individually.
- `cost_components_inr`: arbitrary descriptive categories (`compute`, `network`, `operations`, etc.) whose sum must equal monthly cost. Include depreciation, licensing, operations and data transfer as appropriate. Do not assume all costs are zero when not modeled.

**Crucial model boundaries**:
- Qualcomm inference profile ≠ application end-to-end latency.
- Network RTT, transmission time, queuing, and inference are different contributors. Use RTT once and do not double count network time.
- A *measured or quoted* monthly cost above the budget currently hard-gates the tier under the agreed absolute budget interpretation; an *estimated* price above budget is penalized but not automatically ruled out.
- A *measured* E2E latency above the deadline currently hard-gates the tier; estimated latency above deadline is scored down but not definitively ruled out. For variable networks, prefer percentile latency (e.g. p95) measured under an agreed load and document that method.
- Unit conventions: ms for latency; INR/month for cost. Currency conversion belongs to Person 3, not this module.
- The `source_reference` field is a provenance label, **not cryptographic verification**. Your team must verify providers' evidence manually.

## Backward-compatible v2 input

The following still works and produces the original required response keys:

```python
from ai_engine.recommender import recommend
result = recommend(request_json, metrics_by_tier={
    "cloud": {"source": "estimated", "latency_ms": 80, "monthly_cost_inr": 500,
              "source_note": "legacy source note"}
})
```

New v3 inputs should use one provenance object **per numeric field**. A tier can have `source: mixed` when cost and latency come from different sources.

## Person 1: new display fields (all optional)

Read:
- `details.tier_estimates[tier].latency_ms`, `.latency_source`, `.latency_target_met`, `.latency_target_verified`, `.latency_headroom_ms`
- `details.tier_estimates[tier].monthly_cost_inr`, `.cost_source`, `.budget_met`, `.budget_verified`, `.budget_headroom_inr`, `.cost_to_budget_percent`
- `details.metric_provenance[tier].latency_ms` and `.monthly_cost_inr`, containing `source`, `source_reference`, `method`, `scope`, `assumptions`, optional components
- `details.benchmark` for model inference-only evidence; display separately from latency totals

Render unknown values as `Not available`, not `0`. Show `estimated` / `measured` / `quoted` distinctly and visibly. Display `latency_target_met` as *predicted* vs *verified* using `latency_target_verified` rather than a blanket green check mark.

## What is not yet done

Real local/network E2E sampling, provider-specific pricing and quota limits, source validation, uncertainty intervals, dynamic what-if and sensitivity, hybrid architectures, Pareto analysis, and expanded Qualcomm LLM grounding are later stages. This patch does not fabricate them.

## Handoff to Person 3 (example)

```python
from ai_engine.benchmarked import recommend_with_benchmarks
from ai_engine.benchmark_registry import read_catalog

catalog = read_catalog('benchmarks')
# supply metric evidence generated for each workload, NOT the demo JSON
result = recommend_with_benchmarks(
    request_json,
    benchmark_catalog=catalog,
    metrics_by_tier=metrics_for_this_workload,
    llm=None,  # optional QualcommExplainer after configuration
)
```
