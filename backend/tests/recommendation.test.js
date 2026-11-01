const request = require('supertest');
const express = require('express');
const recommendationRoutes = require('../routes/recommendationRoutes');

const app = express();
app.use(express.json());
app.use('/api', recommendationRoutes);

describe('Backend API Integration Tests', () => {
  // Test Health Endpoint
  test('GET /api/health should return 200 OK', async () => {
    const response = await request(app).get('/api/health');
    expect(response.statusCode).toBe(200);
    expect(response.body.status).toBe('ok');
    expect(response.body.service).toBe('edge-vs-cloud-backend');
  });

  // Test Recommendation Endpoint
  test('POST /api/recommend should return valid recommendation contract', async () => {
    const payload = {
      workload: {
        latency_requirement_ms: 50,
        bandwidth_requirement: "medium",
        budget_monthly: 1000,
        privacy_requirement: "high",
        criticality: "high"
      }
    };

    const response = await request(app)
      .post('/api/recommend')
      .send(payload);

    expect(response.statusCode).toBe(200);
    expect(response.body).toHaveProperty('recommended_tier');
    expect(response.body).toHaveProperty('scores');
    expect(response.body).toHaveProperty('estimates');
    expect(response.body).toHaveProperty('explanation');
    expect(response.body).toHaveProperty('tradeoffs');
    expect(response.body).toHaveProperty('architecture');
  });

  // Test Missing Payload
  test('POST /api/recommend should return 400 when body is missing', async () => {
    const response = await request(app).post('/api/recommend').send({});
    expect(response.statusCode).toBe(400);
  });
});