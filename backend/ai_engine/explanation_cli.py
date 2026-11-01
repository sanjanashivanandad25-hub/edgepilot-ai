"""Stage 4 explanation CLI (all arguments may be used with or without Qualcomm)."""
import argparse
import json
from pathlib import Path
from .benchmark_registry import read_catalog
from .grounded_explanations import explain_recommendation, QUESTIONS
from .config import TIERS


def main():
    p = argparse.ArgumentParser(description="Stage 4 grounded Qualcomm explanations")
    p.add_argument("--input", required=True)
    p.add_argument("--benchmark-dir", default="benchmarks")
    p.add_argument("--metrics", help="Per-tier cost/E2E metrics JSON file")
    p.add_argument("--question", choices=QUESTIONS, default="why_recommended")
    p.add_argument("--alternative-tier", choices=TIERS)
    p.add_argument("--qualcomm", action="store_true")
    args = p.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    catalog = read_catalog(args.benchmark_dir)
    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8")) if args.metrics else None
    llm = None
    if args.qualcomm:
        from .qualcomm_grounded import QualcommGroundedReasoner
        llm = QualcommGroundedReasoner(timeout=30)
    result = explain_recommendation(payload, benchmark_catalog=catalog,
                                    metrics_by_tier=metrics, llm=llm,
                                    question=args.question, alternative_tier=args.alternative_tier)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
