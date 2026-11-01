const request = require('supertest');
const app = require('../app');
const { callTeamEngine } = require('../services/pythonEngineBridge');

jest.mock('../services/pythonEngineBridge', () => ({
  callTeamEngine: jest.fn()
}));

describe('API guardrails', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('health endpoint is mounted on the active API router', async () => {
    const response = await request(app).get('/api/health');

    expect(response.statusCode).toBe(200);
    expect(response.body).toHaveProperty('status', 'ok');
  });

  test('rejects malformed JSON with 400', async () => {
    const response = await request(app)
      .post('/api/recommend')
      .set('Content-Type', 'application/json')
      .send('{"workload":');

    expect(response.statusCode).toBe(400);
    expect(response.body).toHaveProperty('error', 'Request body must contain valid JSON.');
  });

  test('rejects request bodies above 24 KiB with 413', async () => {
    const response = await request(app)
      .post('/api/recommend')
      .send({ workload: { padding: 'x'.repeat(25 * 1024) } });

    expect(response.statusCode).toBe(413);
    expect(response.body).toHaveProperty('error', 'Request body exceeds the 24 KiB limit.');
    expect(callTeamEngine).not.toHaveBeenCalled();
  });

  test('returns engine validation failures as 422 with useful details', async () => {
    const error = new Error('Missing workload field: criticality');
    error.statusCode = 422;
    callTeamEngine.mockRejectedValue(error);

    const response = await request(app)
      .post('/api/recommend')
      .send({ workload: {} });

    expect(response.statusCode).toBe(422);
    expect(response.body).toEqual({
      error: 'Recommendation failed',
      details: 'Missing workload field: criticality'
    });
  });

  test('does not expose internal engine errors in API responses', async () => {
    callTeamEngine.mockRejectedValue(new Error('internal provider detail'));
    const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});

    const response = await request(app)
      .post('/api/recommend')
      .send({ workload: {} });

    expect(response.statusCode).toBe(500);
    expect(response.body).toEqual({ error: 'Recommendation failed' });
    expect(JSON.stringify(response.body)).not.toContain('internal provider detail');
    consoleError.mockRestore();
  });
});
