"""No external network or Qualcomm API key required."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ai_engine.benchmark_registry import read_catalog, match_benchmark
from ai_engine.benchmarked import recommend_with_benchmarks

SAMPLE = {"workload": {"latency_requirement_ms": 50, "bandwidth_requirement": "medium",
                       "budget_monthly": 1000, "privacy_requirement": "high", "criticality": "high"}}
EVIDENCE = {
    "model": "mobilenet_v2", "device": "Samsung Galaxy S25 (Family)", "runtime": "tflite",
    "precision": "float", "inference_latency_ms": 0.45,
    "source_type": "qualcomm_workbench", "source_reference": "https://workbench.aihub.qualcomm.com/jobs/jp8r0e0xg/",
    "retrieved_or_measured_on": "2026-10-24", "measurement_scope": "on_device_model_inference_only_not_end_to_end",
}


class TestBenchmarkMatching(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        (self.folder / "mobilenet_v2_s25_workbench_evidence.json").write_text(json.dumps(EVIDENCE))
        self.catalog = read_catalog(self.folder)

    def request(self, **extra):
        payload = copy.deepcopy(SAMPLE)
        payload["workload"].update(extra)
        return payload

    def test_exact_match(self):
        selected = match_benchmark(self.request(model_name="mobilenet_v2", target_device="Samsung Galaxy S25 (Family)", runtime="tflite", precision="float")["workload"], self.catalog)
        self.assertEqual(selected["status"], "matched")
        self.assertEqual(selected["inference_latency_ms"], 0.45)

    def test_unknown_hardware_cannot_reuse_s25(self):
        payload = self.request(model_name="mobilenet_v2", target_device="Pixel 10", runtime="tflite", precision="float")
        result = recommend_with_benchmarks(payload, benchmark_catalog=self.catalog)
        self.assertEqual(result["details"]["benchmark"]["status"], "no_match")
        self.assertNotIn("on_device", result["details"]["metric_sources"])

    def test_partial_selection_not_mistaken_for_match(self):
        selection = match_benchmark({"model_name": "mobilenet_v2"}, self.catalog)
        self.assertEqual(selection["status"], "incomplete_selection")

    def test_case_and_space_handling(self):
        selection = match_benchmark({"model_name":" MobileNet_V2 ","target_device":" samsung   GALAXY S25 (FAMILY) ","runtime":"TFLITE","precision":"FLOAT"},self.catalog)
        self.assertEqual(selection["status"], "matched")

    def test_inference_only_does_not_change_ranking_or_total_latency(self):
        payload = self.request(model_name="mobilenet_v2", target_device="Samsung Galaxy S25 (Family)", runtime="tflite", precision="float")
        baseline = recommend_with_benchmarks(SAMPLE, benchmark_catalog=self.catalog)
        enriched = recommend_with_benchmarks(payload, benchmark_catalog=self.catalog)
        self.assertEqual(baseline["scores"], enriched["scores"])
        self.assertIsNone(enriched["estimates"]["latency_ms"])
        self.assertFalse(enriched["details"]["benchmark_used_to_score_tier"])

    def test_stale_pinned_inference_metric_removed(self):
        payload = self.request(model_name="unrelated_model", target_device="Samsung Galaxy S25 (Family)", runtime="tflite", precision="float")
        old = {"on_device": {"source":"measured", "source_note":"S25", "inference_latency_ms":0.45}}
        result = recommend_with_benchmarks(payload, benchmark_catalog=self.catalog, metrics_by_tier=old)
        self.assertNotIn("on_device", result["details"]["metric_sources"])

    def test_invalid_provenance_markdown_rejected(self):
        bad = dict(EVIDENCE, source_reference="[job](https://example.com)")
        (self.folder / "bad_evidence.json").write_text(json.dumps(bad))
        with self.assertRaises(ValueError):
            read_catalog(self.folder)

    def test_malformed_evidence_rejected(self):
        bad = dict(EVIDENCE, inference_latency_ms=-3)
        (self.folder / "bad_evidence.json").write_text(json.dumps(bad))
        with self.assertRaises(ValueError):
            read_catalog(self.folder)

if __name__ == "__main__":
    unittest.main()
