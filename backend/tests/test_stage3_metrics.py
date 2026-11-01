"""Stage 3 evidence-scoring tests; no network and no Qualcomm API tokens."""
import copy
import json
from pathlib import Path
import unittest

from ai_engine.metrics import normalize_metrics
from ai_engine.recommender import recommend
from ai_engine.benchmarked import recommend_with_benchmarks
from ai_engine.benchmark_registry import read_catalog

BASE = {"workload": {"latency_requirement_ms": 50, "bandwidth_requirement": "medium",
                     "budget_monthly": 1000, "privacy_requirement": "high", "criticality": "high"}}


def ev(value, source="estimated", field="latency_ms", **extra):
    return {"value": value, "source": source, "source_reference": "TEST ONLY",
            "method": "unit_test", "assumptions": ["synthetic test input"],
            "scope": "end_to_end" if field == "latency_ms" else "cost", **extra}


class Stage3EvidenceTests(unittest.TestCase):
    def test_existing_request_still_works(self):
        r = recommend(BASE)
        self.assertEqual(r["details"]["method"], "transparent_weighted_heuristic_v3")
        self.assertIsNone(r["recommended_tier"])

    def test_nested_latency_estimate_appears(self):
        r = recommend(BASE, metrics_by_tier={"on_device": {"latency_ms": ev(20)}})
        self.assertIsNone(r["estimates"]["latency_ms"])
        self.assertEqual(r["details"]["tier_estimates"]["on_device"]["latency_ms"], 20)
        self.assertEqual(r["details"]["tier_estimates"]["on_device"]["latency_source"], "estimated")
        self.assertFalse(r["details"]["tier_estimates"]["on_device"]["latency_target_verified"])

    def test_nested_quoted_cost_appears_and_is_independent(self):
        m = {"regional_edge": {"latency_ms": ev(35, "measured"), "monthly_cost_inr": ev(800, "quoted", "monthly_cost_inr")}}
        r = recommend(BASE, metrics_by_tier=m)
        self.assertEqual(r["details"]["metric_sources"]["regional_edge"], "mixed")
        self.assertEqual(r["details"]["score_breakdown"]["regional_edge"]["latency"]["origin"], "measured_end_to_end_latency")
        self.assertEqual(r["details"]["score_breakdown"]["regional_edge"]["affordability"]["origin"], "quoted_monthly_cost")
        self.assertTrue(r["details"]["tier_estimates"]["regional_edge"]["budget_verified"])

    def test_quoted_cost_over_budget_blocks_with_mixed_source(self):
        m = {"regional_edge": {"latency_ms": ev(30), "monthly_cost_inr": ev(1100, "quoted", "monthly_cost_inr")}}
        r = recommend(BASE, metrics_by_tier=m)
        self.assertFalse(r["details"]["feasibility"]["regional_edge"]["eligible"])

    def test_measured_cost_over_budget_hard_blocks_and_is_verified(self):
        m = {"cloud": {"monthly_cost_inr": ev(1200, "measured", "monthly_cost_inr")}}
        r = recommend(BASE, metrics_by_tier=m)
        self.assertFalse(r["details"]["feasibility"]["cloud"]["eligible"])
        self.assertTrue(r["details"]["tier_estimates"]["cloud"]["budget_verified"])

    def test_estimated_cost_over_budget_does_not_hard_block(self):
        r = recommend(BASE, metrics_by_tier={"regional_edge": {"monthly_cost_inr": ev(1100, field="monthly_cost_inr")}})
        self.assertTrue(r["details"]["feasibility"]["regional_edge"]["eligible"])
        self.assertFalse(r["details"]["tier_estimates"]["regional_edge"]["budget_met"])

    def test_measured_e2e_latency_over_target_blocks_even_with_estimated_cost(self):
        m = {"regional_edge": {"latency_ms": ev(60, "measured"), "monthly_cost_inr": ev(300, field="monthly_cost_inr")}}
        self.assertFalse(recommend(BASE, metrics_by_tier=m)["details"]["feasibility"]["regional_edge"]["eligible"])

    def test_estimated_e2e_over_target_does_not_hard_block(self):
        r = recommend(BASE, metrics_by_tier={"regional_edge": {"latency_ms": ev(60)}})
        self.assertTrue(r["details"]["feasibility"]["regional_edge"]["eligible"])
        self.assertFalse(r["details"]["tier_estimates"]["regional_edge"]["latency_target_met"])
        self.assertFalse(r["details"]["tier_estimates"]["regional_edge"]["latency_target_verified"])

    def test_inference_only_is_never_e2e(self):
        r = recommend(BASE, metrics_by_tier={"on_device": {"inference_latency_ms": {
            "value": .45, "source": "measured", "source_reference": "Workbench job",
            "method": "device_profile", "scope": "model_inference_only"}}})
        self.assertIsNone(r["estimates"]["latency_ms"])
        self.assertEqual(r["details"]["score_breakdown"]["on_device"]["latency"]["origin"], "heuristic_profile")

    def test_inference_scope_cannot_be_labeled_as_e2e(self):
        with self.assertRaises(ValueError):
            recommend(BASE, metrics_by_tier={"on_device": {"latency_ms": ev(.45, scope="model_inference_only")}})

    def test_estimates_require_assumptions(self):
        x = ev(30)
        x.pop("assumptions")
        with self.assertRaises(ValueError):
            recommend(BASE, metrics_by_tier={"on_device": {"latency_ms": x}})

    def test_measured_requires_reference(self):
        with self.assertRaises(ValueError):
            recommend(BASE, metrics_by_tier={"on_device": {"latency_ms": ev(30, "measured", source_reference="")}})

    def test_cost_components_sum(self):
        x = ev(300, field="monthly_cost_inr", cost_components_inr={"compute": 100, "operations": 200})
        self.assertEqual(normalize_metrics({"cloud": {"monthly_cost_inr": x}})["cloud"]["monthly_cost_inr"], 300)

    def test_cost_components_wrong_sum_rejected(self):
        x = ev(300, field="monthly_cost_inr", cost_components_inr={"compute": 100, "operations": 100})
        with self.assertRaises(ValueError):
            normalize_metrics({"cloud": {"monthly_cost_inr": x}})

    def test_local_latency_components_sum(self):
        x = ev(10.45, latency_components_ms={"preprocessing": 5, "inference": .45, "postprocessing": 5})
        self.assertAlmostEqual(normalize_metrics({"on_device": {"latency_ms": x}})["on_device"]["latency_ms"], 10.45)

    def test_remote_latency_components_must_include_network(self):
        x = ev(10.45, latency_components_ms={"preprocessing": 5, "inference": .45, "postprocessing": 5})
        with self.assertRaises(ValueError):
            normalize_metrics({"cloud": {"latency_ms": x}})

    def test_all_missing_values_are_null(self):
        r = recommend(BASE)
        for tier in ("on_device", "far_edge", "regional_edge", "cloud"):
            self.assertIsNone(r["details"]["tier_estimates"][tier]["latency_ms"])
            self.assertIsNone(r["details"]["tier_estimates"][tier]["monthly_cost_inr"])

    def test_zero_budget_does_not_divide_by_zero(self):
        req = copy.deepcopy(BASE)
        req["workload"]["budget_monthly"] = 0
        r = recommend(req, metrics_by_tier={"on_device": {"monthly_cost_inr": ev(0, field="monthly_cost_inr")}})
        self.assertIsNone(r["details"]["tier_estimates"]["on_device"]["cost_to_budget_percent"])
        self.assertTrue(r["details"]["tier_estimates"]["on_device"]["budget_met"])

    def test_synthetic_illustration_labels_every_value_as_estimated(self):
        m = json.loads(Path("examples/stage3_illustrative_metrics.json").read_text())
        r = recommend(BASE, metrics_by_tier=m)
        for tier, item in r["details"]["tier_estimates"].items():
            self.assertEqual(item["latency_source"], "estimated")
            self.assertEqual(item["cost_source"], "estimated")
            self.assertIsNotNone(item["latency_ms"])
            self.assertIsNotNone(item["monthly_cost_inr"])
            self.assertFalse(item["budget_verified"])

    def test_preserves_exact_benchmark_matching_with_metrics(self):
        catalog = read_catalog("benchmarks")
        r = recommend_with_benchmarks(json.loads(Path("examples/request_s25_match.json").read_text()),
                                      benchmark_catalog=catalog,
                                      metrics_by_tier=json.loads(Path("examples/stage3_illustrative_metrics.json").read_text()))
        self.assertEqual(r["details"]["benchmark"]["status"], "matched")
        self.assertEqual(r["details"]["benchmark"]["inference_latency_ms"], .45)
        self.assertFalse(r["details"]["benchmark_used_to_score_tier"])
        self.assertEqual(r["details"]["tier_estimates"]["on_device"]["latency_source"], "estimated")

    def test_legacy_data_input_unaffected(self):
        r = recommend(BASE, metrics_by_tier={"on_device": {"source": "estimated", "latency_ms": 28, "monthly_cost_inr": 650}})
        self.assertEqual(r["estimates"], {"latency_ms": 28, "monthly_cost": 650, "currency": "INR"})
        self.assertEqual(r["details"]["metric_sources"]["on_device"], "estimated")

    def test_bool_declarations_no_numeric_confusion(self):
        m = {"on_device": {"source": "measured", "model_compatible": False, "monthly_cost_inr": ev(100, field="monthly_cost_inr")}}
        r = recommend(BASE, metrics_by_tier=m)
        self.assertFalse(r["details"]["feasibility"]["on_device"]["eligible"])

    def test_demo_source_ignored(self):
        r = recommend(BASE, metrics_by_tier={"cloud": {"monthly_cost_inr": ev(500, "demo", "monthly_cost_inr")}})
        self.assertEqual(r["scores"], recommend(BASE)["scores"])

    def test_negative_or_nan_component_rejected(self):
        for v in (-1, float("nan"), True):
            with self.subTest(v=v), self.assertRaises(ValueError):
                normalize_metrics({"on_device": {"monthly_cost_inr": ev(10, field="monthly_cost_inr", cost_components_inr={"compute": v})}})

    def test_same_source_with_different_references_kept_per_field(self):
        m = {"cloud": {"latency_ms": ev(40, source_reference="latency report"),
                       "monthly_cost_inr": ev(200, field="monthly_cost_inr", source_reference="cost report")}}
        r = recommend(BASE, metrics_by_tier=m)
        prov = r["details"]["metric_provenance"]["cloud"]
        self.assertEqual(prov["latency_ms"]["source_reference"], "latency report")
        self.assertEqual(prov["monthly_cost_inr"]["source_reference"], "cost report")

    def test_all_four_tiers_in_comparison_even_when_unpriced(self):
        r = recommend(BASE, metrics_by_tier={"on_device": {"monthly_cost_inr": ev(200, field="monthly_cost_inr")}})
        self.assertEqual(set(r["details"]["tier_estimates"]), {"on_device", "far_edge", "regional_edge", "cloud"})


if __name__ == "__main__":
    unittest.main()
