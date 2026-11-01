# EdgePilot Person 2 — Stage 2: constraint-aware scoring

Stage 2 replaces **five Python source files** while keeping Stage 1 benchmark matching, the Qualcomm adapter, the CLI, and the team request/response contract intact.

## What the patch changes

- `ai_engine/validation.py`: additional strictly validated optional workload fields.
- `ai_engine/metrics.py`: validates tier-specific residency and availability evidence.
- `ai_engine/feasibility.py`: deterministic hard constraints plus a separate list of unknown checks.
- `ai_engine/scoring.py`: transparent weighted decision scoring, with per-factor origins and contribution analysis.
- `ai_engine/recommender.py`: preserves v1 response keys and adds `details.weights`, `details.evidence_gaps`, `details.decision_drivers`, `details.explanation_source`.
- `tests/test_stage2_decision.py`: 20 offline tests covering the changes.

The formula is `score(tier) = sum(weight_i * score_i(tier)) / sum(weight_i)` for hard-constraint-eligible tiers, and zero for tiers excluded by hard constraints. Scores are *heuristic suitability indices* (not calibrated probabilities or benchmarks). A tier can be recommended when both latency and cost are available and neither has a verified violation; estimated misses remain provisional rather than becoming hard exclusions. The highest score wins, with missing metrics left unknown. All criterion profiles are project assumptions and require validation. Tier order in ties is stable.

### Handling unknown values

If **no cost** is supplied for a tier, affordability gets 50/100 (neutral prior) with `origin: unknown_neutral_prior`, *not* an actual predicted cost. No money value is returned in `estimates.monthly_cost`. The default neutral score still influences the ranking; the associated uncertainty is explicit in the response. Stage 3 will improve comparability by providing sourced per-tier estimates.

`latency_ms` in tier metrics means **end-to-end** latency under a comparable workload. `inference_latency_ms` means only time spent running the model and does not change end-to-end score. An E2E *measured* latency beyond deadline is a hard feasibility failure. An *estimated* latency beyond deadline is a `provisional_fail`: it lowers suitability and warns users but does not prove infeasibility. Measured/quoted cost above budget is a verified hard failure; estimated cost above budget remains provisional. Quotes and measurements must be genuine and accurately identified by the integration layer.

### Hard feasibility rules

1. Explicit `allowed_tiers` policy.
2. `require_offline` or `allow_remote_processing: false` excludes remote tiers.
3. `network_available: false` or zero available bandwidth excludes remote tiers.
4. Confirmed insufficient available network bandwidth excludes remote tiers.
5. Confirmed on-device memory shortage excludes the device tier.
6. Evidenced incompatible model/hardware blocks its tier.
7. Measured E2E latency misses a mandatory deadline.
8. Quoted cost exceeds monthly budget.
9. Evidenced data residency mismatch / compliance failure excludes the affected tier.
10. Measured availability falls below explicit `minimum_availability_percent`.

Any unverified requirement stays **unknown**, not automatically feasible or infeasible. `details.feasibility[tier].eligible` means not ruled out by hard policy/evidence checks; `details.sla_checks[tier].eligible` means both numeric latency and cost checks pass; `selectable` identifies tiers with both values and no verified failure, including provisional estimate misses. `details.evidence_gaps[tier]` lists missing evidence. Policy/compliance statements are assumed to be properly sourced from trusted data supplied by Person 3; Stage 2 cannot independently certify compliance.

### New optional request fields

| Field | Example | Meaning |
| --- | --- | --- |
| `application_type` | `smart_camera` | Workload label only (not a verified capability) |
| `model_name` | `mobilenet_v2` | Stage 1 benchmark selector |
| `target_device` | `Samsung Galaxy S25 (Family)` | Stage 1 benchmark selector |
| `runtime` | `tflite` | Stage 1 benchmark selector |
| `precision` | `float` | Stage 1 benchmark selector |
| `allowed_data_regions` | `["IN"]` | Explicit policy: regions where processing is allowed |
| `minimum_availability_percent` | `99.9` | Explicit hard availability threshold, gated by measured availability |

Existing optional fields from Stage 1 remain supported, including RAM, offline/network, allowed tiers, concurrency.

### New optional metrics_by_tier fields

Person 3 may pass these only when supported by a provider, deployment config, or validated monitoring:

```python
{
 "cloud": {
   "source": "quoted", "deployment_region": "IN",
   "data_residency_compliant": True, "monthly_cost_inr": 900,
   "source_note": "Provider quote ID and date"
 },
 "on_device": {
   "source": "measured", "model_compatible": True,
   "availability_percent": 99.95,
   "source_note": "Recorded conditions/date and method"
 }
}
```

Do not invent or present the above EXAMPLE numbers as measurements or actual quotes. `source: demo` records are ignored by the engine. The single source on a tier record applies to its fields; **do not mix cost quotes with unrelated inference measurements**. Stage 3 will introduce a cleaner per-metric source contract.

### API output added in `details`

- `weights`: actual algorithm weights based on workload.
- `score_breakdown.{tier}.{factor}.origin`: `heuristic_profile`, `unknown_neutral_prior`, `measured_end_to_end_latency`, `estimated_monthly_cost`, etc.
- `score_breakdown.{tier}.{factor}.weighted_contribution`: contribution in 0–100 score points.
- `evidence_gaps.{tier}`: mandatory verification missing for the tier, not an exclusion.
- `feasibility.{tier}.verification`: `partial` or `checked` (NOT regulatory compliance certification).
- `decision_drivers`: advantages over runner-up, by factor; interpret negative values as disadvantages.
- `explanation_source`: `deterministic` or `qualcomm_llm` (only indicates a successful adapter return; not that explanation accuracy is certified).
- `method`: `transparent_weighted_heuristic_v3`.
- `sla_checks.{tier}`: numeric pass/fail values, source-aware provisional status, and whether metrics permit provisional ranking.

**Old keys** `recommended_tier`, `scores`, `estimates`, `explanation`, `tradeoffs`, `warnings`, `assumptions`, `architecture` stay unchanged. Stage 1 `details.benchmark` is preserved by `recommend_with_benchmarks()`.

## Install (macOS, from existing project directory)

Make sure you're in `~/Desktop/edgepilot_person2_handoff` and your `.venv` is active. Back up changed files before extracting the patch:

```bash
mkdir -p backup_stage2/ai_engine
cp ai_engine/{validation,metrics,feasibility,scoring,recommender}.py backup_stage2/ai_engine/
# After downloading and examining the ZIP contents:
unzip -o ~/Downloads/edgepilot_stage2_decision_engine_patch.zip -d .
```

To verify:

```bash
python3 -m unittest discover -s tests -v
python3 -m ai_engine.benchmark_cli --input examples/request_s25_match.json --benchmark-dir benchmarks > /tmp/edgepilot_stage2.json
python3 - <<'PY'
import json
r=json.load(open('/tmp/edgepilot_stage2.json'))
print('Recommended:', r['recommended_tier'])
print('Method:', r['details']['method'])
print('Benchmark:', r['details']['benchmark']['status'])
print('Drivers:', r['details']['decision_drivers'][:3])
print('Cost origin:', r['details']['score_breakdown']['on_device']['affordability']['origin'])
print('Missing evidence:', r['details']['evidence_gaps'][r['recommended_tier']])
PY
```

These tests don't require an internet connection or the Qualcomm API key. To smoke-test real LLM after verifying certificate trust and loading your environment variables:

```bash
set -a; source .env; set +a
python3 -m ai_engine.benchmark_cli --input examples/request_s25_match.json --benchmark-dir benchmarks --qualcomm
```

If the LLM fails, the deterministic explanation remains available; inspect `details.explanation_source`.

## Ownership

- Person 2: decision algorithms, rules, benchmark matching, evidence quality, unit tests.
- Person 3: actual per-tier cost and end-to-end latency measurements/estimates with sources; API/routes, persistence and simulation routing.
- Person 1: display infeasible tiers separately from `0/100`, show `null` estimates as *Unknown*, warnings and evidence gaps.

## Next Stage 3

Build a field-specific evidence contract so each metric (`latency_ms`, `monthly_cost_inr`, privacy/residency, model compatibility) can have its own independent provenance, quality and measurement configuration; connect cost / network models from Person 3. Run against comparable workloads; otherwise avoid claiming verified tier superiority.
