"""Sampled, deterministic one-factor-at-a-time sensitivity analysis.

This is NOT mathematical optimization of a continuous black box and must never
be described as an exact threshold or globally optimal change. All candidate
input sets are explicit, recorded, bounded, and passed through the same engine.
"""
from copy import deepcopy
from .benchmarked import recommend_with_benchmarks
from .config import TIERS
from .scenarios import simulate_scenario
from .validation import validate

CANDIDATE_FIELDS = (
    "privacy_requirement", "criticality", "bandwidth_requirement",
    "latency_requirement_ms", "budget_monthly", "concurrent_users",
    "require_offline", "allow_remote_processing", "network_available",
    "device_available_ram_mb", "bandwidth_available_mbps",
)


def _alternatives(payload, field):
    w = payload["workload"]
    if field in ("privacy_requirement", "criticality", "bandwidth_requirement"):
        return ["low", "medium", "high"]
    if field == "latency_requirement_ms":
        current = float(w["latency_requirement_ms"])
        return sorted({10, 25, 50, 100, 150, 250, 500, 1000, current / 2, current * 2})
    if field == "budget_monthly":
        b = float(w["budget_monthly"])
        return sorted({0, 250, 500, 1000, 2000, 5000, 10000, max(b / 2, 0), b * 2})
    if field == "concurrent_users":
        return [1, 50, 500, 1000, 5000, 10000, 50000]
    if field in ("require_offline", "allow_remote_processing", "network_available"):
        return [True, False]
    if field == "device_available_ram_mb":
        if "model_ram_required_mb" not in w:
            return []  # No meaningful memory fit test without a known model need.
        need = float(w["model_ram_required_mb"])
        return sorted({max(1.0, need / 2), need, need * 1.5, need * 2})
    if field == "bandwidth_available_mbps":
        return [0, 1, 5, 10, 20, 50, 100]
    return []


def discover_flips(payload, *, benchmark_catalog, metrics_by_tier=None,
                   target_tier=None, fields=None, max_evaluations=100, max_results=8):
    """Return actual observed winner flips, each with a reproducible workload change.

    No live LLM calls; no fake performance. The engine evaluates each candidate.
    If model/network/load changes and fresh scenario metrics aren't provided,
    baseline metrics are invalidated (see scenarios.py). Thus some flips may be
    solely due to loss of numerical evidence; caller should inspect metrics_mode.
    """
    validate(payload)
    if target_tier is not None and target_tier not in TIERS:
        raise ValueError("target_tier must be one of the four deployment tiers")
    if isinstance(max_evaluations, bool) or not isinstance(max_evaluations, int) or not 1 <= max_evaluations <= 200:
        raise ValueError("max_evaluations must be an integer between 1 and 200")
    if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 30:
        raise ValueError("max_results must be an integer between 1 and 30")
    if fields is None:
        fields = list(CANDIDATE_FIELDS)
    if not isinstance(fields, (list, tuple)) or len(fields) > len(CANDIDATE_FIELDS) or len(set(fields)) != len(fields):
        raise ValueError("fields must be a unique list of supported sensitivity dimensions")
    if any(f not in CANDIDATE_FIELDS for f in fields):
        raise ValueError("Unsupported sensitivity dimension")

    baseline = recommend_with_benchmarks(payload, benchmark_catalog=benchmark_catalog,
                                         metrics_by_tier=metrics_by_tier, llm=None)
    original = baseline["recommended_tier"]
    candidates = []
    evaluations = 0
    counts = {"flips": 0, "same": 0, "error": 0}
    for field in fields:
        for value in _alternatives(payload, field):
            if value == payload["workload"].get(field):
                continue
            if evaluations >= max_evaluations:
                break
            evaluations += 1
            try:
                result = simulate_scenario(payload, changes={field: value},
                                           benchmark_catalog=benchmark_catalog,
                                           metrics_by_tier=metrics_by_tier)
            except ValueError:
                counts["error"] += 1
                continue
            new = result["comparison"]["new_tier"]
            if new == original:
                counts["same"] += 1
                continue
            counts["flips"] += 1
            if target_tier is not None and new != target_tier:
                continue
            detail = result["comparison"]
            candidates.append({
                "field": field,
                "from": deepcopy(payload["workload"].get(field)),
                "to": deepcopy(value),
                "from_tier": original,
                "to_tier": new,
                "score_deltas": detail["score_deltas"],
                "feasibility_changes": detail["feasibility_changes"],
                "metrics_mode": detail["metrics_handling"]["mode"],
                "description": detail["explanation"],
            })
        if evaluations >= max_evaluations:
            break
    # In deterministic search order: one-field changes only, preserving field priority.
    # Never describe results as minimal numerical thresholds or global optima.
    return {
        "baseline_tier": original,
        "target_tier": target_tier,
        "method": "sampled_one_factor_at_a_time_v1",
        "evaluations": evaluations,
        "candidate_flips_found": len(candidates),
        "counts": counts,
        "flips": candidates[:max_results],
        "truncated": len(candidates) > max_results or evaluations >= max_evaluations,
        "limitations": [
            "Discrete hypothetical samples, not an exhaustive search or exact switching thresholds.",
            "A one-field change can be insufficient even when a two-field combination could change the winner.",
            "Workload changes may invalidate old cost and end-to-end latency evidence; resupply fresh scenario metrics for numerical comparisons.",
            "Suitability scores use the current uncalibrated engine and are not deployment guarantees.",
        ],
    }
