"""Command-line wrapper for Stage 5 one-shot what-if and sampled sensitivity."""
import argparse
import json
from pathlib import Path
from .benchmark_registry import read_catalog
from .counterfactuals import discover_flips, CANDIDATE_FIELDS
from .scenarios import simulate_scenario
from .config import TIERS


def main():
    parser = argparse.ArgumentParser(description="EdgePilot Stage 5 what-if and counterfactual engine")
    parser.add_argument("--input", required=True, help="Workload request JSON")
    parser.add_argument("--changes", required=True, help="JSON object of workload changes")
    parser.add_argument("--benchmark-dir", default="benchmarks")
    parser.add_argument("--metrics", default=None, help="Baseline per-tier evidence JSON")
    parser.add_argument("--scenario-metrics", default=None, help="Fresh per-tier evidence for new scenario (optional)")
    parser.add_argument("--find-flips", action="store_true", help="Run bounded one-factor-at-a-time sensitivity search")
    parser.add_argument("--target-tier", choices=TIERS, default=None)
    parser.add_argument("--max-evaluations", type=int, default=70)
    parser.add_argument("--max-results", type=int, default=8)
    parser.add_argument("--fields", nargs="+", choices=CANDIDATE_FIELDS, default=None)
    parser.add_argument("--qualcomm", action="store_true", help="ONE LLM answer on final scenario (not during flip search)")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    change_data = json.loads(Path(args.changes).read_text(encoding="utf-8"))
    # Support either plain {field: value} or {"changes":{field: value}}.
    changes = change_data.get("changes", change_data)
    catalog = read_catalog(args.benchmark_dir)
    baseline_metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8")) if args.metrics else None
    scenario_metrics = json.loads(Path(args.scenario_metrics).read_text(encoding="utf-8")) if args.scenario_metrics else None
    llm = None
    if args.qualcomm:
        from .qualcomm_grounded import QualcommGroundedReasoner
        llm = QualcommGroundedReasoner(timeout=30)
    report = simulate_scenario(payload, changes=changes, benchmark_catalog=catalog,
                               metrics_by_tier=baseline_metrics,
                               scenario_metrics_by_tier=scenario_metrics, llm=llm)
    if args.find_flips:
        report["counterfactuals"] = discover_flips(
            payload, benchmark_catalog=catalog, metrics_by_tier=baseline_metrics,
            target_tier=args.target_tier, fields=args.fields,
            max_evaluations=args.max_evaluations, max_results=args.max_results,
        )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
