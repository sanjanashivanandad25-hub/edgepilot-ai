const express = require('express');
const request = require('supertest');
const { createApiSecurity } = require('../middleware/apiSecurity');

function createSecurityApp(options) {
  const app = express();
  app.use('/api', createApiSecurity(options));
  app.get('/api/health', (req, res) => res.json({ status: 'ok' }));
  app.get('/api/private', (req, res) => res.json({ status: 'authorized' }));
  return app;
}

describe('API authentication and rate limiting', () => {
  test('health remains public when no API token is configured', async () => {
    const app = createSecurityApp();

    await request(app).get('/api/health').expect(200);
    await request(app).get('/api/private').expect(503);
  });

  test('requires a matching Bearer token', async () => {
    const app = createSecurityApp({ token: 'test-secret' });

    await request(app).get('/api/private').expect(401);
    await request(app)
      .get('/api/private')
      .set('Authorization', 'Bearer wrong-secret')
      .expect(401);
    await request(app)
      .get('/api/private')
      .set('Authorization', 'Bearer test-secret')
      .expect(200);
  });

  test('limits authenticated requests per IP within the configured window', async () => {
    const app = createSecurityApp({ token: 'test-secret', limit: 2 });
    const sendAuthorized = () => request(app)
      .get('/api/private')
      .set('Authorization', 'Bearer test-secret');

    await sendAuthorized().expect(200);
    await sendAuthorized().expect(200);
    const response = await sendAuthorized().expect(429);
    expect(response.headers).toHaveProperty('retry-after');
  });

  test('does not apply authentication or rate limits to health checks', async () => {
    const app = createSecurityApp({ token: 'test-secret', limit: 1 });

    await request(app).get('/api/health').expect(200);
    await request(app).get('/api/health').expect(200);
  });
});
