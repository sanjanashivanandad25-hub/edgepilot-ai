# Technical design: Person 2's recommendation algorithm

## The decision pipeline

1. Validate the v1 workload JSON, including all required fields.
2. Accept optional per-tier external figures with a provenance flag (`measured`, `quoted`, `estimated`, or `demo`). Synthetic `demo` figures are NEVER used to calculate recommendations or expose estimates.
3. Apply hard feasibility checks (policy, offline/remote restrictions, network outage, declared minimum bandwidth, device RAM, verified model incompatibility, measured missed latency deadline, quoted budget overruns).
4. Compute 0–100 weighted suitability scores using transparent ordinal profiles; replace heuristic latency/cost factors where independently sourced inputs are available.
5. Apply verified policy and SLA failures as hard exclusions. Estimated SLA misses remain provisional; among tiers with both metrics and no verified failure, select the highest suitability score. Return `null` when metrics are missing or every tier has a verified failure.
6. Construct an architecture graph with connected device and selected inference tier.
7. Generate a deterministic, grounded explanation, optionally polished by Qualcomm-hosted LLM without changing decisions or estimates.
8. Return the agreed response plus optional `details` with score breakdown and exclusion reasons.

## Formula

`score_tier = sum(factor_score * importance_weight) / sum(importance_weights)`

**Importance weights** depend on workload preferences. Strict latency, high privacy, criticality, bandwidth demand, and concurrent users alter the relative contribution of the corresponding factor. Bandwidth demand increases scalability importance; it does not increase data-locality importance. The data-locality profile is neutral across tiers until the workload contract includes a distinct locality requirement. Affordability combines budget fit with a relative cost score across supplied tier costs, so cost differences remain meaningful even when the budget is large. Unknown cost uses a neutral 50/100 prior. All profiles are documented demo priors rather than calibrated evidence.

Factor scores and weight details are returned under `details.score_breakdown` so judges and teammates can audit each result. Scores are suitability indices, **not confidence probabilities**.

### Default ordinal profiles (DEMO ASSUMPTIONS; not benchmarks)

| Tier | Relative latency | Privacy | Data locality | Resilience | Scalability |
|---|---:|---:|---:|---:|---:|
| On-device | 96 | 97 | 60 | 45 | 35 |
| Far edge | 86 | 72 | 60 | 65 | 66 |
| Regional edge | 74 | 65 | 60 | 100 | 85 |
| Cloud | 52 | 48 | 60 | 80 | 98 |

These values are NOT physical milliseconds, security guarantees, or provider prices. Use credible environment-specific data to calibrate and validate before making real deployment decisions. Reliability is especially difficult to infer from tier placement alone; the resilience factor is a qualitative proxy, not a reliability SLA.

### Verified vs estimated vs synthetic

- `measured`: latency from a comparable real end-to-end workload; latency greater than deadline is a hard failure. Inference-only measurement belongs in `inference_latency_ms` and does not trigger hard latency checks.
- `quoted`: written infrastructure price quote; `monthly_cost_inr > budget_monthly` is a hard failure. A quoted latency value is a score input but not treated as a measured hard deadline.
- `estimated`: values adjust scores and support provisional comparison. Estimated misses are marked `provisional_fail`, do not hard-block a tier, and may still lead to a recommendation with a warning. A measured latency miss or measured/quoted cost over budget is a verified hard exclusion.
- `demo`: ignored completely. Never surfaced as an operational prediction.

### Mandatory conditions and unverified conditions

`details.feasibility[tier].eligible` records whether hard policy/evidence excludes a tier. `details.sla_checks[tier].eligible` means both numeric values are within limits; `selectable` means both values are available and no verified failure exists. Estimated failures can therefore be selected provisionally but are clearly distinguished from verified failures. Unknown metrics remain unrankable; no latency or cost is invented.

## Limitations requiring future real-world verification

- Model architecture/runtime compatibility, storage, peak RAM during loading and postprocessing
- Device thermal/power constraints and model accuracy after quantization
- User-to-edge geographic routing, network jitter, peak-load degradation and failure domains
- Price currency conversion, provider egress and recurring equipment/maintenance costs
- Sovereignty and privacy requirements beyond a generic `high|medium|low` level
- True end-to-end reliability and failover (not guaranteed by placement)

## Project definitions for ambiguous contest wording

For this hackathon codebase only: **far edge** means a nearby access-network compute location; **regional edge** means a regional datacenter somewhat farther away but typically offering more capacity. Different vendors sometimes name these layers differently. Agree on this with Person 1/3 and include a legend in the dashboard.
