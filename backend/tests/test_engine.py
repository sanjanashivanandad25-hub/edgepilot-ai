import copy
import json
import unittest
from pathlib import Path
from io import BytesIO
from unittest.mock import patch

from ai_engine.recommender import recommend
from ai_engine.explain import QualcommExplainer
from ai_engine.sensitivity import compare_scenarios

SAMPLE = {"workload": {"latency_requirement_ms": 50, "bandwidth_requirement": "medium",
                       "budget_monthly": 1000, "privacy_requirement": "high", "criticality": "high"}}
TIERS = {"on_device", "far_edge", "regional_edge", "cloud"}


class TestEdgepilot(unittest.TestCase):
    def test_exact_team_request_works(self):
        result = recommend(SAMPLE)
        self.assertIsNone(result["recommended_tier"])
        self.assertEqual(set(result["scores"]), TIERS)
        self.assertTrue(all(0 <= v <= 100 for v in result["scores"].values()))
        self.assertTrue(all(key in result for key in ("recommended_tier", "scores", "estimates", "explanation", "tradeoffs", "warnings", "assumptions", "architecture")))

    def test_no_fabricated_metrics(self):
        response = recommend(SAMPLE)
        self.assertIsNone(response["estimates"]["latency_ms"])
        self.assertIsNone(response["estimates"]["monthly_cost"])
        self.assertEqual(response["estimates"]["currency"], "INR")

    def test_synthetic_metric_ignored(self):
        metrics = json.loads(Path("examples/synthetic_metrics_demo.json").read_text())
        self.assertEqual(recommend(SAMPLE, metrics_by_tier=metrics)["scores"], recommend(SAMPLE)["scores"])

    def test_model_memory_blocks_local(self):
        modified = copy.deepcopy(SAMPLE)
        modified["workload"].update({"model_ram_required_mb": 4000, "device_available_ram_mb": 1000})
        result = recommend(modified)
        self.assertNotEqual(result["recommended_tier"], "on_device")
        self.assertEqual(result["scores"]["on_device"], 0)
        self.assertFalse(result["details"]["feasibility"]["on_device"]["eligible"])

    def test_offline_forces_local(self):
        modified = copy.deepcopy(SAMPLE)
        modified["workload"]["require_offline"] = True
        result = recommend(modified, metrics_by_tier={
            "on_device": {"source": "estimated", "latency_ms": 15, "monthly_cost_inr": 900}
        })
        self.assertEqual(result["recommended_tier"], "on_device")
        for tier in TIERS - {"on_device"}:
            self.assertEqual(result["scores"][tier], 0)

    def test_no_feasible_option(self):
        modified = copy.deepcopy(SAMPLE)
        modified["workload"].update({"require_offline": True, "model_ram_required_mb": 3000,
                                     "device_available_ram_mb": 500})
        result = recommend(modified)
        self.assertIsNone(result["recommended_tier"])
        self.assertEqual(result["details"]["status"], "no_feasible_tier")
        self.assertEqual(result["architecture"], {"nodes": [], "connections": []})

    def test_large_workload_scales(self):
        modified = copy.deepcopy(SAMPLE)
        modified["workload"].update({"latency_requirement_ms": 400, "privacy_requirement": "low",
                                     "criticality": "low", "bandwidth_requirement": "low", "concurrent_users": 50000})
        metrics = {
            "on_device": {"source": "estimated", "latency_ms": 15, "monthly_cost_inr": 900},
            "far_edge": {"source": "estimated", "latency_ms": 30, "monthly_cost_inr": 500},
            "regional_edge": {"source": "estimated", "latency_ms": 55, "monthly_cost_inr": 1100},
            "cloud": {"source": "estimated", "latency_ms": 120, "monthly_cost_inr": 300},
        }
        self.assertEqual(recommend(modified, metrics_by_tier=metrics)["recommended_tier"], "cloud")

    def test_infeasible_measured_latency(self):
        m = {"on_device": {"source": "measured", "latency_ms": 90, "source_note": "E2E load test"}}
        result = recommend(SAMPLE, metrics_by_tier=m)
        self.assertFalse(result["details"]["feasibility"]["on_device"]["eligible"])

    def test_estimated_latency_penalizes_not_blocks(self):
        m = {"on_device": {"source": "estimated", "latency_ms": 90}}
        result = recommend(SAMPLE, metrics_by_tier=m)
        self.assertTrue(result["details"]["feasibility"]["on_device"]["eligible"])
        self.assertLess(result["scores"]["on_device"], recommend(SAMPLE)["scores"]["on_device"])

    def test_quoted_over_budget_is_blocked(self):
        m = {"on_device": {"source": "quoted", "monthly_cost_inr": 1200}}
        self.assertFalse(recommend(SAMPLE, metrics_by_tier=m)["details"]["feasibility"]["on_device"]["eligible"])

    def test_estimates_provenance_shown(self):
        m = {"on_device": {"source": "estimated", "monthly_cost_inr": 650,
                           "latency_ms": 28, "source_note": "model-based estimate"}}
        r = recommend(SAMPLE, metrics_by_tier=m)
        self.assertEqual(r["estimates"], {"latency_ms": 28, "monthly_cost": 650, "currency": "INR"})
        self.assertIn("estimated", r["details"]["metric_sources"]["on_device"])

    def test_offline_network_available_switch(self):
        new = copy.deepcopy(SAMPLE)
        new["workload"]["network_available"] = False
        r = recommend(new)
        self.assertTrue(all(r["scores"][t] == 0 for t in ("far_edge", "regional_edge", "cloud")))

    def test_bandwidth_threshold(self):
        new = copy.deepcopy(SAMPLE)
        new["workload"].update({"bandwidth_available_mbps": 2, "minimum_network_bandwidth_mbps": 15})
        self.assertFalse(recommend(new)["details"]["feasibility"]["cloud"]["eligible"])

    def test_architecture_graph_has_valid_ids(self):
        for name in TIERS:
            new = copy.deepcopy(SAMPLE)
            new["workload"]["allowed_tiers"] = [name]
            result = recommend(new)
            ids = {n["id"] for n in result["architecture"]["nodes"]}
            for edge in result["architecture"]["connections"]:
                self.assertIn(edge["source"], ids)
                self.assertIn(edge["target"], ids)

    def test_input_validation(self):
        for value in (-1, float('nan'), "quick", True):
            new = copy.deepcopy(SAMPLE)
            new["workload"]["latency_requirement_ms"] = value
            with self.assertRaises(ValueError):
                recommend(new)
        with self.assertRaises(ValueError):
            recommend({})
        with self.assertRaises(ValueError):
            recommend({"workload": {**SAMPLE["workload"], "privacy_requirement": "extreme"}})
        with self.assertRaises(ValueError):
            recommend(SAMPLE, metrics_by_tier={"moon": {"source": "measured"}})

    def test_score_breakdown_weighted(self):
        result = recommend(SAMPLE)
        parts = result["details"]["score_breakdown"]["on_device"].values()
        reconstructed = round(sum(p["value"] * p["weight"] for p in parts) / sum(p["weight"] for p in parts), 1)
        self.assertAlmostEqual(reconstructed, result["scores"]["on_device"])

    def test_llm_success_with_stub(self):
        class LLM:
            def explain(self, **kwargs):
                return "On-device is selected by deterministic scoring, not an inference benchmark."
        self.assertIn("deterministic", recommend(SAMPLE, llm=LLM())["explanation"])

    def test_llm_failure_falls_back_safely(self):
        class BrokenLLM:
            def explain(self, **kwargs):
                raise ConnectionError("offline")
        result = recommend(SAMPLE, llm=BrokenLLM())
        self.assertTrue(result["explanation"])
        self.assertTrue(any("unavailable" in warning for warning in result["warnings"]))

    def test_qualcomm_client_wire_format(self):
        def mock_open(request, timeout):
            self.assertIn("/chat/completions", request.full_url)
            self.assertEqual(request.headers["Authorization"], "Bearer test-key")
            body = json.loads(request.data)
            self.assertEqual(body["model"], "example-supported-model")
            self.assertIn("recommended_tier", body["messages"][1]["content"])
            return BytesIO(json.dumps({"choices":[{"message":{"content":"On-device is a heuristic recommendation based on constraints."}}]}).encode())
        llm = QualcommExplainer(api_key="test-key", base_url="https://example.test/v1",
                               model="example-supported-model", opener=mock_open)
        result = recommend(SAMPLE, llm=llm)
        self.assertIn("On-device", result["explanation"])

    def test_counterfactual_analysis(self):
        result = compare_scenarios(SAMPLE, {"model_ram_required_mb": 10000,
                                            "device_available_ram_mb": 1000}, metrics_by_tier={
            "on_device": {"source": "estimated", "latency_ms": 15, "monthly_cost_inr": 900},
            "far_edge": {"source": "estimated", "latency_ms": 30, "monthly_cost_inr": 500},
        })
        self.assertEqual(result["original_recommendation"], "on_device")
        self.assertNotEqual(result["new_recommendation"], "on_device")
        self.assertTrue(result["changed"])


if __name__ == "__main__":
    unittest.main()
