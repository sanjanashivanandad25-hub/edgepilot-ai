# EdgePilot — Stage 7: Reliability, Adversarial Testing & Quality Gates

## Purpose

Stage 7 is additive to Stages 1–6. It does not overwrite the Qualcomm adapter, scoring logic, benchmarks, cost model, or simulation. It introduces a strict **opt-in input boundary**, an invariant audit on computed results, a single backend-friendly orchestrator, offline adversarial tests, and a demonstration scenario matrix.

**This is decision-support software.** A passing software test or Workbench inference benchmark does not guarantee deployed latency, infrastructure pricing, model compatibility, security, legal compliance, or operational resilience.

## Install in the existing repository

1. Make a backup or Git commit of working Stages 1–6.
2. From the root of `edgepilot_person2_handoff`, unzip the Stage 7 ZIP (new files only):
   ```bash
   unzip -n ~/Downloads/edgepilot_stage7_reliability_patch.zip -d .
   ```
3. Do **not** put `.env`, `client.ini`, personal keys, or raw customer information in Git. The ZIP has no credentials.

The patch creates:

```text
ai_engine/reliability.py
ai_engine/reliability_cli.py
scripts/__init__.py
scripts/stage7_validation_matrix.py
tests/test_stage7_reliability.py
docs/STAGE_7_RELIABILITY_VALIDATION.md
examples/stage7_invalid_request_DEMO.json
examples/stage7_validation_matrix_example.json
```

## Gate 1 — all unit tests

```bash
python3 -m unittest discover -s tests -v
```

Against the integrated Stage 6 project used to construct this patch, **207 tests passed**: 158 earlier tests plus 49 new tests. Your local count may differ if you have additional tests or modified files.

Covers mandatory field validation, bad numbers, unknown API keys, input control characters, offline and no-network policy, insufficient memory, unsupported devices, missing E2E metrics, non-matching evidence, tampered rankings, fabricated provenance, hybrid policy, invalid architecture links, LLM error fallback, and LLM numerical/guarantee guards. **The tests never call the real Qualcomm API.**

## Gate 2 — audit a complete recommendation (offline)

```bash
python3 -m ai_engine.reliability_cli \
  --input examples/stage6_hybrid_request_DEMO.json \
  --benchmark-dir benchmarks \
  --metrics examples/stage6_pareto_tradeoff_metrics_DEMO.json \
  --cost-curves examples/stage6_cost_curves_DEMO.json \
  --output /tmp/stage7_quality_report.json
```

The CLI prints `Audit: pass_with_caveats; saved /tmp/stage7_quality_report.json` for the supplied Stage 6 demo fixtures. Inspect:

```bash
python3 - <<'PY'
import json
p=json.load(open('/tmp/stage7_quality_report.json'))
print('Winner:', p['recommended_tier'])
print('Audit:', p['details']['reliability'])
print('Explanation:', p['details']['explainability']['answer_source'])
PY
```

`pass_with_caveats` is the **expected** result for provisional, incomplete infrastructure evidence. It does not mean a test failed. `fail` indicates internally contradictory output, which `guarded_recommendation` **raises** as `ReliabilityError` instead of returning it to users. Never hide caveats in the frontend.

The Stage 6 example metrics and cost curves are **synthetic**, not provider pricing or deployment benchmarks. The genuine S25 0.45 ms figure describes **model inference alone**, not complete application E2E latency.

## Gate 3 — scenario regression matrix (offline)

```bash
python3 -m scripts.stage7_validation_matrix \
  --output /tmp/stage7_validation_matrix.json
```

Expected against bundled sample evidence: `Stage 7 scenario matrix: 10/10 passed`.

The matrix covers: matching benchmark, insufficient RAM, offline requirements, network outage, all tiers blocked, unmatched model, high-scale workload, hybrid opt-in, unknown data residency, and an actual recomputed `on_device` → `far_edge` change.

The matrix stores only small result summaries in JSON. It does not ping live cloud inference or use an actual production deployment.

## Gate 4 — verify strict public API input handling

```bash
python3 - <<'PY'
import json
from ai_engine.reliability import validate_external_request
req=json.load(open('examples/stage7_invalid_request_DEMO.json'))
try:
    validate_external_request(req)
except ValueError as exc:
    print('Expected rejection:', str(exc))
else:
    raise SystemExit('FAILED: should reject unknown public request field')
PY
```

`validate_external_request` is opt-in and more restrictive than the original `validate`: it rejects unrecognized workload fields rather than ignoring them. This is appropriate at the HTTP boundary because silently ignored typos can lead to unsafe defaults. Person 3 must coordinate any newly added request fields before enforcing it.

## Gate 5 — optionally verify Qualcomm live explanations

Load your existing `.env` environment variables safely. **No live request is made unless `--qualcomm` is provided.**

```bash
set -a
source .env
set +a
python3 -m ai_engine.reliability_cli \
  --input examples/request_s25_match.json \
  --benchmark-dir benchmarks \
  --qualcomm \
  --output /tmp/stage7_qualcomm.json
```

Check `details.explainability.answer_source` is `qualcomm_llm`; `deterministic` means the fallback was used. Stage 7 unit tests use a **mock** Qualcomm service, not a live account.

## Recommended Person 3 handoff API

```python
from ai_engine.benchmark_registry import read_catalog
from ai_engine.reliability import guarded_recommendation, ReliabilityError
from ai_engine.qualcomm_grounded import QualcommGroundedReasoner

catalog = read_catalog('benchmarks')            # initialize once, at startup
reasoner = QualcommGroundedReasoner(timeout=15) # initialize only with valid env vars

# In an endpoint handler; `payload` is parsed request JSON:
result = guarded_recommendation(
    payload,
    benchmark_catalog=catalog,
    metrics_by_tier=person3_metrics,        # optional workload-specific source-annotated values
    cost_curves=person3_cost_curves,        # optional, scenario-specific
    llm=reasoner,                          # optional; deterministic fallback otherwise
    question='why_recommended',
)
```

Person 3 still owns authorization, HTTP schema mapping (400/422 for invalid input, 500 for `ReliabilityError`), per-user rate limits, server-side credential storage, TLS, request body limits, logging/redaction, backend deployment, and E2E integration checks.

For high-frequency what-if slider updates, use the Stage 5 simulation engine **without a remote LLM call on every tick**. Use Qualcomm for a final explanation on explicit user request.

## Person 1 handoff data

The original top-level recommendation fields are unchanged. `details.reliability` includes:

- `status`: `pass`, `pass_with_caveats`, or `fail`
- `errors`: failures in decision consistency; the guarded entrypoint never returns a response with errors
- `warnings`: explicitly disclosed uncertainties
- `check_categories` and `audit_scope`: the boundaries of the checker

Person 1 should show the warning/caveat strings, benchmark source, and `estimated`/`measured` metric tags. **Do not render `pass_with_caveats` as “verified”, “guaranteed”, or a 100% confidence badge.**

## What remains before calling the whole system finished

- A **real** Person 3 service supplying workload-specific cost and network E2E estimates/quotes, with source citations and assumptions.
- Browser/API integration and secure backend hosting, plus genuine end-to-end tests from React → FastAPI → engine → optional Qualcomm API.
- Physical deployment measurements if your team wants to make real latency or cost guarantees. Those are not provided by the MobileNetV2 hardware inference profiling job.
- Manual adversarial review of LLM explanations: simple format guards are **not** a proof that prose is factually correct.
- Stage 8 end-to-end packaging, reproducible demo runbook, and technical presentation.
