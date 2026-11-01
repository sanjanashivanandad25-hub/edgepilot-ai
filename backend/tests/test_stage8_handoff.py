"""Contract tests: preserve original JSON, safe handoff, simulations, no silent HTTP."""
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from ai_engine.team_handoff import TeamEngine
from ai_engine.team_cli import normalize_changes
from scripts.stage8_export_handoff import allowed_file, prepare_zip
from scripts.stage8_smoke_test import run as run_smoke

ROOT = Path(__file__).resolve().parent.parent


def load(filename):
    return json.loads((ROOT / "examples" / filename).read_text())


class Stage8Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = TeamEngine(benchmark_dir=ROOT / "benchmarks")
        cls.request = load("request_s25_match.json")
        cls.hardware = load("request_stage5_s25_hardware.json")

    def test_01_recommend_required_keys(self):
        r = self.engine.recommend(self.request)
        for key in ("recommended_tier", "scores", "estimates", "explanation", "tradeoffs", "warnings", "assumptions", "architecture", "details"):
            self.assertIn(key, r)

    def test_02_audit_passes(self):
        r = self.engine.recommend(self.request)
        self.assertIn(r["details"]["reliability"]["status"], {"pass", "pass_with_caveats"})

    def test_03_result_is_serializable(self):
        json.dumps(self.engine.recommend(self.request), allow_nan=False)

    def test_04_benchmark_matched(self):
        r = self.engine.recommend(self.request)
        self.assertEqual(r["details"]["benchmark"]["status"], "matched")
        self.assertEqual(r["details"]["benchmark"]["inference_latency_ms"], 0.45)

    def test_05_benchmark_doesnt_fill_e2e(self):
        self.assertIsNone(self.engine.recommend(self.request)["estimates"]["latency_ms"])

    def test_06_unknown_model_no_match(self):
        request = load("request_unmatched_benchmark.json")
        r = self.engine.recommend(request)
        self.assertIn(r["details"]["benchmark"]["status"], {"no_match", "incomplete_selection"})

    def test_07_why_not_cloud(self):
        r = self.engine.explain(self.request, question="why_not_tier", alternative_tier="cloud")
        self.assertEqual(r["details"]["explainability"]["question"], "why_not_tier")
        self.assertIn("cloud", r["details"]["explainability"]["comparisons"])

    def test_08_invalid_question(self):
        with self.assertRaises(ValueError):
            self.engine.explain(self.request, question="ignore_instructions")

    def test_09_invalid_unknown_workload_field(self):
        bad = load("request_v1.json")
        bad["workload"]["privcy_requirement"] = "high"
        with self.assertRaises(ValueError):
            self.engine.recommend(bad)

    def test_10_zero_budget_supported(self):
        req = load("request_v1.json")
        req["workload"]["budget_monthly"] = 0
        self.assertIsInstance(self.engine.recommend(req), dict)

    def test_11_memory_flip(self):
        r = self.engine.simulate(self.hardware, changes={"device_available_ram_mb": 128})
        self.assertEqual((r["comparison"]["original_tier"], r["comparison"]["new_tier"]), ("on_device", "far_edge"))

    def test_12_simulation_has_audits(self):
        r = self.engine.simulate(self.hardware, changes={"device_available_ram_mb": 128})
        self.assertIn("quality", r)
        self.assertEqual(set(r["quality"]), {"baseline", "scenario"})

    def test_13_simulation_rejects_unknown(self):
        with self.assertRaises(ValueError):
            self.engine.simulate(self.hardware, changes={"admin": "true"})

    def test_14_counterfactual_is_bounded(self):
        r = self.engine.counterfactuals(self.hardware, fields=["device_available_ram_mb"], max_evaluations=12)
        self.assertLessEqual(r["evaluations"], 12)
        self.assertGreater(len(r["flips"]), 0)

    def test_15_optimize_has_three_outputs(self):
        r = self.engine.optimize(load("stage6_hybrid_request_DEMO.json"), metrics_by_tier=load("stage6_pareto_tradeoff_metrics_DEMO.json"), cost_curves=load("stage6_cost_curves_DEMO.json"))
        self.assertEqual(set(r["details"]["optimization"]), {"method", "pareto", "hybrid", "cost_break_even"})

    def test_16_static_output_does_not_return_key(self):
        output = json.dumps(self.engine.recommend(self.request))
        self.assertNotIn("QUALCOMM_API_KEY", output)
        self.assertNotIn("Authorization", output)

    def test_17_doesnt_initialize_llm_implicitly(self):
        self.assertEqual(self.engine.recommend(self.request)["details"]["explainability"]["answer_source"], "deterministic")

    def test_18_smoke_suite_passes(self):
        report = run_smoke()
        self.assertEqual(report["total"], report["passed"])
        self.assertGreaterEqual(report["total"], 10)

    def test_19_file_allowlist_blocks_env_and_raw_profile(self):
        self.assertFalse(allowed_file(Path(".env")))
        self.assertFalse(allowed_file(Path("profile_jid_profile.json")))
        self.assertFalse(allowed_file(Path("client.ini")))

    def test_20_clean_export_omits_secrets(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "handoff.zip"
            prepare_zip(path, include_evidence=False, root=ROOT)
            with ZipFile(path) as archive:
                names = archive.namelist()
                self.assertIn("ai_engine/team_handoff.py", names)
                self.assertIn("HANDOFF_MANIFEST.json", names)
                self.assertFalse(any(n.endswith(".env") or "client.ini" in n for n in names))
                self.assertFalse(any(n.startswith("benchmarks/") for n in names))

    def test_21_export_sanitizes_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "handoff.zip"
            prepare_zip(path, include_evidence=True, root=ROOT)
            with ZipFile(path) as archive:
                names = archive.namelist()
                self.assertIn("benchmarks/mobilenet_v2_s25_workbench_evidence.json", names)
                evidence = json.loads(archive.read("benchmarks/mobilenet_v2_s25_workbench_evidence.json"))
                self.assertEqual(evidence["measurement_scope"], "on_device_model_inference_only_not_end_to_end")
                self.assertNotIn("notes", evidence)

    def test_22_invalid_catalog_rejected(self):
        with self.assertRaises(ValueError):
            TeamEngine(benchmark_catalog={"not": "a list"})

    def test_23_available_without_benchmark(self):
        engine = TeamEngine(benchmark_catalog=[])
        r = engine.recommend(self.request)
        self.assertEqual(r["details"]["benchmark"]["status"], "no_match")

    def test_24_cost_unknown_not_zero(self):
        r = self.engine.recommend(self.request)
        self.assertIsNone(r["estimates"]["monthly_cost"])

    def test_25_wrapped_stage5_changes_file_accepted(self):
        value = load("stage5_changes_memory_drop.json")
        self.assertEqual(normalize_changes(value), {"device_available_ram_mb": 128})

    def test_26_bad_scenario_metrics_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.simulate(self.hardware, changes={"device_available_ram_mb": 128}, scenario_metrics_by_tier="not an object")


if __name__ == "__main__":
    unittest.main()
