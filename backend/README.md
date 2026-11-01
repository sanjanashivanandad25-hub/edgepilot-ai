# EdgePilot AI — Person 2 COMPLETE HANDOFF (decision engine v1)

**Owner: Person 2** · **Consumer: Person 3 / FastAPI** · **Display consumer: Person 1 / React**

This is a working, deterministic placement recommendation library implementing the team's `POST /api/recommend` JSON input/response. It includes documented heuristic scoring, hard constraints, architecture graph output, counterfactual analysis, optional Qualcomm AI-generated reasoning, metric provenance handling, and automated tests.

## Run right now — macOS / VS Code

From the extracted `edgepilot_person2_handoff` directory:

```bash
python3 -m ai_engine.cli --input examples/request_v1.json
python3 -m unittest discover -s tests -v
```

To exercise memory feasibility:

```bash
python3 -m ai_engine.cli --input examples/request_enhanced.json
```

To see that synthetic demo figures are **not used as real latency/cost**:

```bash
python3 -m ai_engine.cli --input examples/request_v1.json --metrics examples/synthetic_metrics_demo.json
```

**No installation needed** for the pure Python engine (Python 3.9+).

## One-line integration for Person 3

```python
from ai_engine.recommender import recommend
result = recommend(request_json)
```

With tier measurements and pricing collected by Person 3:

```python
result = recommend(request_json, metrics_by_tier=tier_metrics)
```

Optional LLM explanation:

```python
from ai_engine.explain import QualcommExplainer
result = recommend(request_json, metrics_by_tier=tier_metrics, llm=QualcommExplainer())
```

**Important**: run FastAPI from a project root where `ai_engine/` is importable (see `docs/TEAM_HANDOFF.md`). Person 3 owns the HTTP endpoint, data gathering, simulator and cost estimator; Person 2 owns scoring, model feasibility, reasoning and graph structure.

## Module tree

```
ai_engine/
  config.py        Example ordinal tier profiles, weights reference, tradeoffs
  validation.py    Required and optional workload fields
  metrics.py       Provenance-checked external per-tier measurements/quotes
  feasibility.py   Hard exclusions
  scoring.py       Transparent weighted suitability score 0–100
  recommender.py   Stable entrypoint; complete response JSON
  architecture.py  React Flow-ready node and connection structure
  explain.py       Deterministic fallback + Qualcomm OpenAI-compatible adapter
  sensitivity.py   Counterfactual 'challenge recommendation' helper
  cli.py           Terminal runner
examples/
  request_v1.json
  request_enhanced.json
  original_team_mock_response.json
  synthetic_metrics_demo.json
  metrics_schema_example.json
schemas/
  request_v1.schema.json
  response_v1.schema.json
tests/
  test_engine.py
 docs/
  TEAM_HANDOFF.md
  SCORING_DESIGN.md
  METRICS_AND_BENCHMARKS.md
  QUALCOMM_SETUP.md
```

## What is finished vs pending

| Item | Status |
|---|---|
| Request JSON validation and v1 response shape | Implemented and tested |
| Rule-based feasibility and 4-tier scoring | Implemented and tested |
| Ranking, factor weights, score breakdown and tradeoffs | Implemented and tested |
| Architecture nodes/connections | Implemented and tested |
| Scenario comparison/counterfactual | Implemented and tested |
| Optional OpenAI-compatible Qualcomm explanation adapter | Implemented, wire format mocked in test |
| Real external Qualcomm key/model/base URL call | **Needs your playground account/credentials; not tested live** |
| Real hardware benchmarks and provider estimates | **Needs measurements and cost input; not fabricated** |
| FastAPI endpoint, simulations, UI | **Person 3 / Person 1** |

## Output considerations

- The exact team v1 response keys are present; an additional optional `details` field contains explainability and feasibility data. If the team insists on exact-only response keys, Person 3 can omit `details` in HTTP serialization while still using it internally.
- `estimates.latency_ms` and `estimates.monthly_cost` are `null` until actual scenario-specific data is supplied. UI should show **Not available**, not `0`.
- A score of `0` on an excluded tier indicates **infeasible**, not a genuine 0-point performance measurement; `details.feasibility` gives the reason.
- `recommended_tier` becomes `null` if nothing is feasible; frontend needs an empty-state screen.
- These suitability scores are **demo ordinal heuristics**, not accuracy/confidence percentages, validated device benchmarks, or predicted response times.

Start with **docs/TEAM_HANDOFF.md** to send the module to the team.
