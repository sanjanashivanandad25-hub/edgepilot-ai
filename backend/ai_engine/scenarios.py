"""Stage 5: deterministic, side-effect-free counterfactual scenario evaluation.

Never extrapolate workload-specific E2E metrics after hardware/network/scale changes.
Qualifier: changes represent hypothetical inputs, never automated deployment actions.
"""
from copy import deepcopy
from .benchmarked import recommend_with_benchmarks
from .config import TIERS
from .validation import validate

# Whitelist of fields we actually support and validate in the existing core.
SUPPORTED_CHANGES = frozenset({
    "latency_requirement_ms", "bandwidth_requirement", "budget_monthly",
    "privacy_requirement", "criticality", "model_ram_required_mb",
    "device_available_ram_mb", "concurrent_users", "bandwidth_available_mbps",
    "minimum_network_bandwidth_mbps", "minimum_availability_percent",
    "require_offline", "allow_remote_processing", "network_available",
    "application_type", "model_name", "target_device", "runtime", "precision",
    "allowed_tiers", "allowed_data_regions",
})

# Changing any of these makes the old cost/latency/inference evidence potentially
# unrepresentative of the *new* scenario. Invalidate metrics unless backend sends
# fresh scenario-specific values. Qualitative tier priors still function.
METRIC_SENSITIVE_CHANGES = frozenset({
    "application_type", "model_name", "target_device", "runtime", "precision",
    "model_ram_required_mb", "device_available_ram_mb",
    "bandwidth_requirement", "bandwidth_available_mbps",
    "minimum_network_bandwidth_mbps", "network_available", "concurrent_users",
})

_MISSING = "not_provided"


def _check_changes(payload, changes):
    validate(payload)
    if not isinstance(changes, dict) or not changes:
        raise ValueError("changes must be a nonempty object of workload fields")
    if len(changes) > 22:
        raise ValueError("Too many workload modifications")
    unknown = set(changes) - SUPPORTED_CHANGES
    if unknown:
        raise ValueError("Unsupported scenario fields: " + ", ".join(sorted(unknown)))
    modified = deepcopy(payload)
    modified["workload"].update(deepcopy(changes))
    validate(modified)
    if any(modified["workload"].get(k) == payload["workload"].get(k) for k in changes):
        # Unchanged fields are not a failure; just ignore them in effective changes.
        pass
    actual_changes = {k: v for k, v in changes.items()
                      if payload["workload"].get(k) != v}
    if not actual_changes:
        raise ValueError("Scenario contains no effective change")
    return modified, actual_changes


def _metrics_for_after(actual_changes, baseline_metrics, scenario_metrics):
    if scenario_metrics is not None:
        if not isinstance(scenario_metrics, dict):
            raise ValueError("scenario_metrics_by_tier must be an object or null")
        return deepcopy(scenario_metrics), {
            "mode": "fresh_scenario_supplied",
            "message": "Backend supplied metrics specifically for this hypothetical scenario; evidence labels are preserved.",
            "reused_baseline_metrics": False,
        }
    sensitive = sorted(set(actual_changes) & METRIC_SENSITIVE_CHANGES)
    if sensitive:
        return None, {
            "mode": "baseline_metrics_invalidated",
            "message": "Workload characteristics changed; existing tier metrics were withheld to avoid stale latency and cost claims.",
            "invalidated_because": sensitive,
            "reused_baseline_metrics": False,
        }
    return deepcopy(baseline_metrics), {
        "mode": "baseline_metrics_reused" if baseline_metrics else "no_metrics_available",
        "message": "Only requirements or policies changed; underlying workload evidence was not recalculated.",
        "reused_baseline_metrics": bool(baseline_metrics),
    }


def _deltas(before, after):
    return {tier: {
        "before": before["scores"][tier],
        "after": after["scores"][tier],
        "delta": round(after["scores"][tier] - before["scores"][tier], 1),
    } for tier in TIERS}


def _feasibility_changes(before, after):
    change = {}
    for tier in TIERS:
        old = before["details"]["feasibility"][tier]
        new = after["details"]["feasibility"][tier]
        if old["eligible"] != new["eligible"] or old["reasons"] != new["reasons"]:
            change[tier] = {
                "was_eligible": old["eligible"], "now_eligible": new["eligible"],
                "before_reasons": list(old["reasons"]), "after_reasons": list(new["reasons"]),
            }
    return change


def _description(before, after, changes, handling, feasibility_change):
    old, new = before["recommended_tier"], after["recommended_tier"]
    label = lambda tier: tier.replace("_", " ") if tier else "no feasible tier"
    if old != new:
        sentence = f"Recalculation changed the leading tier from {label(old)} to {label(new)}."
    else:
        sentence = f"Recalculation kept {label(new)} as the leading tier."
    affected = sorted(changes)
    sentence += " Changed input(s): " + ", ".join(affected) + "."
    if feasibility_change:
        sentence += " The set of feasible tiers and/or their exclusions changed."
    if handling["mode"] == "baseline_metrics_invalidated":
        sentence += " Previous latency/cost figures were withheld because they may be stale."
    sentence += " Rankings remain provisional; this is a hypothetical scenario, not a deployment action."
    return sentence


def simulate_scenario(payload, *, changes, benchmark_catalog, metrics_by_tier=None,
                      scenario_metrics_by_tier=None, llm=None):
    """Recompute before vs after from actual core engine; no fake score adjustments.

    `metrics_by_tier`: baseline evidence supplied by Person 3 for original request.
    `scenario_metrics_by_tier`: optional NEW evidence for changed workload, supplied
      by Person 3 after recomputing their cost/network model. Missing = invalidate
      on material workload change. This module never fabricates E2E metrics.
    `llm`: OPTIONAL Stage 4 explainer used once on the FINAL scenario only.
           Slider updates and counterfactual sweeps should default to llm=None.
    """
    modified, actual_changes = _check_changes(payload, changes)
    before = recommend_with_benchmarks(payload, benchmark_catalog=benchmark_catalog,
                                       metrics_by_tier=metrics_by_tier, llm=None)
    after_metrics, handling = _metrics_for_after(actual_changes, metrics_by_tier,
                                                 scenario_metrics_by_tier)
    if llm is None:
        after = recommend_with_benchmarks(modified, benchmark_catalog=benchmark_catalog,
                                           metrics_by_tier=after_metrics, llm=None)
    else:
        # Stage 4 adapter produces explanations, not decisions. Only called on final
        # selected scenario; never used inside automated counterfactual sweeps.
        from .grounded_explanations import explain_recommendation
        after = explain_recommendation(modified, benchmark_catalog=benchmark_catalog,
                                       metrics_by_tier=after_metrics, llm=llm,
                                       question="why_recommended")
    if handling["mode"] == "baseline_metrics_invalidated":
        after["warnings"].append("Scenario invalidated baseline tier metrics; supply freshly modeled or measured scenario metrics for comparable cost/latency figures.")
    fchanges = _feasibility_changes(before, after)
    input_diff = [
        {"field": k, "before": deepcopy(payload["workload"].get(k)), "after": deepcopy(v)}
        for k, v in sorted(actual_changes.items())
    ]
    notes = [
        "Scores are provisional suitability indices, not probabilities.",
        "A changed winner is a sampled scenario result, not a proven real-world tipping point.",
        "Inference-only benchmarks cannot establish application end-to-end latency.",
    ]
    if handling["mode"] == "baseline_metrics_invalidated":
        notes.append("Costs and total latency in the original scenario must not be assumed valid after the workload change.")
    comparison = {
        "original_tier": before["recommended_tier"],
        "new_tier": after["recommended_tier"],
        "recommendation_changed": before["recommended_tier"] != after["recommended_tier"],
        "changed_inputs": input_diff,
        "score_deltas": _deltas(before, after),
        "feasibility_changes": fchanges,
        "metrics_handling": handling,
        "benchmark_before": before["details"]["benchmark"].get("status"),
        "benchmark_after": after["details"]["benchmark"].get("status"),
        "explanation": _description(before, after, actual_changes, handling, fchanges),
        "limitations": notes,
    }
    return {"baseline": before, "scenario": after, "comparison": comparison}
