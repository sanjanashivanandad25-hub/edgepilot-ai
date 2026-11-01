// tests/api.test.js
const request = require('supertest');
const app = require('./app');

describe('EdgePilot API Integration Tests', () => {

  // Test GET /api/health
  test('GET /api/health returns 200 OK', async () => {
    const res = await request(app).get('/api/health');
    expect(res.statusCode).toBe(200);
    expect(res.body).toHaveProperty('status', 'ok');
  });

  // Test POST /api/recommend
  test('POST /api/recommend returns recommendations from Python engine', async () => {
    const samplePayload = {
      workload: {
        latency_requirement_ms: 50,
        bandwidth_requirement: 'medium',
        budget_monthly: 1000,
        privacy_requirement: 'high',
        criticality: 'high'
      }
    };

    const res = await request(app)
      .post('/api/recommend')
      .send(samplePayload);

    expect(res.statusCode).toBe(200);
    expect(res.body).toHaveProperty('recommended_tier');
    expect(res.body).toHaveProperty('scores');
    expect(res.body).toHaveProperty('estimates');
    expect(res.body.details.reliability.errors).toEqual([]);
    expect(res.body.details.tier_estimates.on_device.latency_ms).toBe(15);
    expect(res.body.details.tier_estimates.on_device.latency_source).toBe('estimated');
  });

});