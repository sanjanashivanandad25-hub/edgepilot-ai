# Stage 8 — Person 2 final handoff (contract 1.0)

## 1. What is complete

Person 2 delivers **a Python decision-support engine, not an HTTP server or deployed AI system**.
- Strict workload validation and four-tier feasibility/ranking (`on_device`, `far_edge`, `regional_edge`, `cloud`).
- Exact Qualcomm benchmark identity matching and provenance. The S25 result is *model inference only*.
- Deterministic weighting using available cost and end-to-end latency data plus explicitly labeled heuristics.
- Qualcomm-hosted grounded explanations, optional and guarded, with deterministic fallback.
- Recomputed what-if scenarios; sampled one-factor counterfactuals (not mathematically exact thresholds).
- Conditional hybrid architecture, Pareto comparison, modeled cost break-even.
- Stage 7 invariant auditing and bounded request validation.
- Stage 8 stable import wrapper, sample responses, offline quality gate, sanitized export script.

## 2. Local installation (additive; never replace existing benchmark/.env files)

From the existing `edgepilot_person2_handoff` directory:

```bash
# Stage 8 patch only; these are NEW files
unzip -n ~/Downloads/edgepilot_stage8_final_handoff_patch.zip -d .
python3 -m unittest discover -s tests -v
python3 -m scripts.stage7_validation_matrix --output /tmp/edgepilot_scenarios.json
python3 -m scripts.stage8_smoke_test --output /tmp/edgepilot_stage8_smoke.json
```

Expected results with the patch on Stages 1–7: **233 tests OK**, **10/10 Stage 7 matrix**, **10/10 Stage 8 smoke gate**. Local totals may differ after your own edits.

## 3. The entrypoint Person 3 imports

```python
from ai_engine.team_handoff import TeamEngine

engine = TeamEngine(benchmark_dir="benchmarks")

result = engine.recommend(request_json,
    metrics_by_tier=metrics_for_this_exact_workload, # Person 3 owns estimates
    cost_curves=cost_model_for_this_exact_workload)  # Person 3 owns pricing

explanation = engine.explain(request_json, question="why_not_tier",
    alternative_tier="cloud", metrics_by_tier=metrics_for_this_exact_workload,
    llm=engine.qualcomm_from_environment(timeout=20))

simulation = engine.simulate(request_json,
    changes={"device_available_ram_mb":128},
    metrics_by_tier=metrics_for_baseline,
    scenario_metrics_by_tier=metrics_for_modified_workload)

flips = engine.counterfactuals(request_json, fields=["device_available_ram_mb"])
optimization = engine.optimize(request_json,
    metrics_by_tier=metrics_for_this_exact_workload,
    cost_curves=cost_model_for_this_exact_workload)
```

`metrics_by_tier`, `cost_curves` and LLM are **optional**; missing values remain missing. Do not send the demo metric file for arbitrary workloads. Initialize `TeamEngine` once per worker, not per request. For high-frequency sliders, keep `llm=None` and request an LLM explanation only on user demand.

### Backend endpoints recommended

- `GET /api/health`: Person 3's existing server health route.
- `POST /api/recommend`: original `{ "workload": {...} }` input; original response keys **unchanged**.
- `POST /api/explain`: `{ "workload": {...}, "question":"why_not_tier", "alternative_tier":"cloud" }`.
- `POST /api/simulate`: `{ "workload": {...}, "changes": {"device_available_ram_mb":128} }`.
- `POST /api/optimize`: original workload input.
- `POST /api/counterfactuals`: `{ "workload": {...}, "fields":["device_available_ram_mb"] }`.

See `integration_examples/fastapi_routes_example.py` for a **non-production** reference router. Person 3 owns authentication, endpoint validation, secure configuration, per-workload cost/network modeling, timeouts, CORS, rate limits, error responses, and deployment.

## 4. Frontend fields Person 1 needs

For recommendation, preserve top-level:

`recommended_tier`, `scores`, `estimates`, `explanation`, `tradeoffs`, `warnings`, `assumptions`, `architecture`.

And read `details.benchmark`, `details.ranking`, `details.feasibility`, `details.score_breakdown`, `details.decision_drivers`, `details.tier_estimates`, `details.metric_provenance`, `details.explainability`, `details.optimization`, `details.reliability`.

For simulation, read: `comparison.original_tier`, `comparison.new_tier`, `comparison.recommendation_changed`, `comparison.score_deltas`, `comparison.feasibility_changes`, `comparison.metrics_handling`; `quality` contains baseline and scenario audit results.

For counterfactuals: `flips` are **sampled changes** that actually flip the decision under the current engine; they are not globally minimal, exact thresholds or proof of deployment performance.

See `examples/stage8_*_DEMO.json` for UI-friendly fixture files.

## 5. Qualcomm setup & proof

Only Person 3's backend environment should have `QUALCOMM_API_KEY`, `QUALCOMM_BASE_URL`, and `QUALCOMM_MODEL`. Load the environment in the server process; NEVER embed tokens in frontend, JSON fixtures, or repo.

Offline recommendations work without credentials. Use `--qualcomm` on an explicit explanation command to test the real provider connection, and check `details.explainability.answer_source == 'qualcomm_llm'`. If it is `deterministic`, check warnings and connection diagnostics. **Offline tests do not demonstrate live Qualcomm connectivity.**

## 6. Benchmark provenance

A real user-reported Workbench benchmark exists for `mobilenet_v2` / Samsung Galaxy S25 (Family) / `tflite` / `float`, inference latency 0.45 ms, profile job `jp8r0e0xg`. Keep it as a separate evidence JSON; do not generalize it to other models/devices or use it as end-to-end application latency. Do not overwrite the user's existing S24 published evidence (ONNX Runtime / W8A8 / 0.33 ms).

The included demo cost and E2E latency datasets are **synthetic**. Replace them with transparent, workload-specific estimates from Person 3 before quoting values to judges as real costs.

## 7. Export a sanitized teammate ZIP from YOUR local verified project

```bash
python3 -m scripts.stage8_export_handoff \
  --output dist/edgepilot_person2_team_handoff.zip \
  --include-evidence
```

The `--include-evidence` flag adds only a sanitized allowlist of benchmark metadata. Review source references (including Workbench job IDs) before sharing. The archive intentionally excludes `.env`, private tokens, `.venv`, raw profile dumps, `.git`, caches and backups.

Run your local 233-test suite and 10/10 smoke gate immediately before exporting. **The ZIP is a code handoff; Person 3 must still integrate/deploy the server.**

## 8. Remaining real-team signoffs

- [ ] Person 3 confirms original `/api/recommend` request returns 200 with all top-level fields and handles unknown costs as null.
- [ ] Person 3 supplies scenario-specific end-to-end latency, network and monthly cost estimates with provenance.
- [ ] Person 3 confirms live Qualcomm answer source and secure key loading.
- [ ] Person 3 adds authenticated routes, rate limiting, error handling and deployment.
- [ ] Person 1 renders the four tiers, uncertainty, evidence badge, hybrid diagram, Pareto chart, and scenario deltas.
- [ ] Whole team demos one validated baseline, one hardware-memory flip, and a failure/fallback case.

### Scientific honesty

Quality gate passing means internal invariants were checked **for the cases run**, not verified global optimality, security certification, real-world latency, regulatory compliance, or accuracy probabilities. The Stage 7 code calls these rankings provisional and that caveat must remain visible.
