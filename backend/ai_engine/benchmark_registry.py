"""Match on-device Qualcomm inference evidence to an EXACT workload configuration.

A match never proves E2E latency, hardware compatibility, or tier superiority.
Catalog files must be independently reviewed before trusting their provenance.
"""
from datetime import date
from math import isfinite
from pathlib import Path
import json

KEYS = ("model_name", "target_device", "runtime", "precision")
SOURCE_TYPES = ("qualcomm_workbench", "qualcomm_published")


def _norm(value):
    return " ".join(value.strip().casefold().split())


def read_catalog(directory):
    path = Path(directory)
    if not path.is_dir():
        raise ValueError(f"Benchmark directory not found: {path}")
    records = []
    for filename in sorted(path.glob("*_evidence.json")):
        try:
            data = json.loads(filename.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read evidence file {filename.name}: {exc}") from exc
        required = ("model", "device", "runtime", "precision", "inference_latency_ms",
                    "source_type", "source_reference", "measurement_scope")
        if not isinstance(data, dict) or any(k not in data for k in required):
            raise ValueError(f"Incomplete benchmark evidence: {filename.name}")
        for k in ("model", "device", "runtime", "precision", "source_reference"):
            if not isinstance(data[k], str) or not data[k].strip():
                raise ValueError(f"Invalid {k} in {filename.name}")
        if data["source_type"] not in SOURCE_TYPES:
            raise ValueError(f"Unknown source_type in {filename.name}")
        if data["measurement_scope"] != "on_device_model_inference_only_not_end_to_end":
            raise ValueError(f"Unsupported measurement scope in {filename.name}")
        value = data["inference_latency_ms"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value <= 0:
            raise ValueError(f"Invalid inference_latency_ms in {filename.name}")
        data["inference_latency_ms"] = float(value)
        date_text = data.get("retrieved_or_measured_on", "")
        try:
            date.fromisoformat(date_text)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid date in {filename.name}; expected YYYY-MM-DD") from None
        # Markdown links are not raw URLs and must not enter the API contract.
        if data["source_reference"].startswith("["):
            raise ValueError(f"Use a plain URL/reference, not Markdown, in {filename.name}")
        data["evidence_file"] = filename.name
        records.append(data)
    return records


def match_benchmark(workload, catalog):
    if not isinstance(catalog, list):
        raise ValueError("catalog must be a list loaded by read_catalog")
    supplied = [k for k in KEYS if k in workload and workload[k] is not None]
    for k in supplied:
        if not isinstance(workload[k], str) or not workload[k].strip() or len(workload[k]) > 128:
            raise ValueError(f"{k} must be a nonempty string of at most 128 characters")
    if not supplied:
        return {"status": "not_requested", "reason": "No model/hardware selection provided."}
    missing = [k for k in KEYS if k not in supplied]
    if missing:
        return {"status": "incomplete_selection", "reason": "Missing fields: " + ", ".join(missing)}
    candidates = [r for r in catalog if all(
        _norm(workload[k]) == _norm(r[{"model_name":"model", "target_device":"device", "runtime":"runtime", "precision":"precision"}[k]])
        for k in KEYS
    )]
    if not candidates:
        return {"status": "no_match", "reason": "No exact model/device/runtime/precision benchmark was found."}
    candidates.sort(key=lambda r: (r.get("retrieved_or_measured_on", ""),
                                   r["source_type"] == "qualcomm_workbench"), reverse=True)
    selected = candidates[0]
    return {
        "status": "matched",
        "model": selected["model"], "device": selected["device"],
        "runtime": selected["runtime"], "precision": selected["precision"],
        "inference_latency_ms": selected["inference_latency_ms"],
        "source_type": selected["source_type"], "source_reference": selected["source_reference"],
        "retrieved_or_measured_on": selected["retrieved_or_measured_on"],
        "measurement_scope": selected["measurement_scope"],
        "evidence_file": selected["evidence_file"],
        "note": "Model inference only, not end-to-end latency or proof of deployment feasibility.",
    }
