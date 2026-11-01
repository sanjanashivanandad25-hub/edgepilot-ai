# Backend API security configuration

Set `API_AUTH_TOKEN` in the backend's secret manager or private server environment.
Do not commit the token or expose it to browser code. Protected `/api` endpoints
require:

```http
Authorization: Bearer <API_AUTH_TOKEN>
```

`GET /api/health` remains unauthenticated for health checks. If the token is
missing, other API requests fail closed with HTTP 503. Invalid or missing bearer
tokens receive HTTP 401.

Set `CORS_ORIGINS` to a comma-separated allowlist of exact frontend origins
(scheme, host, and port, with no path). Cross-origin browser requests are not
allowed when the variable is unset. Requests without an `Origin` header, such
as server-to-server calls, are unaffected by CORS; they still require bearer
authentication.

Authenticated API clients are limited to 60 requests per IP address per
one-minute window; excess requests receive HTTP 429 and `Retry-After`. The
current limiter is in-memory and applies per Node process. For multiple
application instances, replace it with a shared rate-limit store before
deployment. Configure trusted proxy handling deliberately if rate limits must
use client IPs forwarded by a reverse proxy.

JSON request bodies are limited to 24 KiB. Invalid JSON returns HTTP 400 and
oversized bodies return HTTP 413. Engine input validation errors return HTTP
422; unexpected server errors return a generic message and are logged server
side.

This integration does not contain Person 3's workload-specific network or
cost models. If metrics are omitted, they remain unknown rather than being
filled with synthetic estimates. Before deployment, add trusted backend-side
metric and cost-curve providers; do not treat client-submitted provenance
labels such as `measured` or `quoted` as independently verified.

During local development outside Jest, configure `API_AUTH_TOKEN` before
calling protected routes. Jest bypasses auth so integration tests can exercise
the routes without a deployed secret.
