"""Stage 6 tests: run with python3 -m unittest discover -s tests -v"""
import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai_engine.optimization import (
    analyze_optimization, cost_break_even, hybrid_architecture,
    optimize_deployment, pareto_frontier,
)
from ai_engine.benchmark_registry import read_catalog
from ai_engine.team_handoff import TeamEngine

ROOT = Path(__file__).resolve().parent.parent


def fixture(name):
    return json.loads((ROOT / 'examples' / name).read_text())


class Stage6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.req = fixture('stage6_hybrid_request_DEMO.json')
        cls.metrics = fixture('stage6_pareto_tradeoff_metrics_DEMO.json')
        cls.curves = fixture('stage6_cost_curves_DEMO.json')
        cls.catalog = read_catalog(ROOT / 'benchmarks')

    def run_engine(self, req=None, metrics=None, curves=None):
        return optimize_deployment(req or self.req, benchmark_catalog=self.catalog,
                                   metrics_by_tier=self.metrics if metrics is None else metrics,
                                   cost_curves=self.curves if curves is None else curves)

    def test_01_response_backwards_compatible(self):
        output = self.run_engine()
        for key in ('recommended_tier','scores','estimates','explanation','architecture','tradeoffs','warnings','assumptions','details'):
            self.assertIn(key, output)
        self.assertIn('optimization', output['details'])

    def test_02_pareto_real_tradeoff(self):
        pareto = self.run_engine()['details']['optimization']['pareto']
        self.assertEqual(set(pareto['non_dominated_tiers']), {'on_device','far_edge','cloud'})
        self.assertEqual(pareto['dominated_by']['regional_edge'], ['on_device', 'far_edge'])
        self.assertEqual(pareto['status'], 'provisional_estimates')

    def test_03_pareto_no_metrics(self):
        data = self.run_engine(metrics={})
        self.assertEqual(data['details']['optimization']['pareto']['status'], 'insufficient_comparable_data')
        self.assertEqual(data['details']['optimization']['pareto']['non_dominated_tiers'], [])

    def test_04_pareto_requires_both(self):
        metrics = copy.deepcopy(self.metrics)
        metrics['cloud'].pop('monthly_cost_inr')
        pareto = self.run_engine(metrics=metrics)['details']['optimization']['pareto']
        self.assertIn('cloud', pareto['excluded_or_missing'])
        self.assertEqual(pareto['status'], 'partial_comparison')

    def test_05_pareto_hard_exclusions(self):
        req = copy.deepcopy(self.req)
        req['workload']['allowed_tiers'] = ['on_device','far_edge']
        pareto = self.run_engine(req=req)['details']['optimization']['pareto']
        self.assertNotIn('cloud', pareto['non_dominated_tiers'])
        self.assertIn('cloud', pareto['excluded_or_missing'])

    def test_06_pareto_equal_not_dominated(self):
        result = self.run_engine()
        copied = copy.deepcopy(result)
        copied['details']['tier_estimates']['cloud']['latency_ms']=30
        copied['details']['tier_estimates']['cloud']['monthly_cost_inr']=500
        pareto = pareto_frontier(copied)
        self.assertNotIn('far_edge', pareto['dominated_by']['cloud'])
        self.assertNotIn('cloud', pareto['dominated_by']['far_edge'])

    def test_07_hybrid_candidate(self):
        hybrid = self.run_engine()['details']['optimization']['hybrid']
        self.assertEqual(hybrid['status'], 'candidate_requires_validation')
        self.assertEqual(len(hybrid['nodes']), 4)
        self.assertEqual(hybrid['critical_path'], ['device', 'local_inference'])
        self.assertEqual(len(hybrid['connections']), 3)

    def test_team_engine_optimize_exposes_hybrid_architecture(self):
        engine = TeamEngine(benchmark_catalog=self.catalog)
        result = engine.optimize(self.req, metrics_by_tier=self.metrics, cost_curves=self.curves)
        hybrid = result["details"]["optimization"]["hybrid"]

        self.assertEqual(hybrid["status"], "candidate_requires_validation")
        self.assertEqual(len(hybrid["nodes"]), 4)
        self.assertEqual(len(hybrid["connections"]), 3)
        self.assertNotIn("hybrid", result["scores"])
        self.assertEqual(result["details"]["reliability"]["errors"], [])

    def test_08_hybrid_does_not_override_required_tier(self):
        output = self.run_engine()
        self.assertIn(output['recommended_tier'], ('on_device','far_edge','regional_edge','cloud',None))
        self.assertNotIn('hybrid', output['scores'])
        self.assertEqual(len(output['scores']), 4)

    def test_09_hybrid_denied_without_explicit_remote_permission(self):
        req = copy.deepcopy(self.req)
        del req['workload']['allow_remote_processing']
        self.assertEqual(self.run_engine(req=req)['details']['optimization']['hybrid']['status'], 'not_proposed')

    def test_10_hybrid_denied_offline(self):
        req = copy.deepcopy(self.req)
        req['workload']['require_offline'] = True
        self.assertEqual(self.run_engine(req=req)['details']['optimization']['hybrid']['status'], 'not_proposed')

    def test_11_hybrid_denied_network_outage(self):
        req = copy.deepcopy(self.req)
        req['workload']['network_available'] = False
        self.assertEqual(self.run_engine(req=req)['details']['optimization']['hybrid']['status'], 'not_proposed')

    def test_12_hybrid_denied_insufficient_memory(self):
        req = copy.deepcopy(self.req)
        req['workload']['device_available_ram_mb'] = 128
        self.assertEqual(self.run_engine(req=req)['details']['optimization']['hybrid']['status'], 'not_proposed')

    def test_13_hybrid_requires_known_memory(self):
        req = copy.deepcopy(self.req)
        del req['workload']['model_ram_required_mb']
        self.assertEqual(self.run_engine(req=req)['details']['optimization']['hybrid']['status'], 'not_proposed')

    def test_14_hybrid_does_not_claim_certainty(self):
        obj = self.run_engine()['details']['optimization']['hybrid']
        self.assertTrue(obj['validation_checks'])
        self.assertIn('not proof', obj['basis'])

    def test_15_break_even_result(self):
        item = self.run_engine()['details']['optimization']['cost_break_even']
        self.assertEqual(item['status'], 'modeled')
        match = [x for x in item['pairwise_break_even_points']
                 if x['tiers'] == ['on_device','far_edge']]
        self.assertEqual(len(match), 1)
        self.assertAlmostEqual(match[0]['monthly_requests'], 8571.43, places=2)

    def test_16_correct_reference_cost(self):
        out = self.run_engine()['details']['optimization']['cost_break_even']
        self.assertEqual(out['estimated_cost_at_reference_inr']['far_edge'], 360)
        self.assertEqual(out['cheapest_eligible_at_reference'], 'far_edge')

    def test_17_no_curves(self):
        out = optimize_deployment(self.req, benchmark_catalog=self.catalog, metrics_by_tier=self.metrics)
        self.assertEqual(out['details']['optimization']['cost_break_even']['status'], 'not_available')

    def test_18_reject_mismatched_workload(self):
        wrong = copy.deepcopy(self.curves)
        wrong['workload_match']['model_name'] = 'unrelated_model'
        with self.assertRaisesRegex(ValueError, 'do not match'):
            self.run_engine(curves=wrong)

    def test_19_reject_negative_rate(self):
        wrong = copy.deepcopy(self.curves)
        wrong['tiers']['cloud']['per_1000_requests_inr'] = -1
        with self.assertRaises(ValueError):
            self.run_engine(curves=wrong)

    def test_20_reject_boolean_rate(self):
        wrong = copy.deepcopy(self.curves)
        wrong['tiers']['cloud']['per_1000_requests_inr'] = True
        with self.assertRaises(ValueError):
            self.run_engine(curves=wrong)

    def test_21_reject_empty_assumptions(self):
        wrong = copy.deepcopy(self.curves)
        wrong['tiers']['cloud']['assumptions'] = []
        with self.assertRaises(ValueError):
            self.run_engine(curves=wrong)

    def test_22_no_crossing_outside_valid_range(self):
        curves = copy.deepcopy(self.curves)
        curves['tiers']['on_device']['max_monthly_requests'] = 5000
        result = self.run_engine(curves=curves)['details']['optimization']['cost_break_even']
        self.assertFalse(any(x['tiers']==['on_device','far_edge'] for x in result['pairwise_break_even_points']))

    def test_23_same_curve_has_no_isolated_crossing(self):
        curves = copy.deepcopy(self.curves)
        curves['tiers']['cloud']['fixed_monthly_inr'] = curves['tiers']['far_edge']['fixed_monthly_inr']
        curves['tiers']['cloud']['per_1000_requests_inr'] = curves['tiers']['far_edge']['per_1000_requests_inr']
        result = self.run_engine(curves=curves)['details']['optimization']['cost_break_even']
        self.assertTrue(any(x['tiers']==['far_edge','cloud'] for x in result['identical_cost_curve_pairs']))

    def test_24_core_engine_not_mutated(self):
        from ai_engine.benchmarked import recommend_with_benchmarks
        base = recommend_with_benchmarks(self.req, benchmark_catalog=self.catalog,
                                         metrics_by_tier=self.metrics)
        old = copy.deepcopy(base)
        analyze_optimization(self.req, base, cost_curves=self.curves)
        self.assertEqual(base, old)

    def test_25_benchmark_still_matched(self):
        result = self.run_engine()
        self.assertEqual(result['details']['benchmark']['status'], 'matched')
        self.assertEqual(result['details']['benchmark']['inference_latency_ms'], 0.45)
        self.assertFalse(result['details']['benchmark_used_to_score_tier'])

    def test_26_untrusted_missing_cost_no_asserted_frontier(self):
        result = self.run_engine(metrics={})
        out = result['details']['optimization']['pareto']
        self.assertFalse(out['all_eligible_tiers_compared'])

    def test_27_report_source_types(self):
        report = self.run_engine()['details']['optimization']['cost_break_even']
        self.assertIn('assumptions', report['curves_used']['on_device'])
        self.assertEqual(report['curves_used']['on_device']['source'], 'estimated')

    def test_28_hard_region_policy_produces_no_invalid_edge(self):
        req = copy.deepcopy(self.req)
        req['workload']['allow_remote_processing'] = False
        report = self.run_engine(req=req)['details']['optimization']['hybrid']
        self.assertFalse(report['connections'])

    def test_29_cost_reference_out_of_bounds(self):
        curves = copy.deepcopy(self.curves)
        curves['reference_monthly_requests'] = 60000
        out = self.run_engine(curves=curves)['details']['optimization']['cost_break_even']
        self.assertIsNone(out['cheapest_eligible_at_reference'])
        self.assertFalse(out['estimated_cost_at_reference_inr'])

    def test_30_hybrid_when_no_feasible_tiers(self):
        req = copy.deepcopy(self.req)
        req['workload']['allowed_tiers'] = ['on_device']
        out = self.run_engine(req=req)['details']['optimization']['hybrid']
        self.assertEqual(out['status'], 'not_proposed')
