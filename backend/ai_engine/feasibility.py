"""Hard-gate deployment tiers only from explicit policy or sufficiently evidenced violations.

Never infer a tier is *verified feasible* merely because no constraint blocked it.
"""
from .config import TIERS
from .metrics import field_source

EVIDENCED = ("measured", "quoted")
REMOTE = TIERS[1:]


def evaluate(workload, metrics):
    blocked = {tier: [] for tier in TIERS}
    allowed_tiers = workload.get("allowed_tiers")
    if allowed_tiers is not None:
        for tier in TIERS:
            if tier not in allowed_tiers:
                blocked[tier].append("Excluded by allowed_tiers policy.")

    if workload.get("require_offline", False) or workload.get("allow_remote_processing", True) is False:
        reason = "Offline-only operation is mandatory." if workload.get("require_offline", False) else "Remote processing is prohibited."
        for tier in REMOTE:
            blocked[tier].append(reason)
    if workload.get("network_available") is False or workload.get("bandwidth_available_mbps") == 0:
        for tier in REMOTE:
            blocked[tier].append("Network is unavailable for remote inference.")
    available_bw = workload.get("bandwidth_available_mbps")
    required_bw = workload.get("minimum_network_bandwidth_mbps")
    if available_bw is not None and required_bw is not None and available_bw < required_bw:
        for tier in REMOTE:
            blocked[tier].append("Available bandwidth is below the declared minimum for remote inference.")
    need = workload.get("model_ram_required_mb")
    available = workload.get("device_available_ram_mb")
    if need is not None and available is not None and need > available:
        blocked["on_device"].append(f"Model requires {need:g} MB RAM but device has {available:g} MB available.")

    deadline = workload["latency_requirement_ms"]
    budget = workload["budget_monthly"]
    allowed_regions = {r.strip().casefold() for r in workload.get("allowed_data_regions", ())}
    minimum_availability = workload.get("minimum_availability_percent")
    for tier, record in metrics.items():
        evidence = record.get("policy_source", record["source"]) in EVIDENCED
        if evidence and record.get("model_compatible") is False:
            blocked[tier].append("Verified model/hardware incompatibility.")
        if field_source(record, "latency_ms") == "measured" and record.get("latency_ms") is not None and record["latency_ms"] > deadline:
            blocked[tier].append("Measured end-to-end latency exceeds the application's deadline.")
        if field_source(record, "monthly_cost_inr") in EVIDENCED and record.get("monthly_cost_inr") is not None and record["monthly_cost_inr"] > budget:
            blocked[tier].append("Measured/quoted monthly cost exceeds the application budget.")
        if evidence and record.get("data_residency_compliant") is False:
            blocked[tier].append("Verified data residency compliance failure.")
        if evidence and allowed_regions and "deployment_region" in record and record["deployment_region"].casefold() not in allowed_regions:
            blocked[tier].append("Verified deployment region is not in allowed_data_regions.")
        if (field_source(record, "availability_percent") == "measured" and minimum_availability is not None
                and "availability_percent" in record and record["availability_percent"] < minimum_availability):
            blocked[tier].append("Measured availability is below the required minimum.")
    return blocked


def evidence_gaps(workload, metrics):
    """Return unverified requirements; these are *not* evidence of infeasibility."""
    gaps = {}
    for tier in TIERS:
        record = metrics.get(tier, {})
        checks = []
        if tier == "on_device":
            if workload.get("model_ram_required_mb") is None or workload.get("device_available_ram_mb") is None:
                checks.append("On-device memory fit not verified.")
            if record.get("model_compatible") is not True or record.get("policy_source", record.get("source")) not in EVIDENCED:
                checks.append("Model compatibility on device not verified.")
        else:
            if workload.get("network_available") is not False and workload.get("bandwidth_available_mbps") is None:
                checks.append("Available network bandwidth not measured.")
        if record.get("latency_ms") is None or field_source(record, "latency_ms") != "measured":
            checks.append("End-to-end latency deadline not verified by measurement.")
        if record.get("monthly_cost_inr") is None or field_source(record, "monthly_cost_inr") not in EVIDENCED:
            checks.append("Monthly cost not independently measured or quoted.")
        if workload.get("allowed_data_regions"):
            if record.get("deployment_region") is None or record.get("policy_source", record.get("source")) not in EVIDENCED:
                checks.append("Deployment region not independently verified.")
        if workload.get("minimum_availability_percent") is not None:
            if record.get("availability_percent") is None or field_source(record, "availability_percent") != "measured":
                checks.append("Service availability requirement not validated by measurement.")
        gaps[tier] = checks
    return gaps
