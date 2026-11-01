jest.mock('../services/pythonEngineBridge', () => ({
  callTeamEngine: jest.fn()
}));

const { callTeamEngine } = require('../services/pythonEngineBridge');
const { calculateSuitability, normalizeWorkload } = require('../services/suitabilityService');
const { getMetricsForWorkload } = require('../services/stage3MetricService');

describe('suitability service input contract', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    callTeamEngine.mockResolvedValue({ recommended_tier: null, scores: {} });
  });

  test('normalizes user-facing aliases before sending inputs to the scoring engine', async () => {
    const workload = {
      latency_target: 200,
      budget: 200,
      privacy: ' LOW ',
      criticality: 'HIGH',
      bandwidth_requirement: 'medium'
    };

    await calculateSuitability(workload);

    expect(normalizeWorkload(workload)).toEqual({
      latency_requirement_ms: 200,
      budget_monthly: 200,
      privacy_requirement: 'low',
      criticality: 'high',
      bandwidth_requirement: 'medium'
    });
    expect(callTeamEngine).toHaveBeenCalledWith('recommend', {
      workload: normalizeWorkload(workload),
      metrics_by_tier: getMetricsForWorkload(workload).metrics_by_tier,
      cost_curves: null
    });
  });

  test('retains the evidence used by scoring for report generation', async () => {
    const result = await calculateSuitability({
      latency_requirement_ms: 50,
      budget_monthly: 1000,
      privacy_requirement: 'high',
      criticality: 'high',
      bandwidth_requirement: 'medium'
    });

    expect(result.metrics_by_tier).toHaveProperty('on_device');
    expect(result.evidence_mode).toBe('illustrative_estimates');
  });
});
