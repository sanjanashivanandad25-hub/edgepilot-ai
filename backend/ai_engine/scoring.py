"""Transparent weighted multi-criteria suitability scoring (v3).

Qualitative tier profiles are hypotheses. Unknown cost uses a transparent neutral
prior of 50; never confuse the placeholder with observed affordability.
"""
from .config import TIERS, FACTORS, PROFILES
from .metrics import field_source


def weights(workload):
    bandwidth_scalability = {"low": 3, "medium": 5, "high": 7}[workload["bandwidth_requirement"]]
    concurrent_users = workload.get("concurrent_users", 0)
    if concurrent_users >= 10000:
        bandwidth_scalability = max(bandwidth_scalability, 9)
    elif concurrent_users >= 1000:
        bandwidth_scalability = max(bandwidth_scalability, 7)

    return {
        "latency": 6 if workload["latency_requirement_ms"] <= 50 else (5 if workload["latency_requirement_ms"] <= 100 else (3 if workload["latency_requirement_ms"] <= 150 else 1)),
        "privacy": {"low": 1, "medium": 4, "high": 22}[workload["privacy_requirement"]],
        "data_locality": 1,
        "resilience": {"low": 1, "medium": 3, "high": 10}[workload["criticality"]],
        "scalability": bandwidth_scalability,
        "affordability": 5,
    }


def clamp(n):
    return max(0.0, min(100.0, float(n)))


def latency_score(actual, deadline):
    # Below the deadline, reward headroom; above, proportionally penalize.
    # 0 ms -> 100, deadline -> 75, 2*deadline -> 0.
    if actual <= deadline:
        return clamp(100 - 25 * actual / deadline)
    return clamp(75 - 75 * (actual - deadline) / deadline)


def affordability_score(cost, budget):
    if budget == 0:
        return 100.0 if cost == 0 else 0.0
    return clamp(100 - 100 * cost / budget)


def relative_cost_score(cost, known_costs):
    low, high = min(known_costs), max(known_costs)
    if low == high:
        return 50.0
    return clamp(100 * (high - cost) / (high - low))


def _readiness(record):
    if record.get("latency_ms") is not None and record.get("source") == "measured":
        return "measured"
    return "estimated" if "latency_ms" in record else "heuristic"


def calculate(workload, metrics, blocked):
    importance = weights(workload)
    denominator = sum(importance.values())
    known_costs = [
        record["monthly_cost_inr"]
        for record in metrics.values()
        if record.get("monthly_cost_inr") is not None
    ]
    scores, breakdown, qualifications = {}, {}, {}
    for tier in TIERS:
        factor_scores = {**PROFILES[tier], "affordability": 50.0}
        origins = {factor: "heuristic_profile" for factor in PROFILES[tier]}
        origins["affordability"] = "unknown_neutral_prior"
        tier_metric = metrics.get(tier, {})
        if "latency_ms" in tier_metric:
            factor_scores["latency"] = latency_score(tier_metric["latency_ms"], workload["latency_requirement_ms"])
            origins["latency"] = f'{field_source(tier_metric, "latency_ms")}_end_to_end_latency'
        if "monthly_cost_inr" in tier_metric:
            budget_score = affordability_score(tier_metric["monthly_cost_inr"], workload["budget_monthly"])
            relative_score = relative_cost_score(tier_metric["monthly_cost_inr"], known_costs)
            factor_scores["affordability"] = 0.25 * budget_score + 0.75 * relative_score
            origins["affordability"] = f'{field_source(tier_metric, "monthly_cost_inr")}_monthly_cost'
        # Report a verified availability input when known; avoid pretending
        # it is identical to reliability without a validated transformation.
        breakdown[tier] = {
            factor: {"value": round(factor_scores[factor], 1),
                     "weight": importance[factor],
                     "origin": origins[factor],
                     "weighted_contribution": round(factor_scores[factor] * importance[factor] / denominator, 2)}
            for factor in FACTORS
        }
        unblocked = not bool(blocked[tier])
        score = sum(factor_scores[f] * importance[f] for f in FACTORS) / denominator
        scores[tier] = round(score, 1) if unblocked else 0.0
        qualifications[tier] = "eligible" if unblocked else "infeasible"
    return scores, breakdown, qualifications


def decision_drivers(winner, runner_up, breakdown):
    if not winner or not runner_up:
        return []
    result = []
    for name, field in breakdown[winner].items():
        other = breakdown[runner_up][name]
        delta = field["weighted_contribution"] - other["weighted_contribution"]
        result.append({"factor": name, "advantage_points": round(delta, 2),
                       "winner_origin": field["origin"], "runner_up_origin": other["origin"]})
    return sorted(result, key=lambda x: (-x["advantage_points"], x["factor"]))
