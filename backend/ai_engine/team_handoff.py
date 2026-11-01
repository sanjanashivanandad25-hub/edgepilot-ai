"""Stable, dependency-free Person 2 entrypoint for EdgePilot API integration.

The backend owns HTTP, authentication, rate limits, provider secrets, network/cost
estimation and monitoring. All scoring remains in the deterministic engine.
No method deploys workloads or contacts external services unless an explicit LLM
object is supplied by the caller.
"""
from copy import deepcopy
from pathlib import Path

from .benchmark_registry import read_catalog
from .counterfactuals import discover_flips
from .qualcomm_grounded import QualcommGroundedReasoner
from .reliability import audit_recommendation, guarded_recommendation, ReliabilityError, validate_external_request
from .scenarios import simulate_scenario
from .optimization import analyze_optimization

CONTRACT_VERSION = "1.0"


class TeamEngine:
    """Reusable synchronous engine. Initialize once per backend worker.

    `metrics_by_tier` and `cost_curves` MUST be supplied by Person 3 for the
    particular workload; there is deliberately no global demo default.
    """

    def __init__(self, *, benchmark_dir="benchmarks", benchmark_catalog=None):
        if benchmark_catalog is None:
            self.benchmark_catalog = read_catalog(Path(benchmark_dir))
        elif isinstance(benchmark_catalog, list):
            self.benchmark_catalog = deepcopy(benchmark_catalog)
        else:
            raise ValueError("benchmark_catalog must be a list or None")

    @staticmethod
    def qualcomm_from_environment(*, timeout=20):
        """Explicit opt-in. Requires 3 QUALCOMM_* environment variables."""
        return QualcommGroundedReasoner(timeout=timeout)

    def recommend(self, payload, *, metrics_by_tier=None, cost_curves=None, llm=None):
        """Return original /api/recommend keys + explanatory/audit details."""
        return guarded_recommendation(
            deepcopy(payload), benchmark_catalog=self.benchmark_catalog,
            metrics_by_tier=metrics_by_tier, cost_curves=cost_curves, llm=llm,
        )

    def explain(self, payload, *, question="why_recommended", alternative_tier=None,
                metrics_by_tier=None, cost_curves=None, llm=None):
        """Return full recommendation with details.explainability selected question."""
        return guarded_recommendation(
            deepcopy(payload), benchmark_catalog=self.benchmark_catalog,
            metrics_by_tier=metrics_by_tier, cost_curves=cost_curves, llm=llm,
            question=question, alternative_tier=alternative_tier,
        )

    def optimize(self, payload, *, metrics_by_tier=None, cost_curves=None):
        """Return the audited recommendation plus Pareto, hybrid, and cost analyses."""
        result = self.recommend(payload, metrics_by_tier=metrics_by_tier,
                                cost_curves=cost_curves, llm=None)
        result["details"]["optimization"] = analyze_optimization(
            payload, result, cost_curves=cost_curves
        )
        audit = audit_recommendation(payload, result)
        if audit["errors"]:
            raise ReliabilityError("EdgePilot optimization failed internal audit: " + "; ".join(audit["errors"]))
        result["details"]["reliability"] = audit
        return result

    def simulate(self, payload, *, changes, metrics_by_tier=None,
                 scenario_metrics_by_tier=None):
        """Return baseline, scenario, before/after comparison and independent audits.

        Do not automatically reuse baseline metrics after model/network/load change.
        Do not send an LLM request for every slider movement.
        """
        validate_external_request(payload)
        if not isinstance(changes, dict):
            raise ValueError("changes must be an object")
        changed = deepcopy(payload)
        changed["workload"].update(deepcopy(changes))
        validate_external_request(changed)
        result = simulate_scenario(
            deepcopy(payload), changes=deepcopy(changes),
            benchmark_catalog=self.benchmark_catalog,
            metrics_by_tier=metrics_by_tier,
            scenario_metrics_by_tier=scenario_metrics_by_tier,
        )
        before_audit = audit_recommendation(payload, result["baseline"])
        after_audit = audit_recommendation(changed, result["scenario"])
        if before_audit["errors"] or after_audit["errors"]:
            raise ReliabilityError("Scenario failed internal validation")
        result["quality"] = {"baseline": before_audit, "scenario": after_audit}
        return result

    def counterfactuals(self, payload, *, fields=None, target_tier=None,
                        metrics_by_tier=None, max_evaluations=100, max_results=8):
        """Return sampled one-variable flips, never exact guaranteed thresholds."""
        validate_external_request(payload)
        return discover_flips(
            deepcopy(payload), benchmark_catalog=self.benchmark_catalog,
            metrics_by_tier=metrics_by_tier, fields=fields,
            target_tier=target_tier, max_evaluations=max_evaluations,
            max_results=max_results,
        )
