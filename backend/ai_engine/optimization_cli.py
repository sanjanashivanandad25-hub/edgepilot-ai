"""CLI: python3 -m ai_engine.optimization_cli --input ... --metrics ... --cost-curves ..."""
import argparse
import json
from pathlib import Path
from .benchmark_registry import read_catalog
from .optimization import optimize_deployment


def main():
    parser = argparse.ArgumentParser(description="Stage 6 EdgePilot multi-objective analysis")
    parser.add_argument("--input", required=True)
    parser.add_argument("--benchmark-dir", default="benchmarks")
    parser.add_argument("--metrics", default=None, help="Stage 3 per-tier E2E latency/cost evidence")
    parser.add_argument("--cost-curves", default=None, help="Person 3 cost curves for break-even analysis")
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    result = optimize_deployment(load(args.input), benchmark_catalog=read_catalog(args.benchmark_dir),
                                 metrics_by_tier=load(args.metrics) if args.metrics else None,
                                 cost_curves=load(args.cost_curves) if args.cost_curves else None)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
