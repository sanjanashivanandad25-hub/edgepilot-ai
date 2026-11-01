"""Run locally: python3 -m ai_engine.cli --input examples/request_v1.json"""
import argparse
import json
from pathlib import Path
from .recommender import recommend


def main():
    parser = argparse.ArgumentParser(description="EdgePilot AI deterministic recommendation engine")
    parser.add_argument("--input", default="examples/request_v1.json", help="JSON request path")
    parser.add_argument("--metrics", default=None, help="Optional tier metrics JSON path")
    parser.add_argument("--qualcomm", action="store_true", help="Enable optional LLM explanation (requires configured environment variables)")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8")) if args.metrics else None
    llm = None
    if args.qualcomm:
        from .explain import QualcommExplainer
        llm = QualcommExplainer()
    print(json.dumps(recommend(payload, metrics_by_tier=metrics, llm=llm), indent=2))


if __name__ == "__main__":
    main()
