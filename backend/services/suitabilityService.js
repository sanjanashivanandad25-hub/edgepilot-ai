const { callTeamEngine } = require('./pythonEngineBridge');
const { getMetricsForWorkload } = require('./stage3MetricService');

const WORKLOAD_ALIASES = {
  latency_target: 'latency_requirement_ms',
  budget: 'budget_monthly',
  privacy: 'privacy_requirement'
};

function normalizeWorkload(workload) {
  if (!workload || typeof workload !== 'object' || Array.isArray(workload)) {
    return workload;
  }

  const normalized = { ...workload };
  for (const [alias, field] of Object.entries(WORKLOAD_ALIASES)) {
    if (!Object.prototype.hasOwnProperty.call(normalized, field)
        && Object.prototype.hasOwnProperty.call(normalized, alias)) {
      normalized[field] = normalized[alias];
    }
    delete normalized[alias];
  }

  for (const field of ['bandwidth_requirement', 'privacy_requirement', 'criticality']) {
    if (typeof normalized[field] === 'string') {
      normalized[field] = normalized[field].trim().toLowerCase();
    }
  }

  return normalized;
}

function costCurvesMatchWorkload(workload, costCurves) {
  const workloadMatch = costCurves && costCurves.workload_match;
  if (!workloadMatch || !workload || typeof workload !== 'object') return null;

  return Object.entries(workloadMatch).every(([key, value]) => workload[key] === value)
    ? costCurves
    : null;
}

async function calculateSuitability(workload, { metricsByTier, costCurves, evidenceMode } = {}) {
  const normalizedWorkload = normalizeWorkload(workload);
  const evidence = metricsByTier
    ? { metrics_by_tier: metricsByTier, evidence_mode: evidenceMode || 'provided' }
    : getMetricsForWorkload(normalizedWorkload);
  const result = await callTeamEngine('recommend', {
    workload: normalizedWorkload,
    metrics_by_tier: evidence.metrics_by_tier,
    cost_curves: costCurvesMatchWorkload(normalizedWorkload, costCurves)
  });

  return {
    ...result,
    workload: normalizedWorkload,
    metrics_by_tier: evidence.metrics_by_tier,
    evidence_mode: evidence.evidence_mode
  };
}

module.exports = { calculateSuitability, normalizeWorkload, costCurvesMatchWorkload };
