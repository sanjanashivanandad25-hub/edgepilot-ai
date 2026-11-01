"""CLI with automatic catalog matching. Leaves the previous cli.py intact."""
import argparse
import json
from pathlib import Path
from .benchmark_registry import read_catalog
from .benchmarked import recommend_with_benchmarks


def main():
    parser = argparse.ArgumentParser(description="EdgePilot with benchmark-aware matching")
    parser.add_argument("--input", required=True)
    parser.add_argument("--benchmark-dir", default="benchmarks")
    parser.add_argument("--qualcomm", action="store_true")
    parser.add_argument("--metrics", default=None, help="Optional per-tier cost/E2E evidence JSON")
    args = parser.parse_args()
    request = json.loads(Path(args.input).read_text(encoding="utf-8"))
    catalog = read_catalog(args.benchmark_dir)
    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8")) if args.metrics else None
    llm = None
    if args.qualcomm:
        from .explain import QualcommExplainer
        llm = QualcommExplainer()
    result = recommend_with_benchmarks(request, benchmark_catalog=catalog, metrics_by_tier=metrics, llm=llm)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
