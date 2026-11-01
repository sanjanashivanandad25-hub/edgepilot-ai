// routes/apiRoutes.js
const {
  getMetricsForWorkload
} = require("../services/stage3MetricService");

const express = require('express');
const router = express.Router();
const { callTeamEngine } = require('../services/pythonEngineBridge');
const { calculateSuitability, normalizeWorkload, costCurvesMatchWorkload } = require('../services/suitabilityService');
const { generatePdfReport } = require('../services/reportService');

function handleRouteError(res, error, operation) {
  const statusCode = error.statusCode || 500;
  if (statusCode >= 500) {
    console.error(`${operation} failed`, error);
  }
  return res.status(statusCode).json({
    error: `${operation} failed`,
    ...(statusCode < 500 ? { details: error.message } : {})
  });
}

// Helper to standardise payload with metrics
function getRequestPayload(req) {
  if (req.body.request) {
    return req.body.request;
  }
  const workload = normalizeWorkload(req.body.workload || req.body);
  return { workload };
}

function getPayloadWithMetrics(req) {
  const requestPayload = getRequestPayload(req);
  const workload = normalizeWorkload(requestPayload.workload);
  const normalizedRequestPayload = { ...requestPayload, workload };

  const evidence = getMetricsForWorkload(workload);

  return {
    requestPayload: normalizedRequestPayload,
    workload,
    stage3Metrics: evidence.metrics_by_tier,
    evidenceMode: evidence.evidence_mode,
    costCurves: costCurvesMatchWorkload(workload, evidence.cost_curves)
  };
}

router.get('/health', (req, res) => {
  res.status(200).json({
    status: 'ok',
    service: 'edge-vs-cloud-backend',
    message: 'Backend is running'
  });
});

// POST /api/recommend
router.post('/recommend', async (req, res) => {
  try {
    const { workload, stage3Metrics, evidenceMode, costCurves } = getPayloadWithMetrics(req);
    const result = await calculateSuitability(workload, {
      metricsByTier: stage3Metrics,
      costCurves,
      evidenceMode
    });
    res.json(result);
  } catch (err) {
    handleRouteError(res, err, 'Recommendation');
  }
});

// POST /api/explain
router.post('/explain', async (req, res) => {
  try {
    const { workload, stage3Metrics, costCurves } = getPayloadWithMetrics(req);
    const pyResult = await callTeamEngine('explain', {
      workload,
      question: req.body.question || "why_not_tier",
      alternative_tier: req.body.alternative_tier || "cloud",
      metrics_by_tier: stage3Metrics,
      cost_curves: costCurves
    });
    res.json(pyResult);
  } catch (err) {
    handleRouteError(res, err, 'Explanation');
  }
});

// POST /api/simulate
router.post('/simulate', async (req, res) => {
  try {
    const { requestPayload, stage3Metrics } = getPayloadWithMetrics(req);
    const pyResult = await callTeamEngine('simulate', {
      request: requestPayload,
      changes: req.body.changes || {},
      metrics_by_tier: stage3Metrics,
      scenario_metrics_by_tier: req.body.scenario_metrics_by_tier || null
    });
    res.json(pyResult);
  } catch (err) {
    handleRouteError(res, err, 'Simulation');
  }
});

// POST /api/counterfactuals
router.post('/counterfactuals', async (req, res) => {
  try {
    const { requestPayload, stage3Metrics } = getPayloadWithMetrics(req);
    const pyResult = await callTeamEngine('counterfactuals', {
      request: requestPayload,
      fields: req.body.fields || ["device_available_ram_mb", "latency_requirement_ms", "privacy_requirement"],
      target_tier: req.body.target_tier || null,
      max_evaluations: req.body.max_evaluations,
      max_results: req.body.max_results,
      metrics_by_tier: stage3Metrics
    });
    res.json(pyResult);
  } catch (err) {
    handleRouteError(res, err, 'Counterfactuals');
  }
});

// POST /api/optimize
router.post('/optimize', async (req, res) => {
  try {
    const { workload, stage3Metrics, costCurves } = getPayloadWithMetrics(req);
    const pyResult = await callTeamEngine('optimize', {
      workload,
      metrics_by_tier: stage3Metrics,
      cost_curves: costCurves
    });
    res.json(pyResult);
  } catch (err) {
    handleRouteError(res, err, 'Optimization');
  }
});

// POST /api/report
router.post('/report', async (req, res) => {
  try {
    const { workload, stage3Metrics, evidenceMode, costCurves } = getPayloadWithMetrics(req);
    const reportData = await calculateSuitability(workload, {
      metricsByTier: stage3Metrics,
      costCurves,
      evidenceMode
    });

    generatePdfReport(reportData, res);
  } catch (err) {
    handleRouteError(res, err, 'Report generation');
  }
});

module.exports = router;