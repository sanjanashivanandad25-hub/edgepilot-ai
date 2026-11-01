"""Add-on Person 2 entrypoint. Existing recommend() API remains untouched.

Use this while integrating benchmark matching; Person 3 can call it directly.
"""
from copy import deepcopy
from .benchmark_registry import match_benchmark
from .recommender import recommend


def recommend_with_benchmarks(payload, *, benchmark_catalog, metrics_by_tier=None, llm=None):
    if not isinstance(payload, dict) or not isinstance(payload.get("workload"), dict):
        raise ValueError("Request requires a workload object")
    matched = match_benchmark(payload["workload"], benchmark_catalog)

    # Any old manually pinned inference-time value must NOT be reused when the
    # selected workload differs from the benchmark. Preserve unrelated metrics.
    safe_metrics = deepcopy(metrics_by_tier or {})
    if "on_device" in safe_metrics:
        safe_metrics["on_device"].pop("inference_latency_ms", None)
        if set(safe_metrics["on_device"]) <= {"source", "source_note"}:
            safe_metrics.pop("on_device")
    if matched["status"] == "matched":
        # A per-tier metrics record has just one source label. Never mix an
        # unrelated pricing quote or E2E estimate with a Workbench measurement
        # under one provenance flag; the benchmark remains in details in that case.
        if "on_device" not in safe_metrics:
            safe_metrics["on_device"] = {
                "source": "measured",
                "source_note": (matched["source_type"] + ": " + matched["source_reference"])[:240],
                "inference_latency_ms": matched["inference_latency_ms"],
            }

    result = recommend(payload, metrics_by_tier=safe_metrics or None, llm=llm)
    result["details"]["benchmark"] = matched
    result["details"]["benchmark_used_to_score_tier"] = False
    if matched["status"] == "matched":
        result["warnings"].append(
            "Matched Qualcomm benchmark measures only model inference; it was NOT used as total latency or to change tier ranking."
        )
    elif matched["status"] in ("no_match", "incomplete_selection"):
        result["warnings"].append("No matching on-device inference benchmark: " + matched["reason"])
    return result
