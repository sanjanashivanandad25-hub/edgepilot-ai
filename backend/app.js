const express = require('express');
const cors = require('cors');
const path = require('path');
const { createApiSecurity } = require('./middleware/apiSecurity');

require('dotenv').config({ path: path.join(__dirname, '.env'), quiet: true });

const apiRoutes = require('./routes/apiRoutes');

const app = express();

const allowedOrigins = (process.env.CORS_ORIGINS || '')
  .split(',')
  .map((origin) => origin.trim())
  .filter(Boolean);

app.use(cors({
  origin: (origin, callback) => callback(null, !origin || allowedOrigins.includes(origin))
}));
app.use(express.json({ limit: '24kb' }));
app.use('/api', createApiSecurity({
  token: process.env.API_AUTH_TOKEN,
  bypassAuthentication: process.env.NODE_ENV === 'test'
}));

// Mount clean unified API router
app.use('/api', apiRoutes);

// General 404 handler
app.use((req, res) => {
  res.status(404).json({ error: `Route ${req.originalUrl} not found` });
});

app.use((err, req, res, next) => {
  if (err.type === 'entity.too.large') {
    return res.status(413).json({ error: 'Request body exceeds the 24 KiB limit.' });
  }
  if (err.type === 'entity.parse.failed') {
    return res.status(400).json({ error: 'Request body must contain valid JSON.' });
  }
  return next(err);
});

module.exports = app;