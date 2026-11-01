# Handoff to Person 1 and Person 3

## Who owns what

**Person 2 ships `ai_engine/`**. The module takes a Python `dict` and returns a Python `dict` whose fields are the team's agreed `POST /api/recommend` response. It does not start a server, save to databases, perform ongoing monitoring or calculate provider billing.

### Person 3: how to integrate

Copy the entire `ai_engine/` directory into the root of your existing backend repository, adjacent to `backend/`. From the common project root, import:

```python
from ai_engine.recommender import recommend

response_json = recommend(request_json)
```

Example FastAPI adapter (Person 3 can replace with Pydantic model later):

```python
from fastapi import FastAPI, HTTPException
from ai_engine.recommender import recommend

app = FastAPI()

@app.post("/api/recommend")
def recommendation_endpoint(request: dict):
    try:
        return recommend(request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
```

If backend runs from a different subdirectory, ensure the package's parent directory is on `PYTHONPATH` or package `ai_engine` into the backend folder. Do not rely on manipulating global imports at runtime.

To add Person 3's tier-specific estimated monthly costs and end-to-end latency, call:

```python
result = recommend(request_json, metrics_by_tier={
    "regional_edge": {
        "source": "estimated",
        "latency_ms": 45.0,
        "monthly_cost_inr": 800.0,
        "source_note": "Illustrative placeholders only; replace with real provenance"
    }
})
```

The numbers in this code block are EXAMPLES; do not present them as measurements. Provide estimates for all tiers if possible to compare fairly. `source='demo'` is ignored on purpose.

If Qualcomm configuration is working, construct one `QualcommExplainer()` at server startup and pass it to `recommend(..., llm=explainer)`; if it's down, engine returns deterministic explanation and a warning. Do not expose API keys to frontend.

Person 3 owns `GET /api/health`, route wiring, CORS, cloud deployment, source-specific costs, scenario simulation, report export, and per-tier metric calculation. For simulation they can rerun `recommend` after modifying workload/metrics. For named counterfactual checks, use `compare_scenarios(payload, modifications)`.

### Person 1: response integration

Use these existing v1 fields as-is:

- `recommended_tier`: one of on_device/far_edge/regional_edge/cloud, or **null** for impossible requirements
- `scores`: 0-100 **suitability** scores; NOT confidence percentages
- `estimates`: latency in ms and monthly cost in INR; values can be **null**
- `explanation`, `tradeoffs[]`, `warnings[]`, `assumptions[]`
- `architecture.nodes[]` & `architecture.connections[]` compatible with React Flow transformation

Extra `details` (can be hidden until an Advanced tab exists): `feasibility`, `ranking`, `score_breakdown`, `metric_sources`, `status`.

Specific UI behavior: for blocked tiers, label `Infeasible` instead of showing only `0/100`. For no eligible tier, display `No feasible deployment found` and reason list. For null estimates show `Not estimated`, not `₹0` or `0 ms`. Include warning `Demo heuristic estimates` on unverified scores.

## Freeze these team decisions now

1. **Bandwidth field:** This implementation interprets `bandwidth_requirement: low|medium|high` as the *amount of network traffic the workload demands*, not the available internet speed. Person 3 should use `bandwidth_available_mbps` plus optional `minimum_network_bandwidth_mbps` to simulate physical network limits.
2. **Budget:** `budget_monthly` and `estimates.monthly_cost` are always **INR/month**.
3. **Unknowns:** `null` allowed for `estimates.latency_ms` and `estimates.monthly_cost`; `recommended_tier=null` allowed only when no tier feasible.
4. **Tier definitions:** Far edge means local/access network compute; regional edge means more distant regional datacenter. These are project assumptions, not universal definitions.
5. **Extras:** Response has optional `details`; consumers may ignore.
6. **Latency terminology:** Metrics field `latency_ms` means **end-to-end experienced latency under comparable workload**, not Qualcomm AI Hub's pure inference milliseconds.
7. **Benchmarks:** Do not describe heuristic scores or sample mock numbers as measured Qualcomm scores.

## Acceptance test before merge

1. `python3 -m unittest discover -s tests -v` is green.
2. Calling Person 3's `/api/recommend` with `examples/request_v1.json` gets HTTP 200 with all team-required keys.
3. Person 1 can render a recommendation with `null` estimates and show architecture connections.
4. Using `examples/request_enhanced.json` excludes on-device due to RAM limits.
5. Setting `require_offline=true` excludes network tiers. When no tier remains, UI handles the empty state.
6. If Qualcomm LLM API times out, response still works with deterministic explanation.

**Do not merge the team's original `original_team_mock_response.json` as a real algorithm result:** that fixture has fictional scores and rupee/latency estimates.
