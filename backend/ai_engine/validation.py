"""Input validation for frozen team API plus optional decision-engine v2 inputs."""
from math import isfinite
from .config import TIERS

REQUIRED = ("latency_requirement_ms", "bandwidth_requirement", "budget_monthly", "privacy_requirement", "criticality")
LEVELS = ("low", "medium", "high")
IDENTIFIERS = ("application_type", "model_name", "target_device", "runtime", "precision")


def finite_number(value, name, *, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < 0 or (not allow_zero and value == 0):
        raise ValueError(f"{name} must be {'nonnegative' if allow_zero else 'positive'}")
    return float(value)


def _nonempty_string(value, name, max_len=128):
    if not isinstance(value, str) or not value.strip() or len(value) > max_len:
        raise ValueError(f"{name} must be a nonempty string of at most {max_len} characters")
    return value


def validate(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("workload"), dict):
        raise ValueError("Request requires a JSON object containing 'workload' object")
    workload = payload["workload"]
    for name in REQUIRED:
        if name not in workload:
            raise ValueError(f"Missing workload field: {name}")
    finite_number(workload["latency_requirement_ms"], "latency_requirement_ms")
    finite_number(workload["budget_monthly"], "budget_monthly", allow_zero=True)
    for name in ("bandwidth_requirement", "privacy_requirement", "criticality"):
        if not isinstance(workload[name], str) or workload[name] not in LEVELS:
            raise ValueError(f"{name} must be 'low', 'medium', or 'high'")
    for name in ("model_ram_required_mb", "device_available_ram_mb", "concurrent_users", "bandwidth_available_mbps", "minimum_network_bandwidth_mbps", "minimum_availability_percent"):
        if name in workload and workload[name] is not None:
            v = finite_number(workload[name], name, allow_zero=name in ("concurrent_users", "bandwidth_available_mbps"))
            if name == "minimum_availability_percent" and not 0 < v <= 100:
                raise ValueError("minimum_availability_percent must be in (0, 100]")
            if name == "concurrent_users" and not v.is_integer():
                raise ValueError("concurrent_users must be a whole number")
    for name in ("require_offline", "allow_remote_processing", "network_available"):
        if name in workload and not isinstance(workload[name], bool):
            raise ValueError(f"{name} must be boolean")
    for name in IDENTIFIERS:
        if name in workload and workload[name] is not None:
            _nonempty_string(workload[name], name)
    if "allowed_tiers" in workload:
        allowed = workload["allowed_tiers"]
        if not isinstance(allowed, list) or not allowed or any(not isinstance(t, str) or t not in TIERS for t in allowed):
            raise ValueError("allowed_tiers must be a nonempty list of recognized tiers")
        if len(set(allowed)) != len(allowed):
            raise ValueError("allowed_tiers must not contain duplicates")
    if "allowed_data_regions" in workload:
        regions = workload["allowed_data_regions"]
        if not isinstance(regions, list) or not regions or len(regions) > 40:
            raise ValueError("allowed_data_regions must be a nonempty list of regions")
        for region in regions:
            _nonempty_string(region, "allowed_data_regions item", max_len=80)
        if len({r.strip().casefold() for r in regions}) != len(regions):
            raise ValueError("allowed_data_regions contains duplicate regions")
    return workload
