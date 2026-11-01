const crypto = require('crypto');

function matchesToken(provided, expected) {
  const providedHash = crypto.createHash('sha256').update(provided).digest();
  const expectedHash = crypto.createHash('sha256').update(expected).digest();
  return crypto.timingSafeEqual(providedHash, expectedHash);
}

function createApiSecurity({
  token,
  limit = 60,
  windowMs = 60_000,
  bypassAuthentication = false
} = {}) {
  const clients = new Map();

  return (req, res, next) => {
    if (req.path === '/health') {
      return next();
    }

    if (!bypassAuthentication) {
      if (!token) {
        return res.status(503).json({ error: 'API authentication is not configured.' });
      }

      const authorization = req.get('authorization') || '';
      const match = authorization.match(/^Bearer\s+(.+)$/i);
      if (!match || !matchesToken(match[1], token)) {
        res.set('WWW-Authenticate', 'Bearer');
        return res.status(401).json({ error: 'Authentication required.' });
      }
    }

    const now = Date.now();
    const client = req.ip || req.socket.remoteAddress || 'unknown';
    let bucket = clients.get(client);
    if (!bucket || now >= bucket.resetAt) {
      bucket = { count: 0, resetAt: now + windowMs };
    }
    bucket.count += 1;
    clients.set(client, bucket);

    if (clients.size > 5000) {
      for (const [key, value] of clients) {
        if (now >= value.resetAt) {
          clients.delete(key);
        }
      }
      while (clients.size > 5000) {
        clients.delete(clients.keys().next().value);
      }
    }

    res.set('RateLimit-Limit', String(limit));
    res.set('RateLimit-Remaining', String(Math.max(0, limit - bucket.count)));
    res.set('RateLimit-Reset', String(Math.ceil(bucket.resetAt / 1000)));

    if (bucket.count > limit) {
      res.set('Retry-After', String(Math.max(1, Math.ceil((bucket.resetAt - now) / 1000))));
      return res.status(429).json({ error: 'Too many requests. Try again later.' });
    }

    return next();
  };
}

module.exports = { createApiSecurity };
