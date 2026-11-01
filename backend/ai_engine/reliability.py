"""Stage 7 reliability gate for EdgePilot's deterministic decision support.

Non-breaking, OPT-IN boundary: `guarded_recommendation` composes Stage 1-6.
Checks schema, invariants, provenance, and policy consistency; does not claim
benchmarks/prices are independently audited or that generated prose is true.
"""
from copy import deepcopy
import json
from math import isfinite

from .config import TIERS
from .validation import validate, REQUIRED, IDENTIFIERS
from .grounded_explanations import explain_recommendation
from .optimization import analyze_optimization

# Do not quietly accept arbitrary public request fields, which the engine might ignore.
OPTIONAL_FIELDS = frozenset({
    "model_ram_required_mb", "device_available_ram_mb", "concurrent_users",
    "bandwidth_available_mbps", "minimum_network_bandwidth_mbps",
    "minimum_availability_percent", "require_offline", "allow_remote_processing",
    "network_available", "allowed_tiers", "allowed_data_regions",
    *IDENTIFIERS,
})
ALLOWED_FIELDS = frozenset(REQUIRED) | OPTIONAL_FIELDS
MAX_REQUEST_BYTES = 24 * 1024


class ReliabilityError(ValueError):
    """An invariant failed: do not publish the result as an accepted recommendation."""


def validate_external_request(payload):
    """Strict opt-in API boundary. Use BEFORE calling core functions on public input.

    Existing loose `validate` remains unchanged for compatibility. Unknown keys
    are rejected so misspellings cannot be silently interpreted as missing data.
    """
    if not isinstance(payload, dict) or set(payload) != {"workload"}:
        raise ValueError("Public request must contain exactly one top-level 'workload' object")
    workload = validate(payload)
    unknown = set(workload) - ALLOWED_FIELDS
    if unknown:
        raise ValueError("Unsupported workload field(s): " + ", ".join(sorted(unknown)))
    # Reject non-standard JSON floats (NaN, Infinity) and oversized requests.
    serialized = json.dumps(payload, allow_nan=False, ensure_ascii=False)
    if len(serialized.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("Request exceeds the 24 KiB limit")
    for k, v in workload.items():
        if isinstance(v, str) and any(ord(c) < 32 for c in v):
            raise ValueError(f"Control character in workload.{k}")
    return workload


def _number(value, low=0.0, high=None):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and isfinite(value) and value >= low and (high is None or value <= high))


def _expected_sla_status(value, source, met, verified_sources):
    if value is None:
        return "unknown"
    if met:
        return "pass" if source in verified_sources else "provisional_pass"
    return "fail" if source in verified_sources else "provisional_fail"


def _architecture_issues(arch, prefix):
    if not isinstance(arch, dict):
        return [f"{prefix}: architecture must be an object"]
    nodes, edges = arch.get("nodes"), arch.get("connections")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return [f"{prefix}: nodes and connections must be lists"]
    ids = []
    errors = []
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"]:
            errors.append(f"{prefix}: invalid node")
        else:
            ids.append(node["id"])
    if len(ids) != len(set(ids)):
        errors.append(f"{prefix}: duplicate architecture node ID")
    for edge in edges:
        if (not isinstance(edge, dict) or edge.get("source") not in ids or edge.get("target") not in ids):
            errors.append(f"{prefix}: dangling architecture connection")
    return errors


def audit_recommendation(payload, result):
    """Static, deterministic QA of a computed recommendation; no network calls.

    status=pass_with_caveats when provisional or incomplete evidence is correctly
    disclosed. errors MUST stop the handoff; warnings are non-fatal audit notes.
    """
    workload = validate_external_request(payload)
    errors, warnings = [], []
    if not isinstance(result, dict):
        return {"status": "fail", "errors": ["Result must be an object"], "warnings": [], "check_categories": []}
    details = result.get("details", {})
    if not isinstance(details, dict):
        return {"status": "fail", "errors": ["Missing result details"], "warnings": [], "check_categories": []}
    scores = result.get("scores")
    feas = details.get("feasibility")
    ranks = details.get("ranking")
    if not isinstance(scores, dict) or set(scores) != set(TIERS):
        errors.append("Exactly four tier scores are required")
        scores = {}
    elif any(not _number(scores[t], 0, 100) for t in TIERS):
        errors.append("Scores must be finite values in [0, 100]")
    if not isinstance(feas, dict) or set(feas) != set(TIERS):
        errors.append("Feasibility must cover all four tiers")
        feas = {}
    if not isinstance(ranks, list) or any(t not in TIERS for t in ranks) or len(set(ranks)) != len(ranks):
        errors.append("Ranking must list unique recognized tiers")
        ranks = []
    recommendable = []
    if len(feas) == len(TIERS):
        for tier in TIERS:
            f = feas[tier]
            if not isinstance(f, dict) or type(f.get("eligible")) is not bool or not isinstance(f.get("reasons"), list):
                errors.append(f"Malformed feasibility for {tier}")
                continue
            if f["eligible"] and f["reasons"]:
                errors.append(f"{tier} marked eligible despite exclusion reasons")
            if not f["eligible"] and not f["reasons"]:
                errors.append(f"{tier} marked excluded without reasons")
            if not f["eligible"] and scores.get(tier) != 0:
                errors.append(f"Excluded tier {tier} must have zero selectable score")
        sla_checks = details.get("sla_checks")
        if not isinstance(sla_checks, dict) or set(sla_checks) != set(TIERS):
            errors.append("Latency and budget status checks must cover all four tiers")
            sla_checks = {}
        estimates = details.get("tier_estimates", {})
        for tier in TIERS:
            checks = sla_checks.get(tier, {})
            if (
                not isinstance(checks, dict)
                or type(checks.get("latency_pass")) is not bool
                or type(checks.get("cost_pass")) is not bool
                or type(checks.get("eligible")) is not bool
                or type(checks.get("selectable")) is not bool
                or checks.get("latency_status") not in ("pass", "provisional_pass", "provisional_fail", "fail", "unknown")
                or checks.get("cost_status") not in ("pass", "provisional_pass", "provisional_fail", "fail", "unknown")
            ):
                errors.append(f"Malformed latency and budget checks for {tier}")
                continue
            metric = estimates.get(tier, {}) if isinstance(estimates, dict) else {}
            expected_latency_pass = metric.get("latency_target_met") is True
            expected_cost_pass = metric.get("budget_met") is True
            expected_eligible = expected_latency_pass and expected_cost_pass
            expected_latency_status = _expected_sla_status(
                metric.get("latency_ms"), metric.get("latency_source"),
                expected_latency_pass, ("measured",)
            )
            expected_cost_status = _expected_sla_status(
                metric.get("monthly_cost_inr"), metric.get("cost_source"),
                expected_cost_pass, ("measured", "quoted")
            )
            if checks.get("eligible") is not expected_eligible:
                errors.append(f"Combined SLA eligibility is inconsistent for {tier}")
            if checks["latency_pass"] is not expected_latency_pass or checks["cost_pass"] is not expected_cost_pass:
                errors.append(f"Numeric SLA results are inconsistent for {tier}")
            if checks["latency_status"] != expected_latency_status or checks["cost_status"] != expected_cost_status:
                errors.append(f"SLA verification status is inconsistent with metric provenance for {tier}")
            expected_selectable = (
                feas[tier].get("eligible", False)
                and metric.get("latency_ms") is not None
                and metric.get("monthly_cost_inr") is not None
                and checks["latency_status"] != "fail"
                and checks["cost_status"] != "fail"
            )
            if checks.get("selectable") is not expected_selectable:
                errors.append(f"Selectable status is inconsistent with feasibility and evidence for {tier}")
            if expected_selectable:
                recommendable.append(tier)
        if set(ranks) != set(recommendable):
            errors.append("Ranking and tiers without verified SLA violations disagree")
        if len(scores) == len(TIERS) and all(_number(v, 0, 100) for v in scores.values()):
            expected = sorted(recommendable, key=lambda t: (-scores[t], TIERS.index(t)))
            if ranks != expected:
                errors.append("Ranking is not sorted by suitability among selectable tiers")
            if result.get("recommended_tier") != (expected[0] if expected else None):
                errors.append("Recommended tier is not the highest-ranked selectable tier")
    if result.get("recommended_tier") not in (None, *TIERS):
        errors.append("Unrecognized recommended tier")
    if result.get("recommended_tier") is None and recommendable:
        errors.append("No winner despite selectable tiers")

    estimates = result.get("estimates")
    tiers = details.get("tier_estimates", {})
    winner = result.get("recommended_tier")
    if not isinstance(tiers, dict) or set(tiers) != set(TIERS):
        errors.append("Missing per-tier latency/cost evidence for four tiers")
    else:
        for tier in TIERS:
            metric = tiers[tier]
            if not isinstance(metric, dict):
                errors.append(f"{tier}: metrics must be an object")
                continue
            for key, source_key in (("latency_ms", "latency_source"), ("monthly_cost_inr", "cost_source")):
                value, source = metric.get(key), metric.get(source_key)
                if value is not None and (not _number(value, 0) or source not in ("measured", "quoted", "estimated")):
                    errors.append(f"{tier}: invalid {key} / provenance pair")
                if value is None and source in ("measured", "quoted", "estimated"):
                    errors.append(f"{tier}: {key} has source without value")
                if value is not None:
                    original_field = "monthly_cost_inr" if key == "monthly_cost_inr" else "latency_ms"
                    provenance = details.get("metric_provenance", {}).get(tier, {}).get(original_field, {})
                    if not isinstance(provenance, dict) or provenance.get("source") != source:
                        errors.append(f"{tier}: {key} source disagrees with evidence provenance")
        if not isinstance(estimates, dict) or estimates.get("currency") != "INR":
            errors.append("Top-level estimates missing or invalid currency")
        elif winner in tiers:
            metric = tiers[winner]
            for out_key, internal_key in (("latency_ms", "latency_ms"), ("monthly_cost", "monthly_cost_inr")):
                expected_value = metric.get(internal_key)
                if expected_value is not None:
                    expected_value = round(expected_value, 2)
                if estimates.get(out_key) != expected_value:
                    errors.append(f"{out_key} disagrees with selected tier metrics")
        elif winner is None and (estimates.get("latency_ms") is not None or estimates.get("monthly_cost") is not None):
            errors.append("No winner must not claim winner's cost or latency")

    errors.extend(_architecture_issues(result.get("architecture"), "selected"))
    bench = details.get("benchmark", {})
    if isinstance(bench, dict) and bench.get("status") == "matched":
        fields = {"model_name": "model", "target_device": "device", "runtime": "runtime", "precision": "precision"}
        for k, m in fields.items():
            a, b = workload.get(k), bench.get(m)
            if not isinstance(a, str) or not isinstance(b, str) or " ".join(a.casefold().split()) != " ".join(b.casefold().split()):
                errors.append(f"Benchmark mismatch: {k}")
        if bench.get("measurement_scope") != "on_device_model_inference_only_not_end_to_end":
            errors.append("Benchmark scope is not model inference only")
        if not _number(bench.get("inference_latency_ms"), 0) or bench.get("inference_latency_ms") == 0:
            errors.append("Invalid benchmark inference time")
        if details.get("benchmark_used_to_score_tier") is not False:
            errors.append("Inference-only benchmark must not drive end-to-end tier scoring")
        warnings.append("Hardware benchmark is model-inference-only, not application E2E latency")

    if "optimization" in details:
        opt = details["optimization"]
        if not isinstance(opt, dict) or "hybrid" not in opt or "pareto" not in opt or "cost_break_even" not in opt:
            errors.append("Malformed optimization response")
        else:
            hy = opt["hybrid"]
            if hy.get("status") == "candidate_requires_validation":
                if workload.get("allow_remote_processing") is not True or workload.get("require_offline") is True or workload.get("network_available") is False:
                    errors.append("Hybrid proposed despite blocked remote-processing policy")
                errors.extend(_architecture_issues(hy, "hybrid"))
                warnings.append("Hybrid architecture is a candidate; validation is required")
            pareto = opt["pareto"]
            if not isinstance(pareto, dict) or any(t not in TIERS for t in pareto.get("non_dominated_tiers", [])):
                errors.append("Invalid Pareto tier identifiers")
            else:
                for t in pareto.get("non_dominated_tiers", []):
                    if not feas.get(t, {}).get("eligible", False):
                        errors.append(f"Pareto contains infeasible tier: {t}")

    if result.get("details", {}).get("status") == "provisional":
        warnings.append("Tier rankings are provisional heuristics, not confidence probabilities")
    if winner and isinstance(details.get("evidence_gaps"), dict) and details["evidence_gaps"].get(winner):
        warnings.append("Winning tier has unverified requirements; display evidence gaps")
    if details.get("explainability", {}).get("answer_source") == "qualcomm_llm":
        warnings.append("LLM output is generated prose, not independent factual verification")
    return {
        "status": "fail" if errors else "pass_with_caveats" if warnings else "pass",
        "errors": errors,
        "warnings": list(dict.fromkeys(warnings)),
        "check_categories": ["public_input", "ranking_feasibility", "tier_metrics_provenance",
                             "architecture", "benchmark_identity_scope", "optimization_policy", "uncertainty"],
        "method": "edgepilot_stage7_invariant_audit_v1",
        "audit_scope": "Decision consistency, schema, provenance and policy invariants only",
    }


def guarded_recommendation(payload, *, benchmark_catalog, metrics_by_tier=None,
                           cost_curves=None, llm=None, question="why_recommended", alternative_tier=None):
    """Opt-in Stage 7 backend entrypoint, preserving existing top-level response keys.

    Raises ReliabilityError on internally inconsistent results; no deployment action.
    For high-volume slider simulations use Stage 5 functions without LLM calls.
    """
    validate_external_request(payload)
    result = explain_recommendation(deepcopy(payload), benchmark_catalog=benchmark_catalog,
                                    metrics_by_tier=metrics_by_tier, llm=llm,
                                    question=question, alternative_tier=alternative_tier)
    result["details"]["optimization"] = analyze_optimization(payload, result, cost_curves=cost_curves)
    report = audit_recommendation(payload, result)
    if report["errors"]:
        raise ReliabilityError("EdgePilot result failed internal audit: " + "; ".join(report["errors"]))
    result["details"]["reliability"] = report
    return result
