"""Capture a real Qualcomm AI Hub model inference benchmark for a specific workload.

Keeps complete provenance for reviewers and produces tier_metrics.json in the
exact shape supported by recommend(metrics_by_tier=...). No invented numbers,
no cloud RTT estimates, no inferred model compatibility.

Run: python3 scripts/record_profile.py
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

DEFAULT_OUTPUT_DIR = Path("benchmarks")


def positive_float(text):
    try:
        value = float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError("Latency must be a number (in milliseconds)") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Latency must be positive and finite")
    return value


def build_records(model, device, runtime, precision, latency_ms, source_type, source_ref, observed_at):
    fields = [model, device, runtime, precision, source_type, source_ref, observed_at]
    if not all(isinstance(value, str) and value.strip() for value in fields):
        raise ValueError("All benchmark provenance fields are required")
    if source_type not in ("qualcomm_published", "qualcomm_workbench"):
        raise ValueError("Source type must be qualcomm_published or qualcomm_workbench")
    date.fromisoformat(observed_at)
    latency = positive_float(latency_ms)
    evidence = {
        "model": model.strip(),
        "device": device.strip(),
        "runtime": runtime.strip(),
        "precision": precision.strip(),
        "inference_latency_ms": latency,
        "source_type": source_type,
        "source_reference": source_ref.strip(),
        "retrieved_or_measured_on": observed_at,
        "measurement_scope": "on_device_model_inference_only_not_end_to_end",
        "notes": "This measurement applies only to the identified model/device/runtime/precision."
    }
    source_note = f"Qualcomm AI Hub | {model} | {device} | {runtime} | {source_type} | {source_ref}"
    metric = {
        "on_device": {
            "source": "measured",  # source data are measured by Qualcomm, not simulated
            "source_note": source_note[:240],
            "inference_latency_ms": latency,
        }
    }
    return evidence, metric


def write_records(evidence, metrics, out_dir=DEFAULT_OUTPUT_DIR):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    evidence_path = out / "mobilenet_v2_evidence.json"
    metrics_path = out / "tier_metrics.json"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return evidence_path, metrics_path


def ask(label, default=None):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        answer = input(f"{label}{suffix}: ").strip()
        if answer:
            return answer
        if default is not None:
            return default
        print("A value is required. Use the exact information from Qualcomm's results.")


def main():
    print("Record a real Qualcomm MobileNetV2 device inference measurement.")
    print("DO NOT enter a guessed latency, and DO NOT use end-to-end latency here.\n")
    model = ask("Model ID", "mobilenet_v2")
    device = ask("Exact Qualcomm-powered device name")
    runtime = ask("Exact runtime (e.g. tflite)")
    precision = ask("Model precision (e.g. float, w8a8, as reported)")
    while True:
        value = ask("Reported model inference latency in milliseconds")
        try:
            latency = positive_float(value)
            break
        except ValueError as exc:
            print(exc)
    source_type = ask("Source type: qualcomm_published or qualcomm_workbench", "qualcomm_published")
    source_ref = ask("Performance result URL / Workbench job URL or job ID")
    observed_at = ask("Date you retrieved or measured result (YYYY-MM-DD)", date.today().isoformat())
    try:
        evidence, metrics = build_records(model, device, runtime, precision, latency, source_type, source_ref, observed_at)
        paths = write_records(evidence, metrics)
    except ValueError as exc:
        raise SystemExit(f"Invalid data: {exc}") from exc
    print("\nRecorded in:")
    for path in paths:
        print(" -", path)
    print("\nNEXT: python3 -m ai_engine.cli --input examples/request_v1.json --metrics benchmarks/tier_metrics.json")
    print("Note: model inference time alone does not change tier ranking or total latency estimates.")


if __name__ == "__main__":
    main()
