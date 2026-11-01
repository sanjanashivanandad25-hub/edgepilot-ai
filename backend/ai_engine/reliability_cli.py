"""Offline-by-default Stage 7 quality gate: python3 -m ai_engine.reliability_cli --help"""
import argparse
import json
from pathlib import Path
from .benchmark_registry import read_catalog
from .reliability import guarded_recommendation


def _read(path):
    data = Path(path).read_bytes()
    if len(data) > 512 * 1024:
        raise ValueError(f"Input file too large: {path}")
    return json.loads(data)


def main():
    p = argparse.ArgumentParser(description="Stage 7 safe decision engine + audit (no API call by default)")
    p.add_argument("--input", required=True)
    p.add_argument("--benchmark-dir", default="benchmarks")
    p.add_argument("--metrics")
    p.add_argument("--cost-curves")
    p.add_argument("--output", help="Write complete JSON to file instead of stdout")
    p.add_argument("--question", default="why_recommended")
    p.add_argument("--alternative-tier")
    p.add_argument("--qualcomm", action="store_true", help="Use hosted LLM; requires configured credentials")
    args = p.parse_args()
    llm = None
    if args.qualcomm:
        from .qualcomm_grounded import QualcommGroundedReasoner
        llm = QualcommGroundedReasoner(timeout=15)
    response = guarded_recommendation(_read(args.input), benchmark_catalog=read_catalog(args.benchmark_dir),
                                      metrics_by_tier=_read(args.metrics) if args.metrics else None,
                                      cost_curves=_read(args.cost_curves) if args.cost_curves else None,
                                      llm=llm, question=args.question, alternative_tier=args.alternative_tier)
    rendered = json.dumps(response, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        print(f"Audit: {response['details']['reliability']['status']}; saved {args.output}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
