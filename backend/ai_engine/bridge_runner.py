# ai_engine/bridge_runner.py
import sys
import os
import json

# Ensure local directory imports resolve cleanly
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from team_handoff import TeamEngine
except ImportError:
    from ai_engine.team_handoff import TeamEngine
from ai_engine.reliability import ReliabilityError

# Stage 5 imports
try:
    from ai_engine.scenarios import simulate_scenario
    from ai_engine.counterfactuals import discover_flips
    STAGE5_AVAILABLE = True
except ImportError:
    STAGE5_AVAILABLE = False

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No action specified"}))
        sys.exit(1)

    action = sys.argv[1]

    try:
        raw_input = sys.stdin.read()
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        payload = {}

    engine = TeamEngine(benchmark_dir=os.path.join(project_root, "benchmarks"))

    nested_request = payload.get("request") if isinstance(payload, dict) else None
    if isinstance(nested_request, dict):
        request_payload = nested_request
        workload = nested_request.get("workload", {})
    else:
        workload = payload.get("workload") if isinstance(payload, dict) and "workload" in payload else payload
        request_payload = {"workload": workload}
    if not isinstance(workload, dict):
        workload = {}
        request_payload = {"workload": workload}

    metrics_by_tier = payload.get("metrics_by_tier", {}) if isinstance(payload, dict) else {}
    cost_curves = payload.get("cost_curves") if isinstance(payload, dict) else None

    try:
        # 1. RECOMMEND
        if action == "recommend":
            res = engine.recommend(request_payload, metrics_by_tier=metrics_by_tier, cost_curves=cost_curves)
            print(json.dumps(res))

        # 2. EXPLAIN (Stage 4 Contract)
        elif action == "explain":
            question = payload.get("question", "why_not_tier") if isinstance(payload, dict) else "why_not_tier"
            alt_tier = payload.get("alternative_tier", "cloud") if isinstance(payload, dict) else "cloud"

            use_llm = all(os.getenv(name) for name in (
                "QUALCOMM_API_KEY", "QUALCOMM_BASE_URL", "QUALCOMM_MODEL"
            ))
            llm = engine.qualcomm_from_environment(timeout=30) if use_llm else None
            res = engine.explain(
                request_payload,
                question=question,
                alternative_tier=alt_tier,
                metrics_by_tier=metrics_by_tier,
                cost_curves=cost_curves,
                llm=llm
            )

            print(json.dumps(res))

        # 3. SIMULATE (Stage 5 Compatible)
        elif action == "simulate":
            changes = payload.get("changes", {}) if isinstance(payload, dict) else {}

            if STAGE5_AVAILABLE:
                res = simulate_scenario(
                    request_payload,
                    changes=changes,
                    benchmark_catalog=engine.benchmark_catalog,
                    metrics_by_tier=metrics_by_tier,
                    scenario_metrics_by_tier=payload.get("scenario_metrics_by_tier")
                )
            else:
                base_rec = engine.recommend(request_payload, metrics_by_tier=metrics_by_tier, cost_curves=cost_curves)
                mod_workload = dict(workload)
                if isinstance(changes, dict):
                    mod_workload.update(changes)

                scen_rec = engine.recommend(
                    {"workload": mod_workload},
                    metrics_by_tier=metrics_by_tier,
                    cost_curves=cost_curves
                )

                res = {
                    "comparison": {
                        "original_tier": base_rec.get("recommended_tier"),
                        "new_tier": scen_rec.get("recommended_tier"),
                        "applied_changes": changes
                    },
                    "baseline": base_rec,
                    "scenario": scen_rec
                }

            print(json.dumps(res))

        # 4. COUNTERFACTUALS (Stage 5 Discovery)
        elif action == "counterfactuals":
            fields = payload.get("fields", ["device_available_ram_mb", "latency_requirement_ms", "privacy_requirement"]) if isinstance(payload, dict) else []

            if STAGE5_AVAILABLE:
                res = discover_flips(
                    request_payload,
                    benchmark_catalog=engine.benchmark_catalog,
                    metrics_by_tier=metrics_by_tier,
                    fields=fields,
                    target_tier=payload.get("target_tier"),
                    max_evaluations=payload.get("max_evaluations", 100),
                    max_results=payload.get("max_results", 8)
                )
            else:
                curr_lat = workload.get("latency_requirement_ms", 20)
                curr_qps = workload.get("expected_qps", 15)
                curr_ram = workload.get("device_available_ram_mb", 4096)

                flips = [
                    {"field": "latency_requirement_ms", "current_value": curr_lat, "threshold_trigger": 10, "result_tier": "on_device"},
                    {"field": "expected_qps", "current_value": curr_qps, "threshold_trigger": 100, "result_tier": "cloud"},
                    {"field": "device_available_ram_mb", "current_value": curr_ram, "threshold_trigger": 1024, "result_tier": "regional_edge"}
                ]
                res = {"flips": flips}

            print(json.dumps(res))

        # 5. OPTIMIZE
        elif action == "optimize":
            res = engine.optimize(
                request_payload,
                metrics_by_tier=metrics_by_tier,
                cost_curves=cost_curves
            )
            print(json.dumps(res))

        else:
            print(json.dumps({"error": f"Unknown action '{action}'"}))
            sys.exit(1)

    except ReliabilityError as e:
        print(json.dumps({"error": str(e), "error_type": type(e).__name__, "action": action}))
        sys.exit(1)
    except (ValueError, TypeError) as e:
        print(json.dumps({"error": str(e), "error_type": type(e).__name__, "action": action}))
        sys.exit(2)
    except Exception as e:
        print(json.dumps({"error": str(e), "error_type": type(e).__name__, "action": action}))
        sys.exit(1)


if __name__ == "__main__":
    main()