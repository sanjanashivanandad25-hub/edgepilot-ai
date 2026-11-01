"""Stage 4: bounded evidence-grounded explanations without altering the decision.

The recommendation, ranking, constraints and numeric fields are ALWAYS determined by
recommend_with_benchmarks. A language model can only rephrase a selected answer.
No raw end-user prompt or provider credential is returned to the frontend.
"""
from copy import deepcopy
from .benchmarked import recommend_with_benchmarks
from .config import TIERS, LABELS
from .validation import validate

QUESTIONS = ("why_recommended", "why_not_tier", "evidence_limitations", "what_would_change")


def _show(tier):
    return LABELS.get(tier, "No feasible tier")


def _metric_phrase(tier, estimate):
    pieces = []
    if estimate.get("latency_ms") is not None:
        pieces.append(f"end-to-end latency {estimate['latency_ms']:g} ms ({estimate['latency_source']})")
    else:
        pieces.append("end-to-end latency unknown")
    if estimate.get("monthly_cost_inr") is not None:
        pieces.append(f"monthly cost INR {estimate['monthly_cost_inr']:g} ({estimate['cost_source']})")
    else:
        pieces.append("monthly cost unknown")
    return f"{_show(tier)}: " + "; ".join(pieces) + "."


def _reason(result, question, alternative_tier, workload):
    tier = result["recommended_tier"]
    details = result["details"]
    ranking = details["ranking"]
    scores = result["scores"]
    statuses = details["feasibility"]
    estimates = details["tier_estimates"]
    if question == "why_recommended":
        if tier is None:
            return "No deployment tier passed the confirmed hard constraints. Review the exclusions and requirements."
        answer = (f"{_show(tier)} ranks first with a provisional, uncalibrated suitability score of "
                  f"{scores[tier]:g}/100. " + _metric_phrase(tier, estimates[tier]))
        if tier == "on_device" and workload["privacy_requirement"] == "high":
            if workload["latency_requirement_ms"] <= 50:
                answer += " High privacy and strict latency priorities favor local execution."
            else:
                answer += " The high privacy requirement favors keeping inference local."
        if (tier == "cloud" and workload["privacy_requirement"] == "low"
                and workload["latency_requirement_ms"] >= 150):
            costs = [
                values["monthly_cost_inr"]
                for values in estimates.values()
                if values["monthly_cost_inr"] is not None
            ]
            if costs and estimates[tier]["monthly_cost_inr"] == min(costs):
                answer += " Lower relative cost, relaxed latency, and low privacy requirements favor scalable cloud processing."
            else:
                answer += " Relaxed latency and low privacy requirements favor scalable cloud processing."
        checks = details.get("sla_checks", {}).get(tier, {})
        provisional_failures = [
            label for label, key in (("latency", "latency_status"), ("cost", "cost_status"))
            if checks.get(key) == "provisional_fail"
        ]
        if provisional_failures:
            metrics = " and ".join(provisional_failures)
            verb = "exceed" if len(provisional_failures) > 1 else "exceeds"
            answer += (
                f" Estimated {metrics} {verb} the supplied limit; "
                "treat this recommendation as provisional until verified."
            )
        if len(ranking) > 1:
            second = ranking[1]
            answer += f" {_show(second)} ranks next ({scores[second]:g}/100)."
        return answer + " The ranking is not a guarantee of deployment performance."
    if question == "why_not_tier":
        alt = alternative_tier
        if alt == tier:
            return f"{_show(alt)} is the selected recommendation. " + _metric_phrase(alt, estimates[alt])
        if not statuses[alt]["eligible"]:
            reasons = "; ".join(statuses[alt]["reasons"])
            return f"{_show(alt)} was excluded by confirmed constraints: {reasons}."
        if tier is None:
            return f"{_show(alt)} cannot be selected because no tier passed the mandatory constraints."
        gap = round(scores[tier] - scores[alt], 1)
        return (f"{_show(alt)} remains eligible, but ranks below {_show(tier)} by {gap:g} "
                f"uncalibrated suitability points. " + _metric_phrase(alt, estimates[alt]))
    if question == "evidence_limitations":
        benchmark = details.get("benchmark", {})
        if benchmark.get("status") == "matched":
            evidence = (f"A matching Qualcomm device-level inference result is available: "
                        f"{benchmark['inference_latency_ms']:g} ms for {benchmark['model']} "
                        f"on {benchmark['device']} ({benchmark['runtime']}, {benchmark['precision']}). "
                        "It measures model inference only, not end-to-end latency or monthly cost.")
        else:
            evidence = "No exact Qualcomm model/device/runtime/precision inference benchmark was selected."
        if tier is None:
            return evidence + " No tier passed the confirmed constraints."
        return evidence + " " + _metric_phrase(tier, estimates[tier])
    # 'what_would_change' only explains the conditions that are worth exploring;
    # a real flip threshold requires Stage 5 to recompute multiple scenarios.
    return ("Changing hard constraints (for example device memory or offline access), latency budgets, "
            "network conditions or credible cost estimates may change the winning tier. "
            "Run the decision engine again with changed inputs to establish whether it actually changes; "
            "no specific switching threshold has been demonstrated here.")


def _comparison(result):
    winner = result["recommended_tier"]
    breakdown = result["details"]["score_breakdown"]
    comparison = {}
    for tier in TIERS:
        eligible = result["details"]["feasibility"][tier]["eligible"]
        score = result["scores"][tier]
        comparison[tier] = {
            "eligible": eligible,
            "score": score,
            "status": "selected" if tier == winner else "eligible" if eligible else "excluded",
            "reasons": result["details"]["feasibility"][tier]["reasons"],
            "score_gap_to_winner": round(result["scores"][winner] - score, 1) if winner and eligible else None,
            "latency": result["details"]["tier_estimates"][tier],
            "factor_sources": {factor: item["origin"] for factor, item in breakdown[tier].items()},
        }
    return comparison


def _safe_facts(result):
    """Explicit allowlist for the LLM, not the raw user request or evidence notes.

    No model prompts, raw URLs, data region strings, or arbitrary application text
    are sent. Benchmark identifiers are intentionally omitted to limit prompt injection.
    """
    details = result["details"]
    benchmark = details.get("benchmark", {})
    selected_benchmark = None
    if benchmark.get("status") == "matched":
        selected_benchmark = {
            "status": "matched", "inference_latency_ms": benchmark["inference_latency_ms"],
            "scope": "model_inference_only_not_end_to_end",
        }
    return {
        "winner": result["recommended_tier"],
        "scores_are_heuristic": True,
        "scores": result["scores"],
        "ranking": details["ranking"],
        "eligible": {tier: details["feasibility"][tier]["eligible"] for tier in TIERS},
        "decision_drivers": details["decision_drivers"][:4],
        "tier_metrics": {tier: {
            "end_to_end_latency_ms": details["tier_estimates"][tier]["latency_ms"],
            "latency_source": details["tier_estimates"][tier]["latency_source"],
            "monthly_cost_inr": details["tier_estimates"][tier]["monthly_cost_inr"],
            "cost_source": details["tier_estimates"][tier]["cost_source"],
        } for tier in TIERS},
        "benchmark": selected_benchmark,
        "limitations": [
            "Model inference benchmark alone does not prove end-to-end latency.",
            "Missing metrics must remain unknown, not zero.",
            "Suitability scores are not probabilities or validated real-world rankings.",
        ],
    }


def explain_recommendation(payload, *, benchmark_catalog, metrics_by_tier=None,
                           llm=None, question="why_recommended", alternative_tier=None):
    """Drop-in Stage 4 entrypoint for backend; always returns Stage 3 required fields.

    question is a controlled identifier, NOT raw user chat. Person 3 is responsible
    for authentication, throttling, and private-data rules on public API routes.
    """
    if question not in QUESTIONS:
        raise ValueError(f"Unsupported explanation question. Choose from {QUESTIONS}")
    if question == "why_not_tier" and alternative_tier not in TIERS:
        raise ValueError("why_not_tier requires a recognized alternative_tier")
    if alternative_tier is not None and alternative_tier not in TIERS:
        raise ValueError("alternative_tier is not a recognized deployment tier")
    # Compute ONCE with the audited Stage 3 engine. Never delegate ranking to LLM.
    result = recommend_with_benchmarks(payload, benchmark_catalog=benchmark_catalog,
                                       metrics_by_tier=metrics_by_tier, llm=None)
    deterministic_answer = _reason(result, question, alternative_tier, validate(payload))
    response_answer, source = deterministic_answer, "deterministic"
    if llm is not None:
        try:
            candidate = llm.answer(facts=_safe_facts(result), question=question,
                                   alternative_tier=alternative_tier)
            if not isinstance(candidate, str) or not candidate.strip():
                raise ValueError("LLM answer is empty")
            response_answer = candidate.strip()
            source = "qualcomm_llm"
        except Exception as exc:
            # Exception class only; never leak API key, HTTP payload or response body.
            result["warnings"].append(
                f"Qualcomm grounded answer unavailable ({type(exc).__name__}); deterministic answer used."
            )
    if question == "why_recommended":
        result["explanation"] = response_answer
        result["details"]["explanation_source"] = source
    result["details"]["explainability"] = {
        "question": question,
        "alternative_tier": alternative_tier if question == "why_not_tier" else None,
        "answer": response_answer,
        "answer_source": source,
        "deterministic_answer": deterministic_answer,
        "comparisons": _comparison(result),
        "decision_drivers": deepcopy(result["details"]["decision_drivers"]),
        "evidence": {
            "benchmark": deepcopy(result["details"].get("benchmark")),
            "metric_provenance": deepcopy(result["details"]["metric_provenance"]),
        },
        "guardrail_note": (
            "LLM can reword the explanation but cannot modify ranking or metrics. "
            "Format and numeric-claim guards are not independent factual verification."
        ),
        "next_step": "Use the Stage 5 scenario engine for quantitative what-if thresholds."
                     if question == "what_would_change" else None,
    }
    return result
