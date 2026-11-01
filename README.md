# EdgePilot AI

EdgePilot AI is a responsive React/Vite frontend for exploring workload placement
across on-device, far-edge, regional-edge, and cloud tiers. It is an original
recreation based on shared specifications and screenshots, not the original Manus
source or a proprietary implementation.

The Overview opens with a large, text-only introduction, followed by a full
deployment scene and a single summary of the four execution tiers. The next
section presents interactive decision signals with a selected-signal explanation
below the diagram, followed by the placement workflow. The scene and
decision-signal diagram are illustrative explainers, not live scoring or benchmark
visualizations; headings and section changes avoid card frames and divider rules.

The Overview is a continuous, scroll-driven scene rather than a set of dashboard
cards. Its deployment visualization is a lazy-loaded React Three Fiber scene with
a rotating computational core, spatially separated placement nodes, glowing
curved routes, moving data packets, pointer parallax, and keyboard-operable DOM
labels. When WebGL cannot start, the page falls back to the interactive SVG map.
The atmosphere spans the full page, with overlapping scroll-scrubbed scene
transitions; the placement loop adds a CSS perspective floor on larger screens
and stays flat on small screens.

The Analyzer pairs the existing workload controls with a live signal-profile
visualization. Latency, bandwidth, privacy, and budget bars summarize the
current input values; increasing the latency requirement increases its bar.
These display bars are not scores or recommendations. The preview does not
show an execution spectrum or select a tier before an analysis response is
received. Optional application/model context remains local to the browser.

The Results page ties its route visualization and tier comparison to the
current recommendation response. It does not show a selected route before an
analysis exists, and missing live scores or estimates remain explicitly
unprovided. Score bars are service suitability values, not probabilities or
verified hardware benchmarks. PDF reporting sends the same complete response
object that the Results page displays.

## Showcase-inspired visual addition

The Overview's cinematic atmosphere takes broad inspiration from
[Aether 1](https://aether1.ai/) and the
[Codrops technical case study](https://tympanus.net/codrops/2025/08/06/building-aether-1-sound-without-boundaries/).
That case study describes baked 3D scene animation, GPU flow-field particles,
multi-pass WebGL effects, cursor fluid simulation, and a custom Lenis scroll
controller. EdgePilot adapts the techniques to an information-dense deployment
tool: CSS lighting and a pointer-reactive 3D scene emphasize real placement
relationships, while SVG/CSS keeps the lower diagrams crisp and accessible.
Lenis is coordinated with GSAP ScrollTrigger for native-feeling scroll-linked
reveals, without pinning sections or looping the page. Motion and the WebGL
render loop are disabled or reduced when the user requests reduced motion, and
off-screen scene rendering is paused. No Aether copy, product imagery, or page
template is reproduced.

## Interaction and visual references

The visual implementation borrows interaction ideas—not source code or assets—
from [Bencho interactive UI components](https://bencho.dev/) and
[Animos motion templates](https://animos.app/editor). Examples include pointer-lit
visualization fields, hover-highlighted hub routes, focused node states, route
packets, dotted heading illumination, click ripples, and restrained hover
transitions. In-page navigation uses native smooth scrolling and honors reduced
motion settings. These are implemented locally with React, CSS, and SVG; there
are no imported Framer, Bencho, or Animos components. Decorative motion reduces
or becomes static when reduced motion is requested.

Scattered dot-grid text is applied to headings across the application, with a brighter
hover treatment. It and the click ripples are original CSS recreations inspired
by the Framer Marketplace
[dot grid](https://www.framer.com/marketplace/components/dot-grid-background/)
and [ripple](https://www.framer.com/marketplace/components/ripple/) concepts.

## Requirements

- Node.js 20.19+ or 22.12+
- npm

## Setup and commands

Start the backend from the cloned `backend/` directory in one terminal:

```bash
cd backend
npm ci
# Set API_AUTH_TOKEN in backend/.env using backend/.env.example as a guide.
npm start
```

In another terminal, create a root-level `.env.local` file containing the same
backend token and the backend origin reachable from Vite:

```text
API_AUTH_TOKEN=your-local-backend-token
API_BACKEND_URL=http://127.0.0.1:5001
```

Then start the frontend from the repository root:

```bash
npm install
npm run dev -- --host 0.0.0.0
```

The Vite development server proxies `/api` requests to `API_BACKEND_URL`
(default `http://127.0.0.1:5001`). It reads the bearer token from `.env.local` or
the `API_AUTH_TOKEN` process environment variable and adds it on the server side
for protected routes; the token is not included in browser code. Health checks
do not require authentication. `.env.local` is gitignored. Restart Vite after
changing these values. Never use a `VITE_` prefix for the token or commit it to
the frontend.

`localhost` and `127.0.0.1` refer to the machine or container running Vite. If
the backend runs in a separate environment, set `API_BACKEND_URL` to an address
that the Vite environment can reach, such as a forwarded port or the backend
machine's private network URL. A loopback URL will not connect across isolated
environments.

Vite prints the local development URL after it starts. To create a production
build:

```bash
npm run build
npm run preview
```

## Backend API contract

API calls are centralized in `src/services/api.js` and use the relative API
base:

```text
/api
```

During local development, Vite forwards these requests to
`API_BACKEND_URL/api`. JSON requests send `Content-Type: application/json`.
The backend requires `Authorization: Bearer <API_AUTH_TOKEN>` for all API
endpoints except health; the Vite proxy supplies it without exposing the token
to the browser.

### Health

On app load the frontend requests `GET /health`. A successful HTTP response shows
**Backend online**; HTTP errors, network errors, CORS failures, and tunnel failures
show **Backend unavailable**. A failed health check is never treated as healthy.

### Recommendation

`POST /recommend` receives the five supported workload fields nested under
`workload`. An optional benchmark profile adds model, device, runtime, and
precision so the backend can look for an exact catalog match:

```json
{
  "workload": {
    "latency_requirement_ms": 50,
    "bandwidth_requirement": "medium",
    "budget_monthly": 1000,
    "privacy_requirement": "high",
    "criticality": "high",
    "application_type": "smart_camera",
    "model_name": "mobilenet_v2",
    "target_device": "Samsung Galaxy S25 (Family)",
    "runtime": "tflite",
    "precision": "float"
  }
}
```

Latency is a number from 1 to 1000 milliseconds; budget is a non-negative number
in INR; bandwidth, privacy, and criticality are each `low`, `medium`, or `high`;
the complete JSON response is retained in app state for the Results page.
Estimates or scores missing from a live response are shown as not provided rather
than fabricated.

When an exact benchmark profile matches, the backend returns it in
`details.benchmark`, including inference latency, source, date, and measurement
scope. The Results page displays that provenance separately from service scores
and estimated end-to-end latency. The benchmark catalog is accessed through
`POST /recommend`; this backend does not expose a standalone benchmark-list
endpoint. Inference-only latency is not an end-to-end measurement.

### What-if simulator

The Results page can submit a hypothetical latency requirement to
`POST /simulate`:

```json
{
  "workload": {
    "latency_requirement_ms": 50,
    "bandwidth_requirement": "medium",
    "budget_monthly": 1000,
    "privacy_requirement": "high",
    "criticality": "high"
  },
  "changes": {
    "latency_requirement_ms": 100
  }
}
```

The backend returns baseline and scenario recommendations plus
`comparison.score_deltas`, `comparison.explanation`,
`comparison.metrics_handling`, and limitations. The UI displays the tier
transition and per-tier score changes. These are hypothetical, provisional
suitability results, not deployment actions or performance guarantees.

The UI supports score objects named `scores`, `tier_scores`, or
`suitability_scores`; recommendation labels can be returned as `recommendation`
or `recommended_tier`. Explanation text can be returned as `explanation`,
`rationale`, or `reasoning`. Monthly cost reads `estimates.monthly_cost` with
`estimates.currency`, `estimates.monthly_cost_inr`, or the top-level
`monthly_cost` with `currency`. INR values display with the rupee symbol.

### PDF report

`POST /report` receives the original workload under a `workload` property. The
backend reruns the recommendation for that workload and returns a PDF blob. The
browser downloads it as
`EdgePilot_Recommendation_Report.pdf`. The report action is only available after
a live recommendation response, not for the sample screen or mock responses.
The Results view reads its explanation, estimates, scores, warnings, trade-offs,
and assumptions from that same response object. Missing live scores or monthly
costs are shown as `Not provided`; the on-device score is read from the
`on_device` entry in the response's score object. Monthly cost in INR is
displayed with the rupee symbol and without a second currency suffix. Tier
scores are displayed beside each destination in the routing visualization,
directly from the service response, with no separate score panel.

The development proxy keeps browser requests on the frontend origin, avoiding
cross-origin browser requests. Request and download failures are displayed in
an error banner.

### Troubleshooting

- If the header reports **Backend unavailable**, verify the backend is listening
  on port 5001 and inspect the Vite terminal and browser network requests. A
  failed health check is not treated as online.
- If analysis fails, verify that the service accepts the documented
  `{ "workload": { ... } }` JSON body and that the backend-provided
  `API_AUTH_TOKEN` is set in `.env.local` before starting Vite.
- If a benchmark is not matched, confirm the model, target device, runtime, and
  precision match an evidence record exactly.
- If what-if simulation fails, verify the backend accepts the selected workload
  field in `changes`; the simulator rejects unchanged or unsupported values.
- If report download fails, verify the report endpoint accepts the original
  workload and returns a non-empty PDF blob.
- Enable mock mode to exercise the interface without a reachable service.

## Mock mode and illustrative data

Use the header toggle to enable **Mock mode on**. It works without the backend
and supplies a fixed example recommendation to the Results screen. A visible
notice marks it as a demo. Mock scores and estimates are
illustrative UI examples only: they are not probabilities, calibrated metrics,
real performance measurements, or hardware benchmarks. The `/results` route
also has an illustrative sample view before any analysis is run. Neither mode
can produce a live PDF report.

## Known limitations

- Recommendations require the configured service when mock mode is off.
- CORS and tunnel configuration must be managed by the backend deployment.
- Qualcomm hardware benchmark integration is pending a verified source, API, or
  benchmark dataset. No Qualcomm benchmark values or hardware performance
  claims are included.
- The CSS and SVG visual effects are original lightweight recreations inspired
  by dot-grid, interactive-gradient, gravity-particle, ripple, animated-gradient,
  gradient-motion, and shader-background concepts. No Framer components,
  WebGL shader package, or external animation library is integrated.
