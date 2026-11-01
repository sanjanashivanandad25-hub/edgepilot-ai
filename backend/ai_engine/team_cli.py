"""Stage 8 no-server smoke/demo CLI for handoff interface.

Examples:
 python3 -m ai_engine.team_cli --operation recommend --input examples/request_s25_match.json
 python3 -m ai_engine.team_cli --operation simulate --input examples/request_stage5_s25_hardware.json --changes examples/stage5_changes_memory_drop.json
"""
import argparse
import json
from pathlib import Path

from .team_handoff import TeamEngine


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def normalize_changes(value):
    """Accept Stage 5 change files: plain mapping or {'changes': mapping}."""
    if isinstance(value, dict) and set(value) == {"changes"}:
        return value["changes"]
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", choices=["recommend", "explain", "simulate", "optimize", "counterfactuals"], required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--benchmark-dir", default="benchmarks")
    parser.add_argument("--metrics")
    parser.add_argument("--scenario-metrics")
    parser.add_argument("--cost-curves")
    parser.add_argument("--changes")
    parser.add_argument("--question", choices=["why_recommended", "why_not_tier", "evidence_limitations", "what_would_change"], default="why_recommended")
    parser.add_argument("--alternative-tier", choices=["on_device", "far_edge", "regional_edge", "cloud"])
    parser.add_argument("--fields", nargs="*")
    parser.add_argument("--target-tier", choices=["on_device", "far_edge", "regional_edge", "cloud"])
    parser.add_argument("--qualcomm", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    engine = TeamEngine(benchmark_dir=args.benchmark_dir)
    payload, metrics = _json(args.input), _json(args.metrics)
    curves = _json(args.cost_curves)
    if args.qualcomm and args.operation not in ("recommend", "explain"):
        parser.error("--qualcomm applies only to recommend/explain; simulations are deterministic")
    llm = engine.qualcomm_from_environment() if args.qualcomm else None
    if args.operation == "recommend":
        result = engine.recommend(payload, metrics_by_tier=metrics, cost_curves=curves, llm=llm)
    elif args.operation == "explain":
        result = engine.explain(payload, question=args.question, alternative_tier=args.alternative_tier,
                                metrics_by_tier=metrics, cost_curves=curves, llm=llm)
    elif args.operation == "simulate":
        if not args.changes:
            parser.error("--changes required for simulate")
        result = engine.simulate(payload, changes=normalize_changes(_json(args.changes)), metrics_by_tier=metrics,
                                 scenario_metrics_by_tier=_json(args.scenario_metrics))
    elif args.operation == "optimize":
        result = engine.optimize(payload, metrics_by_tier=metrics, cost_curves=curves)
    else:
        result = engine.counterfactuals(payload, fields=args.fields, target_tier=args.target_tier,
                                        metrics_by_tier=metrics)
    encoded = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
        print("Saved:", args.output)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
