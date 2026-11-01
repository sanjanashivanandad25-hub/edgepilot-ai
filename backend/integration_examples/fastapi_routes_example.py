"""OPTIONAL EXAMPLE FOR PERSON 3. NOT A RUNNING BACKEND BY ITSELF.

Copy/adapt into Person 3's FastAPI application. Requires pip install fastapi.
Do not mount this file until benchmark path and service auth are configured.
Provider/cost estimates are intentionally not fabricated here.
"""
import os
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from ai_engine.reliability import ReliabilityError
from ai_engine.team_handoff import TeamEngine

router = APIRouter(prefix="/api")


@lru_cache(maxsize=1)
def engine():
    return TeamEngine(benchmark_dir=os.getenv("EDGEPILOT_BENCHMARK_DIR", "benchmarks"))


def workload_only(body):
    if not isinstance(body, dict) or "workload" not in body:
        raise ValueError("Expected 'workload' object")
    return {"workload": body["workload"]}


def metrics_for_workload(payload):
    # PERSON 3: Replace with workload-specific calculations and provenance.
    # NEVER pass the Stage 3 synthetic demo file as production evidence.
    return None


def cost_curves_for_workload(payload):
    # PERSON 3: Replace with provider/hardware pricing assumptions for this workload.
    return None


def llm_if_configured():
    # Person 3 owns secure environment configuration and timeouts.
    env = ("QUALCOMM_API_KEY", "QUALCOMM_BASE_URL", "QUALCOMM_MODEL")
    return engine().qualcomm_from_environment(timeout=20) if all(os.getenv(k) for k in env) else None


def invoke(function):
    try:
        return function()
    except ReliabilityError:
        raise HTTPException(status_code=500, detail="Decision validation failed") from None
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    # Configure generic exception reporting via server logging, never return secrets.


@router.get("/health")
def health():
    return {"status": "ok", "service": "edge-vs-cloud-backend", "message": "Backend is running"}


@router.post("/recommend")
def recommend(body: dict):
    def work():
        payload = workload_only(body)
        return engine().recommend(payload, metrics_by_tier=metrics_for_workload(payload),
                                  cost_curves=cost_curves_for_workload(payload),
                                  llm=llm_if_configured())
    return invoke(work)


@router.post("/explain")
def explain(body: dict):
    def work():
        payload = workload_only(body)
        return engine().explain(payload, question=body.get("question", "why_recommended"),
                                alternative_tier=body.get("alternative_tier"),
                                metrics_by_tier=metrics_for_workload(payload),
                                cost_curves=cost_curves_for_workload(payload),
                                llm=llm_if_configured())
    return invoke(work)


@router.post("/simulate")
def simulate(body: dict):
    def work():
        payload = workload_only(body)
        changes = body.get("changes")
        # Refresh scenario estimates in the backend when relevant; None causes
        # the engine to withhold stale metrics after workload changes.
        return engine().simulate(payload, changes=changes,
                                 metrics_by_tier=metrics_for_workload(payload),
                                 scenario_metrics_by_tier=None)
    return invoke(work)


@router.post("/optimize")
def optimize(body: dict):
    def work():
        payload = workload_only(body)
        return engine().optimize(payload, metrics_by_tier=metrics_for_workload(payload),
                                 cost_curves=cost_curves_for_workload(payload))
    return invoke(work)


@router.post("/counterfactuals")
def counterfactuals(body: dict):
    def work():
        payload = workload_only(body)
        return engine().counterfactuals(payload, fields=body.get("fields"),
                                        target_tier=body.get("target_tier"),
                                        metrics_by_tier=metrics_for_workload(payload))
    return invoke(work)

# PERSON 3: add request authentication, CORS allowlist, rate limits, payload limits,
# centralized logging, deployment health checks and production exception handling.
# App wiring (in Person 3's backend): app.include_router(router)
