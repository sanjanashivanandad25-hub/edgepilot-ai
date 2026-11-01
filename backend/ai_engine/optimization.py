"""Stage 6: conservative multi-objective decision support for EdgePilot.

Additive to Stages 1-5. No real deployment, no invented measurements.
Pareto requires comparable workload-specific end-to-end latency AND monthly cost.
Hybrid is an explicitly conditional architecture candidate, never a fifth scored tier.
Break-even requires scenario-matched cost curves supplied by Person 3.
"""
from copy import deepcopy
from itertools import combinations
from math import isfinite

from .benchmarked import recommend_with_benchmarks
from .config import TIERS
from .validation import validate

_ALLOWED_SOURCES = frozenset({"estimated", "measured", "quoted"})
_MATCH_FIELDS = frozenset({"application_type", "model_name", "target_device", "runtime", "precision"})


def _nonnegative(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite, nonnegative number")
    return float(value)


def _positive(value, name):
    out = _nonnegative(value, name)
    if out <= 0:
        raise ValueError(f"{name} must be positive")
    return out


def _short(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 240:
        raise ValueError(f"{name} must be nonempty text (<=240 characters)")
    return value.strip()


def _snapshot(recommendation):
    if not isinstance(recommendation, dict) or not isinstance(recommendation.get("details"), dict):
        raise ValueError("recommendation must be an EdgePilot engine result")
    details = recommendation["details"]
    if not isinstance(details.get("tier_estimates"), dict) or not isinstance(details.get("feasibility"), dict):
        raise ValueError("Stage 3 tier_estimates and feasibility are required")
    return details


def pareto_frontier(recommendation):
    """Non-dominated latency/cost frontier among eligible tiers with BOTH E2E metrics.

    This is NOT a global frontier when some eligible tiers lack comparable inputs.
    Estimated values imply conditional, not verified dominance.
    """
    details = _snapshot(recommendation)
    known = {}
    skipped = {}
    for tier in TIERS:
        feas = details["feasibility"].get(tier, {})
        if not feas.get("eligible", False):
            skipped[tier] = "Excluded by the core feasibility engine"
            continue
        metrics = details["tier_estimates"].get(tier, {})
        latency, cost = metrics.get("latency_ms"), metrics.get("monthly_cost_inr")
        lsource, csource = metrics.get("latency_source"), metrics.get("cost_source")
        if latency is None or cost is None or lsource not in _ALLOWED_SOURCES or csource not in _ALLOWED_SOURCES:
            skipped[tier] = "Requires supported end-to-end latency and monthly cost for the same workload"
            continue
        known[tier] = {
            "end_to_end_latency_ms": latency, "monthly_cost_inr": cost,
            "latency_source": lsource, "cost_source": csource,
        }
    dominating = {}
    for candidate, values in known.items():
        dominates = []
        for other, other_values in known.items():
            if other == candidate:
                continue
            if (other_values["end_to_end_latency_ms"] <= values["end_to_end_latency_ms"]
                    and other_values["monthly_cost_inr"] <= values["monthly_cost_inr"]
                    and (other_values["end_to_end_latency_ms"] < values["end_to_end_latency_ms"]
                         or other_values["monthly_cost_inr"] < values["monthly_cost_inr"])):
                dominates.append(other)
        dominating[candidate] = dominates
    frontier = [tier for tier in TIERS if tier in known and not dominating[tier]]
    all_eligible = [t for t in TIERS if details["feasibility"].get(t, {}).get("eligible")]
    uncertain = any(v["latency_source"] == "estimated" or v["cost_source"] == "estimated"
                    for v in known.values())
    synthetic = any("demo" in (str(details.get("metric_provenance", {}).get(t, {})).casefold())
                    for t in known)
    return {
        "status": "insufficient_comparable_data" if len(known) < 2 else
                  "partial_comparison" if len(known) < len(all_eligible) else
                  "provisional_estimates" if uncertain else "supported_comparison",
        "non_dominated_tiers": frontier if len(known) >= 2 else [],
        "dominated_by": dominating if len(known) >= 2 else {},
        "compared_tiers": known,
        "excluded_or_missing": skipped,
        "all_eligible_tiers_compared": len(known) == len(all_eligible) and len(known) >= 2,
        "contains_estimates": uncertain,
        "contains_demo_inputs": synthetic,
        "note": "Pareto dominance compares eligible tiers on the supplied E2E latency and monthly cost only; estimated or demo figures are hypothetical and do not imply verified real-world performance.",
    }


def hybrid_architecture(payload, recommendation):
    """A cautious optional *candidate*, not a recommended tier or proved split.

    Requires explicit remote-processing permission and locally fitting model memory.
    Restricts remote work to optional asynchronous analytics; critical inference stays local.
    """
    workload = validate(payload)
    details = _snapshot(recommendation)
    reasons = []
    if workload.get("allow_remote_processing") is not True:
        reasons.append("Explicit allow_remote_processing=true is required to propose a hybrid split")
    if workload.get("require_offline") is True:
        reasons.append("Offline-only policy prohibits remote analytics")
    if workload.get("network_available") is False or workload.get("bandwidth_available_mbps") == 0:
        reasons.append("No available network path for the optional remote stage")
    local = details["feasibility"].get("on_device", {})
    if not local.get("eligible", False):
        reasons.append("On-device stage is excluded by hard constraints")
    need, available = workload.get("model_ram_required_mb"), workload.get("device_available_ram_mb")
    if need is None or available is None:
        reasons.append("Local model memory requirement and available device memory must be provided")
    elif need > available:
        reasons.append("Local model does not fit available device memory")
    candidates = [tier for tier in details.get("ranking", ())
                  if tier != "on_device" and details["feasibility"].get(tier, {}).get("eligible")]
    if not candidates:
        reasons.append("No eligible remote analytics tier")
    if reasons:
        return {"status": "not_proposed", "reasons": reasons, "nodes": [], "connections": [],
                "note": "Hybrid is optional and separate from the required four-tier ranking."}
    remote = candidates[0]
    node_type = "cloud" if remote == "cloud" else "edge"
    checks = [
        "Validate that local inference really works on the selected hardware; memory fit alone is not enough",
        "Validate that only permitted, minimized data leaves the device; do not assume anonymization is perfect",
        "Measure data-transfer, asynchronous analytics latency, and total hybrid operating cost",
        "Verify encrypted communication, access control, data residency, and consent before deployment",
        "Validate remote service failure handling; never make critical local decisions depend on optional cloud analytics",
    ]
    if workload["privacy_requirement"] == "high":
        checks.append("High privacy: verify de-identification policy and legal basis for each transmitted field")
    return {
        "status": "candidate_requires_validation", "remote_analytics_tier": remote,
        "nodes": [
            {"id": "device", "label": "Source Device", "type": "device", "role": "data_source"},
            {"id": "local_inference", "label": "Local Time-Critical Inference", "type": "device", "role": "critical_inference"},
            {"id": "local_filter", "label": "Local Output Filtering", "type": "device", "role": "data_minimization"},
            {"id": "remote_analytics", "label": remote.replace("_", " ").title() + " Analytics", "type": node_type,
             "role": "optional_async_analytics"},
        ],
        "connections": [
            {"source": "device", "target": "local_inference", "data": "raw input (local only)"},
            {"source": "local_inference", "target": "local_filter", "data": "inference outputs"},
            {"source": "local_filter", "target": "remote_analytics", "data": "approved summaries only"},
        ],
        "critical_path": ["device", "local_inference"],
        "optional_remote_path": ["local_filter", "remote_analytics"],
        "validation_checks": checks,
        "basis": "Rule-based architecture proposal, not a fifth scored deployment tier and not proof of feasibility or lower cost",
    }


def _validate_curves(payload, curves):
    workload = validate(payload)
    if curves is None:
        return None
    if not isinstance(curves, dict) or set(curves) != {"scenario_id", "workload_match", "tiers", "reference_monthly_requests"}:
        raise ValueError("cost_curves must contain scenario_id, workload_match, tiers, reference_monthly_requests")
    scenario_id = _short(curves["scenario_id"], "scenario_id")
    match = curves["workload_match"]
    if not isinstance(match, dict) or not match or set(match) - _MATCH_FIELDS:
        raise ValueError("workload_match must select supported workload identifiers")
    for key, value in match.items():
        _short(value, f"workload_match.{key}")
        current = workload.get(key)
        if not isinstance(current, str) or current.strip().casefold() != value.strip().casefold():
            raise ValueError(f"cost curves do not match request workload field: {key}")
    reference = _nonnegative(curves["reference_monthly_requests"], "reference_monthly_requests")
    tiers = curves["tiers"]
    if not isinstance(tiers, dict) or not tiers or set(tiers) - set(TIERS):
        raise ValueError("cost curves tiers must contain recognized deployment tiers")
    validated = {}
    for tier, item in tiers.items():
        if not isinstance(item, dict):
            raise ValueError(f"cost curve {tier} must be an object")
        expected = {"fixed_monthly_inr", "per_1000_requests_inr", "source", "source_reference",
                    "assumptions", "min_monthly_requests", "max_monthly_requests"}
        if set(item) != expected:
            raise ValueError(f"cost curve {tier} fields must be {sorted(expected)}")
        fixed = _nonnegative(item["fixed_monthly_inr"], f"{tier}.fixed_monthly_inr")
        rate = _nonnegative(item["per_1000_requests_inr"], f"{tier}.per_1000_requests_inr")
        lower = _nonnegative(item["min_monthly_requests"], f"{tier}.min_monthly_requests")
        upper = _positive(item["max_monthly_requests"], f"{tier}.max_monthly_requests")
        if lower >= upper:
            raise ValueError(f"{tier}: monthly request interval must be increasing")
        if item["source"] not in _ALLOWED_SOURCES:
            raise ValueError(f"{tier}: unsupported cost-curve source")
        reference_url = _short(item["source_reference"], f"{tier}.source_reference")
        assumptions = item["assumptions"]
        if not isinstance(assumptions, list) or len(assumptions) > 15 or any(
                not isinstance(a, str) or not a.strip() or len(a) > 240 for a in assumptions):
            raise ValueError(f"{tier}: assumptions must be a list of concise strings")
        if item["source"] == "estimated" and not assumptions:
            raise ValueError(f"{tier}: modeled cost curve must declare assumptions")
        validated[tier] = dict(item, fixed_monthly_inr=fixed, per_1000_requests_inr=rate,
                               min_monthly_requests=lower, max_monthly_requests=upper,
                               source_reference=reference_url)
    return scenario_id, reference, validated


def cost_break_even(payload, recommendation, cost_curves=None):
    """Linear *modeled* cost crosses, never promises real invoice prices.

    C = fixed monthly INR + per-1000-request INR * monthly_requests / 1000.
    Only expose crossings inside the valid range of both source curves.
    """
    parsed = _validate_curves(payload, cost_curves)
    if parsed is None:
        return {"status": "not_available", "reason": "No workload-matched, sourced cost curves from Person 3"}
    details = _snapshot(recommendation)
    scenario_id, requested_volume, curves = parsed
    usable = {tier: c for tier, c in curves.items() if details["feasibility"].get(tier, {}).get("eligible")}
    amounts = {}
    for tier, c in usable.items():
        if c["min_monthly_requests"] <= requested_volume <= c["max_monthly_requests"]:
            amounts[tier] = round(c["fixed_monthly_inr"] + c["per_1000_requests_inr"] * requested_volume / 1000, 2)
    ranked = sorted(amounts, key=lambda t: (amounts[t], TIERS.index(t)))
    crossings = []
    coincident = []
    for a, b in combinations([t for t in TIERS if t in usable], 2):
        x, y = usable[a], usable[b]
        low = max(x["min_monthly_requests"], y["min_monthly_requests"])
        high = min(x["max_monthly_requests"], y["max_monthly_requests"])
        if high < low:
            continue
        delta_rate = x["per_1000_requests_inr"] - y["per_1000_requests_inr"]
        delta_fixed = y["fixed_monthly_inr"] - x["fixed_monthly_inr"]
        if abs(delta_rate) <= 1e-10:
            if abs(delta_fixed) <= 1e-10:
                coincident.append({"tiers": [a, b], "shared_valid_range": [low, high]})
            continue
        crossing = delta_fixed * 1000 / delta_rate
        if low <= crossing <= high and crossing >= 0:
            cost = x["fixed_monthly_inr"] + x["per_1000_requests_inr"] * crossing / 1000
            crossings.append({"tiers": [a, b], "monthly_requests": round(crossing, 2),
                              "monthly_cost_inr": round(cost, 2),
                              "source_types": {a: x["source"], b: y["source"]},
                              "valid_volume_range": [low, high]})
    return {
        "status": "modeled" if len(usable) >= 2 else "insufficient_curves",
        "scenario_id": scenario_id,
        "reference_monthly_requests": requested_volume,
        "estimated_cost_at_reference_inr": amounts,
        "cheapest_eligible_at_reference": ranked[0] if ranked else None,
        "ranked_by_cost_at_reference": ranked,
        "pairwise_break_even_points": crossings,
        "identical_cost_curve_pairs": coincident,
        "unavailable_at_reference": [tier for tier in TIERS if tier not in amounts],
        "curves_used": {tier: {"source": c["source"], "source_reference": c["source_reference"],
                               "assumptions": c["assumptions"], "valid_volume_range": [c["min_monthly_requests"], c["max_monthly_requests"]]}
                        for tier, c in usable.items()},
        "note": "Pairwise intersections are conditional on Person 3's linear cost assumptions, not observed market prices or global optimization; cost alone does not decide deployment suitability.",
    }


def analyze_optimization(payload, recommendation, *, cost_curves=None):
    """Analyze a result without rerunning the engine. Useful for Person 3 integration."""
    validate(payload)
    return {
        "method": "stage6_multiobjective_v1",
        "pareto": pareto_frontier(recommendation),
        "hybrid": hybrid_architecture(payload, recommendation),
        "cost_break_even": cost_break_even(payload, recommendation, cost_curves),
    }


def optimize_deployment(payload, *, benchmark_catalog, metrics_by_tier=None,
                        cost_curves=None, llm=None):
    """Backward-compatible full result: original top-level fields unchanged."""
    recommendation = recommend_with_benchmarks(payload, benchmark_catalog=benchmark_catalog,
                                               metrics_by_tier=metrics_by_tier, llm=llm)
    output = deepcopy(recommendation)
    output["details"]["optimization"] = analyze_optimization(payload, recommendation,
                                                              cost_curves=cost_curves)
    return output
