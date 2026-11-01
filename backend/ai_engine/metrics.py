"""Per-metric evidence with independent provenance (Stage 3).

Backward-compatible with Stage 2 flat records. Nested field evidence permits a
measured E2E latency and an estimated monthly cost on the *same tier* without
mislabeling either value. Inference-only measurements NEVER fill latency_ms.
"""
from .config import TIERS
from .validation import finite_number

VALID_SOURCES = ("measured", "quoted", "estimated", "demo")
NUMERIC = ("latency_ms", "monthly_cost_inr", "inference_latency_ms", "availability_percent")
BOOL_FIELDS = ("model_compatible", "data_residency_compliant")


def field_source(record, field):
    return record.get("field_sources", {}).get(field, record.get("source"))


def _text(value, name, max_len=500):
    if not isinstance(value, str) or not value.strip() or len(value) > max_len:
        raise ValueError(f"{name} must be nonempty text (max {max_len} chars)")
    return value.strip()


def _evidence(value, field, tier, tier_source, tier_note):
    label = f"metrics[{tier}].{field}"
    if isinstance(value, dict):
        source = value.get("source")
        if source not in VALID_SOURCES:
            raise ValueError(f"{label}.source must be one of {VALID_SOURCES}")
        measured_value = value.get("value")
        reference = _text(value.get("source_reference", ""), f"{label}.source_reference")
        method = _text(value.get("method", ""), f"{label}.method", 240)
        assumptions = value.get("assumptions", [])
        if not isinstance(assumptions, list) or len(assumptions) > 15 or any(
                not isinstance(x, str) or not x.strip() or len(x) > 240 for x in assumptions):
            raise ValueError(f"{label}.assumptions must be a list of short strings")
        if source == "estimated" and not assumptions:
            raise ValueError(f"{label}: modeled estimates must declare assumptions")
        scope = value.get("scope", "end_to_end" if field == "latency_ms" else "cost" if field == "monthly_cost_inr" else "model_inference_only")
        if field == "latency_ms" and scope != "end_to_end":
            raise ValueError(f"{label}: only end-to-end scope can populate latency_ms")
        if field == "inference_latency_ms" and scope != "model_inference_only":
            raise ValueError(f"{label}: inference_latency_ms must use model_inference_only scope")
        if field == "monthly_cost_inr" and scope != "cost":
            raise ValueError(f"{label}: monthly cost must use cost scope")
        if field == "availability_percent" and scope != "availability":
            raise ValueError(f"{label}: availability must use availability scope")
        components_name = "latency_components_ms" if field == "latency_ms" else "cost_components_inr" if field == "monthly_cost_inr" else None
        amount = finite_number(measured_value, label, allow_zero=(field == "monthly_cost_inr"))
        components = value.get(components_name) if components_name else None
        if components is not None:
            if not isinstance(components, dict) or not components or len(components) > 20:
                raise ValueError(f"{label}.{components_name} must be a nonempty mapping")
            for k, part in components.items():
                _text(k, f"{label} component name", 60)
                finite_number(part, f"{label}.{k}", allow_zero=True)
            if field == "latency_ms":
                required = ("preprocessing", "inference", "postprocessing") if tier == "on_device" else (
                    "preprocessing", "upload", "network_rtt", "queue", "inference", "postprocessing", "download")
                if set(components) != set(required):
                    raise ValueError(f"{label} must specify exactly {', '.join(required)}")
            elif "other" not in components:  # no requirement for cost categories; all entered amounts must be accounted for
                pass
            if abs(sum(components.values()) - amount) > 0.011:
                raise ValueError(f"{label}: total must equal sum of the itemized components")
        if source == "demo":
            return None, None
        metadata = {"source": source, "source_reference": reference, "method": method,
                    "assumptions": assumptions, "scope": scope}
        if components_name and components is not None:
            metadata[components_name] = dict(components)
    else:
        if tier_source not in VALID_SOURCES:
            raise ValueError(f"metrics[{tier}].source required for legacy numeric {field}")
        if tier_source == "demo":
            return None, None
        source = tier_source
        measured_value = value
        metadata = {"source": source, "source_reference": tier_note or "Legacy tier-level source note not provided",
                    "method": "legacy_flat_metric", "assumptions": [],
                    "scope": "end_to_end" if field == "latency_ms" else "cost" if field == "monthly_cost_inr" else
                    "model_inference_only" if field == "inference_latency_ms" else "availability"}
    amount = finite_number(measured_value, label, allow_zero=(field == "monthly_cost_inr"))
    if field == "availability_percent" and not 0 < amount <= 100:
        raise ValueError("availability_percent must be in (0, 100]")
    return amount, metadata


def normalize_metrics(metrics_by_tier):
    if metrics_by_tier is None:
        return {}
    if not isinstance(metrics_by_tier, dict):
        raise ValueError("metrics_by_tier must be a dict")
    cleaned = {}
    for tier, metrics in metrics_by_tier.items():
        if tier not in TIERS or not isinstance(metrics, dict):
            raise ValueError(f"Invalid metrics tier or record: {tier}")
        source = metrics.get("source")
        if source is not None and source not in VALID_SOURCES:
            raise ValueError(f"metrics[{tier}].source must be one of {VALID_SOURCES}")
        note = str(metrics.get("source_note", ""))[:240]
        record = {"source_note": note, "field_sources": {}, "field_evidence": {},
                  "policy_source": source if source is not None else "unknown"}
        for field in NUMERIC:
            if field in metrics and metrics[field] is not None:
                value, metadata = _evidence(metrics[field], field, tier, source, note)
                if metadata is None:
                    continue
                record[field] = value
                record["field_sources"][field] = metadata["source"]
                record["field_evidence"][field] = metadata
        # Existing field-level boolean/policy evidence retains the legacy tier-level source.
        for field in BOOL_FIELDS:
            if field in metrics and metrics[field] is not None:
                if not isinstance(metrics[field], bool):
                    raise ValueError(f"metrics[{tier}].{field} must be boolean")
                if source not in VALID_SOURCES:
                    raise ValueError(f"metrics[{tier}].source required for {field}")
                record[field] = metrics[field]
        if metrics.get("deployment_region") is not None:
            region = metrics["deployment_region"]
            if not isinstance(region, str) or not region.strip() or len(region) > 80:
                raise ValueError(f"metrics[{tier}].deployment_region must be a nonempty region")
            if source not in VALID_SOURCES:
                raise ValueError(f"metrics[{tier}].source required for deployment_region")
            record["deployment_region"] = region.strip()
        field_sources = set(record["field_sources"].values())
        if source is not None and any(k in record for k in BOOL_FIELDS + ("deployment_region",)):
            field_sources.add(source)
        record["source"] = field_sources.pop() if len(field_sources) == 1 else "mixed" if field_sources else source or "unknown"
        # Do not include non-evidence demo / empty records.
        if any(k in record for k in NUMERIC + BOOL_FIELDS + ("deployment_region",)) and record["source"] != "demo":
            cleaned[tier] = record
    return cleaned
