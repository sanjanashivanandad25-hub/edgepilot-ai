"""Stage 2 integration and decision safety tests; no network or credentials required."""
from copy import deepcopy
import unittest
from ai_engine.recommender import recommend
from ai_engine.scoring import latency_score, affordability_score, weights

BASE = {"workload": {"latency_requirement_ms": 50, "bandwidth_requirement": "medium",
                     "budget_monthly": 1000, "privacy_requirement": "high", "criticality": "high"}}


def request(**overrides):
    payload = deepcopy(BASE)
    payload["workload"].update(overrides)
    return payload


class DecisionEngineStage2(unittest.TestCase):
    def test_backward_compatibility_of_required_response(self):
        r = recommend(BASE)
        keys = ("recommended_tier", "scores", "estimates", "explanation", "tradeoffs", "warnings", "assumptions", "architecture")
        self.assertTrue(all(k in r for k in keys))
        self.assertIsNone(r["recommended_tier"])
        self.assertEqual(r["details"]["ranking"], [])
        self.assertEqual(r["details"]["method"], "transparent_weighted_heuristic_v3")
        self.assertEqual(r["details"]["explanation_source"], "deterministic")

    def test_unknown_cost_is_neutral_and_not_presented_as_real_cost(self):
        r = recommend(BASE)
        self.assertIsNone(r["estimates"]["monthly_cost"])
        field = r["details"]["score_breakdown"]["on_device"]["affordability"]
        self.assertEqual(field["origin"], "unknown_neutral_prior")
        self.assertEqual(field["value"], 50)
        self.assertTrue(any("neutral" in s for s in r["warnings"]))

    def test_actual_cost_changes_score_without_faking_other_tiers(self):
        cheap = {"on_device": {"source": "estimated", "monthly_cost_inr": 100}}
        expensive = {"on_device": {"source": "estimated", "monthly_cost_inr": 1800}}
        a = recommend(BASE, metrics_by_tier=cheap)
        b = recommend(BASE, metrics_by_tier=expensive)
        self.assertGreater(a["scores"]["on_device"], b["scores"]["on_device"])
        self.assertEqual(a["details"]["score_breakdown"]["cloud"]["affordability"]["origin"], "unknown_neutral_prior")

    def test_measured_latency_outside_deadline_is_blocked(self):
        m = {"regional_edge": {"source": "measured", "latency_ms": 60}}
        r = recommend(BASE, metrics_by_tier=m)
        self.assertEqual(r["scores"]["regional_edge"], 0)
        self.assertFalse(r["details"]["feasibility"]["regional_edge"]["eligible"])

    def test_estimated_latency_outside_deadline_is_soft_penalty(self):
        m = {"regional_edge": {"source": "estimated", "latency_ms": 60}}
        r = recommend(BASE, metrics_by_tier=m)
        self.assertTrue(r["details"]["feasibility"]["regional_edge"]["eligible"])
        self.assertEqual(r["details"]["score_breakdown"]["regional_edge"]["latency"]["origin"], "estimated_end_to_end_latency")

    def test_memory_infeasibility(self):
        r = recommend(request(model_ram_required_mb=3072, device_available_ram_mb=2048))
        self.assertFalse(r["details"]["feasibility"]["on_device"]["eligible"])

    def test_offline_and_no_device_ram_yields_no_feasible_tier(self):
        r = recommend(request(require_offline=True, model_ram_required_mb=4096, device_available_ram_mb=1024))
        self.assertIsNone(r["recommended_tier"])

    def test_data_residency_verified_mismatch_blocks(self):
        r = recommend(request(allowed_data_regions=["IN"]), metrics_by_tier={
            "cloud": {"source": "measured", "deployment_region": "EU"}})
        self.assertFalse(r["details"]["feasibility"]["cloud"]["eligible"])

    def test_data_residency_estimate_does_not_claim_verification(self):
        r = recommend(request(allowed_data_regions=["IN"]), metrics_by_tier={
            "cloud": {"source": "estimated", "deployment_region": "EU"}})
        self.assertTrue(r["details"]["feasibility"]["cloud"]["eligible"])
        self.assertTrue(any("region" in g.lower() for g in r["details"]["evidence_gaps"]["cloud"]))

    def test_explicit_verified_residency_failure_blocks(self):
        r = recommend(BASE, metrics_by_tier={"cloud": {"source": "quoted", "data_residency_compliant": False}})
        self.assertFalse(r["details"]["feasibility"]["cloud"]["eligible"])

    def test_unverified_compliance_failure_cannot_block(self):
        r = recommend(BASE, metrics_by_tier={"cloud": {"source": "estimated", "data_residency_compliant": False}})
        self.assertTrue(r["details"]["feasibility"]["cloud"]["eligible"])

    def test_verified_model_incompatibility_blocks(self):
        r = recommend(BASE, metrics_by_tier={"on_device": {"source": "measured", "model_compatible": False}})
        self.assertFalse(r["details"]["feasibility"]["on_device"]["eligible"])

    def test_measured_availability_below_declared_minimum_blocks(self):
        r = recommend(request(minimum_availability_percent=99.9), metrics_by_tier={
            "cloud": {"source": "measured", "availability_percent": 99.0}})
        self.assertFalse(r["details"]["feasibility"]["cloud"]["eligible"])

    def test_estimated_availability_below_declared_minimum_does_not_hard_block(self):
        r = recommend(request(minimum_availability_percent=99.9), metrics_by_tier={
            "cloud": {"source": "estimated", "availability_percent": 99.0}})
        self.assertTrue(r["details"]["feasibility"]["cloud"]["eligible"])

    def test_missing_availability_reports_gap(self):
        r = recommend(request(minimum_availability_percent=99.95))
        self.assertTrue(any("availability" in g.lower() for g in r["details"]["evidence_gaps"]["cloud"]))

    def test_benchmark_inference_does_not_become_end_to_end(self):
        r = recommend(BASE, metrics_by_tier={"on_device": {"source": "measured", "inference_latency_ms": .45}})
        self.assertIsNone(r["estimates"]["latency_ms"])
        self.assertEqual(r["details"]["score_breakdown"]["on_device"]["latency"]["origin"], "heuristic_profile")

    def test_decision_driver_matches_weighted_difference(self):
        metrics = {
            "on_device": {"source": "estimated", "latency_ms": 15, "monthly_cost_inr": 900},
            "far_edge": {"source": "estimated", "latency_ms": 30, "monthly_cost_inr": 500},
        }
        r = recommend(BASE, metrics_by_tier=metrics)
        drivers = r["details"]["decision_drivers"]
        self.assertEqual(len(drivers), 6)
        self.assertGreaterEqual(drivers[0]["advantage_points"], drivers[-1]["advantage_points"])
        winner, runner_up = r["details"]["ranking"][:2]
        self.assertEqual(sum(x["advantage_points"] for x in drivers),
                         sum(round(r["details"]["score_breakdown"][winner][f]["weighted_contribution"]
                                   - r["details"]["score_breakdown"][runner_up][f]["weighted_contribution"], 2)
                             for f in r["details"]["weights"]))

    def test_valid_scoring_is_finite(self):
        self.assertTrue(0 <= latency_score(50, 50) <= 100)
        self.assertTrue(0 <= affordability_score(1000, 1000) <= 100)
        self.assertEqual(affordability_score(0, 0), 100)
        self.assertEqual(affordability_score(100, 0), 0)

    def test_bandwidth_changes_scalability_not_locality_weight(self):
        low_bandwidth = weights(request(bandwidth_requirement="low")["workload"])
        high_bandwidth = weights(request(bandwidth_requirement="high")["workload"])

        self.assertEqual(low_bandwidth["data_locality"], high_bandwidth["data_locality"])
        self.assertGreater(high_bandwidth["scalability"], low_bandwidth["scalability"])

    def test_relaxed_latency_has_low_weight(self):
        relaxed = weights(request(latency_requirement_ms=1000)["workload"])
        strict = weights(request(latency_requirement_ms=50)["workload"])

        self.assertEqual(relaxed["latency"], 1)
        self.assertGreater(strict["latency"], relaxed["latency"])

    def test_estimated_sla_miss_is_ranked_as_provisional_not_hard_blocked(self):
        metrics = {
            "on_device": {"source": "estimated", "latency_ms": 15, "monthly_cost_inr": 900},
            "far_edge": {"source": "estimated", "latency_ms": 30, "monthly_cost_inr": 500},
            "cloud": {"source": "estimated", "latency_ms": 120, "monthly_cost_inr": 300},
        }
        result = recommend(request(latency_requirement_ms=50), metrics_by_tier=metrics)
        self.assertIsNotNone(result["recommended_tier"])
        self.assertTrue(result["details"]["sla_checks"][result["recommended_tier"]]["selectable"])
        self.assertEqual(result["details"]["sla_checks"]["cloud"]["latency_status"], "provisional_fail")
        self.assertTrue(result["details"]["feasibility"]["cloud"]["eligible"])
        self.assertEqual(result["details"]["status"], "provisional")

    def test_low_privacy_relaxed_latency_reweights_scores_without_ignoring_budget(self):
        metrics = {
            "on_device": {"source": "estimated", "latency_ms": 15, "monthly_cost_inr": 900},
            "far_edge": {"source": "estimated", "latency_ms": 30, "monthly_cost_inr": 500},
            "regional_edge": {"source": "estimated", "latency_ms": 55, "monthly_cost_inr": 1100},
            "cloud": {"source": "estimated", "latency_ms": 120, "monthly_cost_inr": 300},
        }
        result = recommend(request(
            latency_requirement_ms=200,
            budget_monthly=200,
            privacy_requirement="low"
        ), metrics_by_tier=metrics)

        self.assertGreater(result["scores"]["cloud"], result["scores"]["on_device"])
        self.assertEqual(result["recommended_tier"], "cloud")
        self.assertTrue(all(not check["eligible"] for check in result["details"]["sla_checks"].values()))
        self.assertEqual(result["details"]["status"], "provisional_sla_failure")

    def test_workload_profiles_can_select_each_tier_when_supported_by_inputs(self):
        from pathlib import Path
        import json

        metrics = json.loads(Path("examples/stage6_pareto_tradeoff_metrics_DEMO.json").read_text())
        cases = [
            ("cloud", {"latency_requirement_ms": 1000, "bandwidth_requirement": "high",
                       "budget_monthly": 20000, "privacy_requirement": "low",
                       "criticality": "low"}),
            ("on_device", {"latency_requirement_ms": 50, "bandwidth_requirement": "medium",
                           "budget_monthly": 1000, "privacy_requirement": "high",
                           "criticality": "high"}),
            ("far_edge", {"latency_requirement_ms": 35, "bandwidth_requirement": "high",
                          "budget_monthly": 650, "privacy_requirement": "medium",
                          "criticality": "low"}),
            ("regional_edge", {"latency_requirement_ms": 60, "bandwidth_requirement": "high",
                               "budget_monthly": 2000, "privacy_requirement": "medium",
                               "criticality": "high", "concurrent_users": 1000}),
        ]
        for expected_tier, workload_overrides in cases:
            with self.subTest(expected_tier=expected_tier):
                result = recommend(request(**workload_overrides), metrics_by_tier=metrics)
                self.assertEqual(result["recommended_tier"], expected_tier, result["scores"])
                self.assertTrue(result["details"]["sla_checks"][expected_tier]["selectable"])

    def test_strict_estimated_latency_is_provisional_and_does_not_hard_exclude(self):
        from pathlib import Path
        import json

        metrics = json.loads(Path("examples/stage6_pareto_tradeoff_metrics_DEMO.json").read_text())
        result = recommend(request(
            latency_requirement_ms=8,
            budget_monthly=20000,
            privacy_requirement="low",
            criticality="low"
        ), metrics_by_tier=metrics)

        self.assertIsNotNone(result["recommended_tier"])
        self.assertEqual(result["details"]["status"], "provisional_sla_failure")
        self.assertTrue(all(check["latency_status"] == "provisional_fail"
                            for check in result["details"]["sla_checks"].values()))
        self.assertTrue(all(item["eligible"] for item in result["details"]["feasibility"].values()))
        self.assertTrue(any("estimated SLA overrun" in warning for warning in result["warnings"]))

    def test_reject_invalid_optional_fields(self):
        fields = [
            {"concurrent_users": 4.2}, {"minimum_availability_percent": 110},
            {"allowed_data_regions": []}, {"allowed_data_regions": ["IN", "in"]},
            {"target_device": " "}, {"require_offline": "false"},
        ]
        for overrides in fields:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                recommend(request(**overrides))

    def test_llm_source_and_failure_fallback(self):
        class FakeLLM:
            def explain(self, **kwargs):
                return "On device is provisionally recommended."
        class FailingLLM:
            def explain(self, **kwargs):
                raise TimeoutError()
        self.assertEqual(recommend(BASE, llm=FakeLLM())["details"]["explanation_source"], "qualcomm_llm")
        self.assertEqual(recommend(BASE, llm=FailingLLM())["details"]["explanation_source"], "deterministic")


if __name__ == "__main__":
    unittest.main()
