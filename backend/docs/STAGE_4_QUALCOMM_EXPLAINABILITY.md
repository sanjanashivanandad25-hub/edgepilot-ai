# EdgePilot Person 2 — Stage 4: Qualcomm-grounded explainability

## Purpose & boundary

Continue with the **same** Stage 1–3 engine. Stage 4 adds a separate entrypoint that:
1. Calls `recommend_with_benchmarks` **once** and preserves the winner, scores, estimates, warnings, architecture, metric provenance, and S24/S25 matching.
2. Generates deterministic answers to supported question types plus comparison/evidence data for Person 1's UI.
3. Optionally calls the Qualcomm Cloud AI Playground to **rephrase** the decision; the model does not choose the tier, scores, price, compliance, or latency.
4. Falls back to deterministic answers if the provider is unavailable or the response fails guardrails.

**Not done by Stage 4:** dynamic what-if recalculation, hybrid placement optimization, provider cost modeling, cloud/edge latency measurement, Pareto search, independent verification of LLM qualitative claims. These belong to future stages.

## Install (no additional dependencies or account configuration)

From your existing project directory with `.venv` active:

```bash
# Keep existing files and keys; this patch adds new files only.
unzip ~/Downloads/edgepilot_stage4_qualcomm_explainability_patch.zip -d .
python3 -m unittest discover -s tests -v
```

The patch adds `ai_engine/grounded_explanations.py`, `ai_engine/qualcomm_grounded.py`, `ai_engine/explanation_cli.py`, `tests/test_stage4_explainability.py` and this guide, plus sample output. It **does not** overwrite `.env`, old Qualcomm adapter, recommendation logic or benchmark evidence.

### Run offline first

```bash
python3 -m ai_engine.explanation_cli \
  --input examples/request_s25_match.json \
  --benchmark-dir benchmarks \
  --metrics examples/stage3_illustrative_metrics.json \
  --question why_recommended > /tmp/edgepilot_stage4.json

python3 - <<'PY'
import json
r=json.load(open('/tmp/edgepilot_stage4.json'))
e=r['details']['explainability']
print('Winner:',r['recommended_tier'])
print('Benchmark:',r['details']['benchmark']['status'])
print('Explanation source:',r['details']['explanation_source'])
print('Answer:',e['answer'])
for tier, v in e['comparisons'].items():
    print(tier, v['status'], v['score_gap_to_winner'])
PY
```

The numeric values in `examples/stage3_illustrative_metrics.json` are synthetic. Stage 4 reports and relays them as **estimated**, never as real provider quotes or real application performance.

### Ask why cloud lost (offline)

```bash
python3 -m ai_engine.explanation_cli \
  --input examples/request_s25_match.json \
  --benchmark-dir benchmarks \
  --metrics examples/stage3_illustrative_metrics.json \
  --question why_not_tier \
  --alternative-tier cloud > /tmp/why_not_cloud.json
```

Other questions: `--question evidence_limitations` and `--question what_would_change`. The latter currently explains what kinds of inputs *might* alter a decision. It does **not** compute switching thresholds; this is the responsibility of the upcoming Stage 5 simulator.

### Live Qualcomm (credentials must already work)

Load your existing playground credentials **in the current VS Code terminal** (never commit `.env`):

```bash
set -a
source .env
set +a

python3 -m ai_engine.explanation_cli \
  --input examples/request_s25_match.json \
  --benchmark-dir benchmarks \
  --metrics examples/stage3_illustrative_metrics.json \
  --question why_recommended \
  --qualcomm > /tmp/edgepilot_stage4_live.json

python3 - <<'PY'
import json
r=json.load(open('/tmp/edgepilot_stage4_live.json'))
print('Source:', r['details']['explainability']['answer_source'])
print('Answer:', r['details']['explainability']['answer'])
print('Warnings:', [x for x in r['warnings'] if 'Qualcomm' in x])
PY
```

A real success requires `answer_source: "qualcomm_llm"`. If it shows `deterministic`, inspect the warning and provider setup. Local unit tests do not prove the external service works. The API key stays in backend environment variables only.

**Provider constraints:** Stage 4 uses the same `QUALCOMM_API_KEY`, `QUALCOMM_BASE_URL`, `QUALCOMM_MODEL` as your earlier adapter. It sends chat completions to `<QUALCOMM_BASE_URL>/chat/completions`. Verify your account's provider endpoint and model; do not assume they are interchangeable across playgrounds.

**Provenance:** `0.45 ms` refers to the specific MobileNetV2 / Samsung Galaxy S25 (Family) / TFLite / float **inference-only** Workbench measurement (`jp8r0e0xg`). The separate S24/ONNX/W8A8 evidence is not interchangeable. Published and measured records still require source-level human verification.

## Person 3 backend integration

Stage 3's existing `recommend(...)` / `recommend_with_benchmarks(...)` remain unchanged. New entrypoint:

```python
from ai_engine.benchmark_registry import read_catalog
from ai_engine.grounded_explanations import explain_recommendation
from ai_engine.qualcomm_grounded import QualcommGroundedReasoner

catalog = read_catalog('benchmarks') # preferably cache at backend startup
llm = QualcommGroundedReasoner(timeout=30) # initialize server-side, once

response = explain_recommendation(
    request_json,
    benchmark_catalog=catalog,
    metrics_by_tier=metrics_for_this_workload,
    llm=llm,
    question='why_not_tier',
    alternative_tier='cloud',
)
```

Add an endpoint such as `POST /api/explain` (Person 3 owns API routing/authentication); accept only:
- `question`: `why_recommended | why_not_tier | evidence_limitations | what_would_change`
- `alternative_tier`: one of `on_device | far_edge | regional_edge | cloud`, required for `why_not_tier`.

The input is the **original workload** plus optionally workload-specific metric evidence your backend supplies. Do not accept arbitrary client-provided numbers as measured evidence; provenance labels are self-declared and must be verified against trusted sources. Never send API keys to browser clients. Rate-limit your public endpoint and avoid logging raw user inputs that may contain sensitive data.

### Backward-compatible output

Original fields remain: `recommended_tier`, `scores`, `estimates`, `explanation`, `tradeoffs`, `warnings`, `assumptions`, `architecture`, `details`. Stage 4 **adds**:

```json
{
  "details": {
    "explanation_source": "deterministic",
    "explainability": {
      "question": "why_not_tier",
      "alternative_tier": "cloud",
      "answer": "...",
      "answer_source": "qualcomm_llm",
      "deterministic_answer": "...",
      "comparisons": {
        "on_device": {
          "eligible": true,
          "score": 0,
          "status": "selected",
          "reasons": [],
          "score_gap_to_winner": 0,
          "latency": {"latency_ms": null, "monthly_cost_inr": null},
          "factor_sources": {"latency": "heuristic_profile"}
        }
      },
      "decision_drivers": [],
      "evidence": {"benchmark": null, "metric_provenance": {}},
      "guardrail_note": "...",
      "next_step": null
    }
  }
}
```

The JSON fragment above is a **schema illustration**, not a real response or score. Use the provided `examples/stage4_response_example.json` for a complete, genuine output from the deterministic test engine with *synthetic* test metrics.

### Person 1 UI contract

- Display `details.explainability.answer` and `answer_source` for the chosen explanation question.
- Provide a dropdown with the four supported questions, and a tier picker for `why_not_tier`.
- Show each tier's `comparisons[tier]` and source labels, including infeasibility reasons. Don't show a fake zero latency/cost where `null`.
- Display `details.explainability.evidence.benchmark` separately from `details.tier_estimates[*].latency_ms`.
- Show `answer_source=qualcomm_llm` as AI wording, **not as a verified measurement badge**. User must see the deterministic data/limitations alongside it.
- Do not make LLM output the controlling source of the recommendation or rates.

## Explainability safeguards

1. **No decision authority:** core engine scores and applies hard constraints once; LLM changes only explanation prose.
2. **Data minimization:** the provider receives an allowlisted machine-generated summary (scores, tiers, basic evidence scope); never the raw prompt, source URLs, arbitrary workload strings or API key as content.
3. **Number guard:** generated text containing numeric digits or currency symbols is rejected, so quantitative figures come from the deterministic response instead.
4. **Basic guarantee guard:** disallows a few explicit unsupported guarantee phrases, but does **not** scientifically verify qualitative claims.
5. **Failure-safe:** fallback includes the computed explanation and a warning identified by exception class only.

Note that a supported LLM could still make qualitative errors that these guards do not detect. Never claim LLM responses are independently verified. If using sensitive workloads (e.g. health applications), do not transmit user/patient data to the playground.

## End-to-end completion checklist

- [ ] Stage 4 installed without overwriting prior code or credentials
- [ ] Full test suite passes (96 tests with the original 76 plus Stage 4's 20)
- [ ] Offline question and comparisons work
- [ ] Live Qualcomm explanation returns `qualcomm_llm`
- [ ] Invalid numeric LLM claims fall back safely
- [ ] Frontend/back-end owners receive above API contract
