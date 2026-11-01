"""Stage 5 regression tests (work without network or Qualcomm key)."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from ai_engine.benchmark_registry import read_catalog
from ai_engine.scenarios import simulate_scenario
from ai_engine.counterfactuals import discover_flips

ROOT = Path(__file__).resolve().parents[1]


class FakeQualcomm:
    calls = 0
    def answer(self, *, facts, question, alternative_tier=None):
        self.calls += 1
        winner = facts.get("winner")
        return (winner or "no feasible tier").replace("_", " ") + " is provisionally recommended."


class Stage5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = json.loads((ROOT / 'examples/request_s25_match.json').read_text())
        cls.catalog = read_catalog(ROOT / 'benchmarks')
        cls.metrics = json.loads((ROOT / 'examples/stage3_illustrative_metrics.json').read_text())

    def run_scenario(self, changes, request=None, metrics=None, **kwargs):
        return simulate_scenario(request or self.request, changes=changes,
                                 benchmark_catalog=self.catalog,
                                 metrics_by_tier=self.metrics if metrics is None else metrics,
                                 **kwargs)

    def test_scenario_preserves_original_workload(self):
        before = deepcopy(self.request)
        self.run_scenario({'privacy_requirement': 'low'})
        self.assertEqual(before, self.request)

    def test_scenario_preserves_input_metrics(self):
        before = deepcopy(self.metrics)
        self.run_scenario({'network_available': False})
        self.assertEqual(before, self.metrics)

    def test_s25_benchmark_kept_when_privacy_changes(self):
        r = self.run_scenario({'privacy_requirement': 'low'})
        self.assertEqual(r['scenario']['details']['benchmark']['status'], 'matched')
        self.assertEqual(r['scenario']['details']['benchmark']['inference_latency_ms'], .45)

    def test_changed_model_has_no_match(self):
        r = self.run_scenario({'model_name': 'unseen_model'})
        self.assertEqual(r['scenario']['details']['benchmark']['status'], 'no_match')
        self.assertNotIn('on_device', r['scenario']['details']['metric_sources'])

    def test_privacy_reuses_estimates(self):
        r = self.run_scenario({'privacy_requirement': 'low'})
        self.assertEqual(r['comparison']['metrics_handling']['mode'], 'baseline_metrics_reused')
        self.assertEqual(r['scenario']['details']['tier_estimates']['on_device']['monthly_cost_inr'], 400)

    def test_latency_deadline_change_reuses_estimates(self):
        r = self.run_scenario({'latency_requirement_ms': 20})
        self.assertEqual(r['scenario']['details']['tier_estimates']['cloud']['latency_ms'], 112)
        self.assertEqual(r['scenario']['details']['tier_estimates']['cloud']['latency_target_met'], False)

    def test_budget_change_reuses_cost_estimates(self):
        r = self.run_scenario({'budget_monthly': 450})
        self.assertEqual(r['scenario']['details']['tier_estimates']['on_device']['monthly_cost_inr'], 400)
        self.assertEqual(r['scenario']['details']['tier_estimates']['far_edge']['budget_met'], False)

    def test_network_change_invalidates_estimates(self):
        r = self.run_scenario({'bandwidth_available_mbps': 1})
        self.assertEqual(r['comparison']['metrics_handling']['mode'], 'baseline_metrics_invalidated')
        self.assertIsNone(r['scenario']['details']['tier_estimates']['cloud']['latency_ms'])
        self.assertIsNone(r['scenario']['details']['tier_estimates']['cloud']['monthly_cost_inr'])

    def test_concurrent_user_change_invalidates_estimates(self):
        r = self.run_scenario({'concurrent_users': 50000})
        self.assertEqual(r['comparison']['metrics_handling']['mode'], 'baseline_metrics_invalidated')
        self.assertEqual(r['scenario']['details']['benchmark']['status'], 'matched')

    def test_model_change_invalidates_old_inference(self):
        r = self.run_scenario({'precision': 'w8a8'})
        self.assertEqual(r['scenario']['details']['benchmark']['status'], 'no_match')
        self.assertIsNone(r['scenario']['estimates']['latency_ms'])

    def test_ram_shortage_forces_real_flip(self):
        r = self.run_scenario({'model_ram_required_mb': 4096, 'device_available_ram_mb': 1024})
        self.assertTrue(r['comparison']['recommendation_changed'])
        self.assertEqual(r['comparison']['original_tier'], 'on_device')
        self.assertNotEqual(r['comparison']['new_tier'], 'on_device')
        self.assertFalse(r['scenario']['details']['feasibility']['on_device']['eligible'])
        self.assertTrue(r['comparison']['feasibility_changes']['on_device']['was_eligible'])
        self.assertFalse(r['comparison']['feasibility_changes']['on_device']['now_eligible'])

    def test_network_offline_blocks_remote(self):
        r = self.run_scenario({'network_available': False})
        for tier in ('far_edge', 'regional_edge', 'cloud'):
            self.assertFalse(r['scenario']['details']['feasibility'][tier]['eligible'])

    def test_no_feasible_tier_when_offline_and_ram_lacking(self):
        r = self.run_scenario({'require_offline': True, 'model_ram_required_mb': 4096,
                               'device_available_ram_mb': 512})
        self.assertIsNone(r['comparison']['new_tier'])
        self.assertEqual(r['scenario']['details']['status'], 'no_feasible_tier')

    def test_no_qualcomm_call_unless_explicit(self):
        r = self.run_scenario({'criticality': 'low'})
        self.assertEqual(r['scenario']['details']['explanation_source'], 'deterministic')

    def test_one_llm_answer_only_for_final(self):
        llm = FakeQualcomm()
        r = self.run_scenario({'privacy_requirement': 'low'}, llm=llm)
        self.assertEqual(llm.calls, 1)
        self.assertEqual(r['scenario']['details']['explanation_source'], 'qualcomm_llm')
        self.assertEqual(r['baseline']['details']['explanation_source'], 'deterministic')

    def test_scenario_specific_metrics_override(self):
        new_metric = {
            'cloud': {'latency_ms': {
                'value': 20, 'source': 'estimated', 'source_reference': 'example-model',
                'method': 'fresh_scenario_estimator', 'scope': 'end_to_end',
                'assumptions': ['hypothetical network scenario']}}
        }
        r = self.run_scenario({'bandwidth_available_mbps': 1}, scenario_metrics_by_tier=new_metric)
        self.assertEqual(r['comparison']['metrics_handling']['mode'], 'fresh_scenario_supplied')
        self.assertEqual(r['scenario']['details']['tier_estimates']['cloud']['latency_ms'], 20)
        self.assertIsNone(r['scenario']['details']['tier_estimates']['cloud']['monthly_cost_inr'])

    def test_scenario_metric_with_false_source_rejected(self):
        with self.assertRaises(ValueError):
            self.run_scenario({'privacy_requirement': 'low'}, scenario_metrics_by_tier={
                'cloud': {'source': 'fiction', 'latency_ms': 5}})

    def test_error_unsupported_input(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported scenario'):
            self.run_scenario({'mystery_key': 1})

    def test_error_no_changes(self):
        with self.assertRaises(ValueError):
            self.run_scenario({'privacy_requirement': 'high'})

    def test_error_invalid_range(self):
        with self.assertRaises(ValueError):
            self.run_scenario({'latency_requirement_ms': -2})

    def test_error_invalid_enum(self):
        with self.assertRaises(ValueError):
            self.run_scenario({'privacy_requirement': 'maximum'})

    def test_score_deltas_recompute_not_fabricated(self):
        r = self.run_scenario({'privacy_requirement': 'low'})
        for tier, record in r['comparison']['score_deltas'].items():
            self.assertEqual(record['delta'], round(r['scenario']['scores'][tier] - r['baseline']['scores'][tier], 1))

    def test_diff_identifies_inputs(self):
        r = self.run_scenario({'require_offline': True, 'privacy_requirement': 'medium'})
        self.assertEqual([item['field'] for item in r['comparison']['changed_inputs']], ['privacy_requirement', 'require_offline'])

    def test_discover_flips_finds_real_memory_change(self):
        p = deepcopy(self.request)
        p['workload']['model_ram_required_mb'] = 4096
        p['workload']['device_available_ram_mb'] = 8192
        result = discover_flips(p, benchmark_catalog=self.catalog, metrics_by_tier=self.metrics,
                                fields=['device_available_ram_mb'])
        self.assertGreater(result['candidate_flips_found'], 0)
        self.assertEqual(result['flips'][0]['field'], 'device_available_ram_mb')
        self.assertNotEqual(result['flips'][0]['to_tier'], result['baseline_tier'])

    def test_flip_search_is_reproducible(self):
        p = deepcopy(self.request)
        p['workload']['model_ram_required_mb'] = 4096
        p['workload']['device_available_ram_mb'] = 8192
        kw = dict(benchmark_catalog=self.catalog, metrics_by_tier=self.metrics,
                  fields=['device_available_ram_mb','privacy_requirement'])
        self.assertEqual(discover_flips(p, **kw), discover_flips(p, **kw))

    def test_flip_search_does_not_mutate(self):
        p = deepcopy(self.request)
        prev = deepcopy(p)
        discover_flips(p, benchmark_catalog=self.catalog, metrics_by_tier=self.metrics)
        self.assertEqual(p, prev)

    def test_flip_search_target_filter(self):
        p = deepcopy(self.request)
        p['workload']['model_ram_required_mb'] = 4096
        p['workload']['device_available_ram_mb'] = 8192
        result = discover_flips(p, benchmark_catalog=self.catalog, metrics_by_tier=self.metrics,
                                fields=['device_available_ram_mb'], target_tier='cloud')
        self.assertTrue(all(r['to_tier'] == 'cloud' for r in result['flips']))

    def test_flip_search_reject_bad_target(self):
        with self.assertRaises(ValueError):
            discover_flips(self.request, benchmark_catalog=self.catalog, target_tier='mars')

    def test_flip_search_reject_bad_dimension(self):
        with self.assertRaises(ValueError):
            discover_flips(self.request, benchmark_catalog=self.catalog, fields=['api_key'])

    def test_flip_search_bounded(self):
        result = discover_flips(self.request, benchmark_catalog=self.catalog,
                                max_evaluations=3, max_results=1)
        self.assertLessEqual(result['evaluations'], 3)
        self.assertTrue(result['truncated'])

    def test_invalid_sampling_limits(self):
        for bad in (0, 201, True, 2.5):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    discover_flips(self.request, benchmark_catalog=self.catalog, max_evaluations=bad)

    def test_workload_input_backward_compatible(self):
        basic = json.loads((ROOT / 'examples/request_v1.json').read_text())
        r = simulate_scenario(basic, changes={'privacy_requirement': 'medium'},
                              benchmark_catalog=self.catalog)
        self.assertIn('recommended_tier', r['scenario'])
        self.assertIn('architecture', r['scenario'])
        self.assertIn('scores', r['scenario'])


if __name__ == '__main__':
    unittest.main()
