const { getMetricsForWorkload } = require('../services/stage3MetricService');

describe('Stage 3 metric fixture lookup', () => {
  test.each([
    [{ target_device: 'Samsung Galaxy S24', runtime: 'ONNX Runtime' }],
    [{ target_device: 'Samsung Galaxy S25 (Family)', runtime: 'tflite' }],
    [{}]
  ])('returns demo fixtures regardless of workload profile', (workload) => {
    const result = getMetricsForWorkload(workload);

    expect(Object.keys(result.metrics_by_tier)).toEqual([
      'on_device',
      'far_edge',
      'regional_edge',
      'cloud'
    ]);
    expect(result.cost_curves).toHaveProperty('tiers');
    expect(result.evidence_mode).toBe('illustrative_estimates');
    expect(result.metrics_by_tier.on_device.latency_ms.value).toBe(15);
    expect(result.metrics_by_tier.cloud.monthly_cost_inr.value).toBe(300);
    expect(result).not.toHaveProperty('scores');
  });
});
