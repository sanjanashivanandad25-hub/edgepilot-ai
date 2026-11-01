"""Safety checks for Phase 3 benchmark provenance and engine integration."""
import json
import tempfile
import unittest
from pathlib import Path

from ai_engine.recommender import recommend
from scripts.record_profile import build_records, write_records


class Phase3BenchmarksTests(unittest.TestCase):
    def test_qualcomm_published_results_are_evidence_not_end_to_end(self):
        evidence, metrics = build_records(
            "mobilenet_v2", "Example Qualcomm device", "tflite", "float", 8.5,
            "qualcomm_published", "https://example.org/result", "2026-10-24"
        )
        self.assertEqual(evidence["inference_latency_ms"], 8.5)
        self.assertNotIn("latency_ms", metrics["on_device"])
        self.assertNotIn("monthly_cost_inr", metrics["on_device"])
        with tempfile.TemporaryDirectory() as tmp:
            _, metrics_file = write_records(evidence, metrics, tmp)
            payload = {"workload": {
                "latency_requirement_ms": 50, "bandwidth_requirement": "medium",
                "budget_monthly": 1000, "privacy_requirement": "high", "criticality": "high"
            }}
            with open(metrics_file, encoding="utf-8") as f:
                output = recommend(payload, metrics_by_tier=json.load(f))
            self.assertIsNone(output["estimates"]["latency_ms"])
            self.assertEqual(output["details"]["metric_sources"], {"on_device": "measured"})

    def test_invalid_or_fake_inference_latency_rejected(self):
        for val in [0, -1, float("nan"), float("inf"), "foo"]:
            with self.assertRaises(ValueError):
                build_records("mobilenet_v2", "device", "tflite", "float", val,
                              "qualcomm_published", "report", "2026-10-24")


if __name__ == "__main__":
    unittest.main()
