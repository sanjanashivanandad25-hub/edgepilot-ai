const request = require('supertest');
const express = require('express');
const { callTeamEngine } = require('../services/pythonEngineBridge');
const apiRoutes = require('../routes/apiRoutes');
const { getMetricsForWorkload } = require('../services/stage3MetricService');

jest.mock('../services/pythonEngineBridge', () => ({
  callTeamEngine: jest.fn()
}));

const app = express();
app.use(express.json());
app.use('/api', apiRoutes);

const workload = {
  latency_requirement_ms: 50,
  bandwidth_requirement: 'medium',
  budget_monthly: 1000,
  privacy_requirement: 'high',
  criticality: 'high'
};
const demoMetrics = getMetricsForWorkload(workload).metrics_by_tier;

describe('Stage 5 and optimization API integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    callTeamEngine.mockResolvedValue({ ok: true });
  });

  test('POST /api/simulate forwards the request envelope and scenario metrics', async () => {
    const scenarioMetrics = { on_device: { latency_ms: null } };
    await request(app)
      .post('/api/simulate')
      .send({
        request: { workload },
        changes: { privacy_requirement: 'low' },
        scenario_metrics_by_tier: scenarioMetrics
      })
      .expect(200);

    expect(callTeamEngine).toHaveBeenCalledWith('simulate', {
      request: { workload },
      changes: { privacy_requirement: 'low' },
      metrics_by_tier: demoMetrics,
      scenario_metrics_by_tier: scenarioMetrics
    });
  });

  test('POST /api/counterfactuals forwards search bounds and target tier', async () => {
    await request(app)
      .post('/api/counterfactuals')
      .send({
        request: { workload },
        fields: ['privacy_requirement'],
        target_tier: 'cloud',
        max_evaluations: 40,
        max_results: 5
      })
      .expect(200);

    expect(callTeamEngine).toHaveBeenCalledWith('counterfactuals', {
      request: { workload },
      fields: ['privacy_requirement'],
      target_tier: 'cloud',
      max_evaluations: 40,
      max_results: 5,
      metrics_by_tier: demoMetrics
    });
  });

  test('POST /api/explain accepts the documented request envelope', async () => {
    await request(app)
      .post('/api/explain')
      .send({
        request: { workload },
        question: 'why_not_tier',
        alternative_tier: 'cloud'
      })
      .expect(200);

    expect(callTeamEngine).toHaveBeenCalledWith('explain', {
      workload,
      question: 'why_not_tier',
      alternative_tier: 'cloud',
      metrics_by_tier: demoMetrics,
      cost_curves: null
    });
  });

  test('POST /api/optimize uses the demo metrics for unmatched workloads', async () => {
    const metrics = { custom: true };
    const costCurves = { scenario_id: 'workload-a' };
    await request(app)
      .post('/api/optimize')
      .send({ workload, metrics_by_tier: metrics, cost_curves: costCurves })
      .expect(200);

    expect(callTeamEngine).toHaveBeenCalledWith('optimize', {
      workload,
      metrics_by_tier: demoMetrics,
      cost_curves: null
    });
  });

  test('POST /api/recommend normalizes workload aliases and forwards shared metrics', async () => {
    await request(app)
      .post('/api/recommend')
      .send({
        workload: {
          latency_target: 200,
          budget: 200,
          privacy: 'LOW',
          criticality: 'HIGH',
          bandwidth_requirement: 'medium'
        }
      })
      .expect(200);

    expect(callTeamEngine).toHaveBeenCalledWith('recommend', {
      workload: {
        latency_requirement_ms: 200,
        budget_monthly: 200,
        privacy_requirement: 'low',
        criticality: 'high',
        bandwidth_requirement: 'medium'
      },
      metrics_by_tier: demoMetrics,
      cost_curves: null
    });
  });
});
