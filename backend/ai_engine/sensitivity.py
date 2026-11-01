"""Optional v1.1 counterfactual analysis: change one input and recompute.
Useful for 'Challenge this recommendation' without asking an LLM to invent claims.
"""
from copy import deepcopy
from .recommender import recommend
from .validation import validate


def compare_scenarios(payload, modifications, *, metrics_by_tier=None):
    validate(payload)
    if not isinstance(modifications, dict):
        raise ValueError("modifications must be a dict of workload fields")
    before = recommend(payload, metrics_by_tier=metrics_by_tier)
    modified_payload = deepcopy(payload)
    modified_payload["workload"].update(modifications)
    after = recommend(modified_payload, metrics_by_tier=metrics_by_tier)
    return {
        "original_recommendation": before["recommended_tier"],
        "new_recommendation": after["recommended_tier"],
        "changed": before["recommended_tier"] != after["recommended_tier"],
        "original_scores": before["scores"],
        "new_scores": after["scores"],
        "new_warnings": after["warnings"],
    }
