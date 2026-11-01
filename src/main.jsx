import { Component, lazy, Suspense, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  checkBackendHealth,
  getRecommendation,
  getRecommendationReport,
  simulateWorkload,
} from './services/api.js';
import './styles.css';

const HeroScene = lazy(() => import('./components/HeroScene.jsx'));
let activeLenis = null;

const TIERS = ['On-device', 'Far edge', 'Regional edge', 'Cloud'];
const INITIAL_WORKLOAD = {
  latency_requirement_ms: 50,
  bandwidth_requirement: 'medium',
  budget_monthly: '1000',
  privacy_requirement: 'high',
  criticality: 'high',
};
const BENCHMARK_PROFILES = {
  mobilenetS25: {
    application_type: 'smart_camera',
    model_name: 'mobilenet_v2',
    target_device: 'Samsung Galaxy S25 (Family)',
    runtime: 'tflite',
    precision: 'float',
  },
  mobilenetS24: {
    application_type: 'smart_camera',
    model_name: 'mobilenet_v2',
    target_device: 'Samsung Galaxy S24',
    runtime: 'ONNX Runtime',
    precision: 'w8a8',
  },
};
const MOCK_RECOMMENDATION = {
  recommendation: 'Regional edge',
  rationale:
    'Illustrative routing for a balanced workload: latency, privacy, cost and resilience have competing requirements.',
  estimates: {
    latency_ms: 42,
    monthly_cost_inr: 1800,
  },
  scores: {
    'On-device': 78,
    'Far edge': 86,
    'Regional edge': 93,
    Cloud: 68,
  },
  warnings: [
    'Illustrative estimate — validate with measured workload traffic before production rollout.',
  ],
  tradeoffs: ['Requires a managed edge infrastructure layer.'],
  assumptions: ['Regional capacity is available near the primary user population.'],
};

const ROUTES = [
  ['/', 'Overview'],
  ['/analyzer', 'Analyzer'],
  ['/results', 'Results'],
];

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function navigateTo(path, setPath) {
  if (window.location.pathname !== path) {
    window.history.pushState({}, '', path);
  }
  setPath(path);
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (activeLenis && !reduceMotion) {
    activeLenis.scrollTo(0, { immediate: true });
  } else {
    window.scrollTo({ top: 0, behavior: 'auto' });
  }
}

function Header({ path, setPath, mockMode, setMockMode, health }) {
  const healthLabel = {
    checking: 'Checking backend',
    online: 'Backend online',
    offline: 'Backend unavailable',
  }[health];

  return (
    <header className="site-header">
      <a
        className="brand"
        href="/"
        onClick={(event) => {
          event.preventDefault();
          navigateTo('/', setPath);
        }}
        aria-label="EdgePilot AI overview"
      >
        <span className="orbit" aria-hidden="true" />
        <span>EdgePilot</span>
        <span className="brand-ai">AI</span>
      </a>
      <nav className="primary-nav" aria-label="Main navigation">
        {ROUTES.map(([route, label]) => (
          <a
            key={route}
            href={route}
            className={path === route ? 'active' : ''}
            aria-current={path === route ? 'page' : undefined}
            onClick={(event) => {
              event.preventDefault();
              navigateTo(route, setPath);
            }}
          >
            {label}
          </a>
        ))}
      </nav>
      <div className="header-actions">
        <span className={`backend-status ${health}`} role="status" aria-live="polite">
          <span className="status-dot" aria-hidden="true" />
          {healthLabel}
        </span>
        <button
          className="mode-toggle"
          type="button"
          aria-pressed={mockMode}
          onClick={() => setMockMode((enabled) => !enabled)}
        >
          {mockMode ? 'Mock mode on' : 'Use mock mode'}
        </button>
        <button
          className="button button-outline header-analyze"
          type="button"
          onClick={() => navigateTo('/analyzer', setPath)}
        >
          Analyze workload <span aria-hidden="true">↗</span>
        </button>
      </div>
    </header>
  );
}

const DEPLOYMENT_ROUTES = {
  'On-device': 'M400 216 C330 192 275 130 220 90',
  'Far edge': 'M400 216 C325 244 275 290 220 284',
  'Regional edge': 'M400 216 C475 244 525 290 580 284',
  Cloud: 'M400 216 C470 192 525 130 580 90',
};

const DEPLOYMENT_DETAILS = {
  'On-device': [
    'Private execution',
    'Closest to the data, with private, immediate execution.',
    'Local execution avoids a network hop and keeps data close to its source.',
  ],
  'Far edge': [
    'Nearby execution',
    'A nearby layer for low-latency, distributed workloads.',
    'Nearby compute trades some locality for distributed capacity.',
  ],
  'Regional edge': [
    'Balanced placement',
    'A regional fabric balancing latency, data locality, and scale.',
    'Balances local responsiveness with broader shared capacity.',
  ],
  Cloud: [
    'Centralized execution',
    'Centralized capacity with room to scale.',
    'More distance can bring elastic, centralized capacity.',
  ],
};

function updatePointerLight(event) {
  const bounds = event.currentTarget.getBoundingClientRect();
  event.currentTarget.style.setProperty(
    '--pointer-x',
    `${((event.clientX - bounds.left) / bounds.width) * 100}%`,
  );
  event.currentTarget.style.setProperty(
    '--pointer-y',
    `${((event.clientY - bounds.top) / bounds.height) * 100}%`,
  );
}

function DeploymentMapFallback() {
  const [selectedTier, setSelectedTier] = useState('Regional edge');
  const activePath = DEPLOYMENT_ROUTES[selectedTier];
  const [detailTitle, detailCopy, detailContext] = DEPLOYMENT_DETAILS[selectedTier];
  const tierClass = selectedTier.toLowerCase().replaceAll(' ', '-');

  return (
    <div className="deployment-map-wrap">
      <section
        className={`deployment-map tier-${tierClass}`}
        aria-label="Illustrative workload deployment map"
        onPointerMove={updatePointerLight}
      >
        <div className="map-grid" aria-hidden="true" />
        <div className="map-technical-labels" aria-hidden="true">
          <span className="map-label-latency">LATENCY</span>
          <span className="map-label-compute">COMPUTE SIGNAL / 04</span>
          <span className="map-label-routing">MODEL ROUTING</span>
          <span className="map-label-locality">DATA LOCALITY</span>
          <span className="map-label-inference">INFERENCE</span>
        </div>
        <svg
          className="map-paths"
          viewBox="0 0 800 440"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path className="route-muted" d={DEPLOYMENT_ROUTES['On-device']} />
          <path className="route-muted" d={DEPLOYMENT_ROUTES['Far edge']} />
          <path className="route-muted" d={DEPLOYMENT_ROUTES['Regional edge']} />
          <path className="route-muted" d={DEPLOYMENT_ROUTES.Cloud} />
          <path className={`route-selected route-${tierClass}`} d={activePath} />
          <circle className="signal-dot" r="4">
            <animateMotion dur="5s" repeatCount="indefinite" path={activePath} />
          </circle>
          <circle className="signal-dot signal-dot-secondary" r="2.5">
            <animateMotion dur="7s" begin="-2.4s" repeatCount="indefinite" path={activePath} />
          </circle>
          <circle className="signal-dot signal-dot-secondary" r="2">
            <animateMotion dur="9s" begin="-5.8s" repeatCount="indefinite" path={activePath} />
          </circle>
        </svg>
        <button
          className={`map-node node-device ${selectedTier === 'On-device' ? 'is-active' : ''}`}
          type="button"
          aria-pressed={selectedTier === 'On-device'}
          onMouseEnter={() => setSelectedTier('On-device')}
          onFocus={() => setSelectedTier('On-device')}
          onClick={() => setSelectedTier('On-device')}
        >
          <span aria-hidden="true">▣</span>
          <strong>ON-DEVICE</strong>
          <small>private / immediate</small>
        </button>
        <button
          className={`map-node node-far ${selectedTier === 'Far edge' ? 'is-active' : ''}`}
          type="button"
          aria-pressed={selectedTier === 'Far edge'}
          onMouseEnter={() => setSelectedTier('Far edge')}
          onFocus={() => setSelectedTier('Far edge')}
          onClick={() => setSelectedTier('Far edge')}
        >
          <span aria-hidden="true">⌁</span>
          <strong>FAR EDGE</strong>
          <small>nearby / resilient</small>
        </button>
        <button
          className={`map-node node-regional ${selectedTier === 'Regional edge' ? 'is-active' : ''}`}
          type="button"
          aria-pressed={selectedTier === 'Regional edge'}
          onMouseEnter={() => setSelectedTier('Regional edge')}
          onFocus={() => setSelectedTier('Regional edge')}
          onClick={() => setSelectedTier('Regional edge')}
        >
          <span aria-hidden="true">⌘</span>
          <strong>REGIONAL EDGE</strong>
          <small>balanced / selected</small>
        </button>
        <button
          className={`map-node node-cloud ${selectedTier === 'Cloud' ? 'is-active' : ''}`}
          type="button"
          aria-pressed={selectedTier === 'Cloud'}
          onMouseEnter={() => setSelectedTier('Cloud')}
          onFocus={() => setSelectedTier('Cloud')}
          onClick={() => setSelectedTier('Cloud')}
        >
          <span aria-hidden="true">▤</span>
          <strong>CLOUD</strong>
          <small>elastic / centralized</small>
        </button>
        <div className="workload-node">
          <span className="workload-aura" aria-hidden="true" />
          <svg
            className="workload-wireframe"
            viewBox="0 0 100 100"
            aria-hidden="true"
            focusable="false"
          >
            <path d="M50 4 77 17 94 43 84 73 58 94 27 86 7 61 12 30 32 10Z M50 4 58 94 M77 17 27 86 M94 43 7 61 M84 73 12 30 M32 10 84 73 M50 4 7 61 M77 17 58 94 M94 43 27 86 M12 30 58 94 M32 10 94 43 M7 61 84 73 M27 86 77 17" />
          </svg>
          <strong>AI</strong>
          <span>WORKLOAD</span>
        </div>
      </section>
      <div className="map-caption" aria-live="polite">
        <span>Illustrative sample signal · {detailTitle}</span>
        <strong>{selectedTier}</strong>
        <p>{detailCopy}</p>
        <small>{detailContext}</small>
      </div>
    </div>
  );
}

class SceneErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    console.error('Interactive deployment scene failed; using the illustrative SVG fallback.', error);
  }

  render() {
    if (this.state.failed) return this.props.fallback;
    return this.props.children;
  }
}

function DeploymentMap() {
  const fallback = <DeploymentMapFallback />;

  return (
    <SceneErrorBoundary fallback={fallback}>
      <Suspense fallback={fallback}>
        <HeroScene />
      </Suspense>
    </SceneErrorBoundary>
  );
}

const DECISION_SIGNALS = [
  {
    name: 'LATENCY',
    detail: 'response time',
    explanation: 'Tighter response targets pull the route toward nearby execution.',
    followUp: 'Shorter network paths can help meet a strict response-time target.',
  },
  {
    name: 'BANDWIDTH',
    detail: 'data movement',
    explanation: 'Data movement needs shape which parts of a workload should travel.',
    followUp: 'Keeping transfers small can reduce pressure on limited connections.',
  },
  {
    name: 'PRIVACY',
    detail: 'data locality',
    explanation: 'Data locality can favor execution closer to its source.',
    followUp: 'Local processing can also limit how much sensitive data travels.',
  },
  {
    name: 'BUDGET',
    detail: 'monthly guardrail',
    explanation: 'A monthly guardrail frames the trade-offs between tiers.',
    followUp: 'Compare compute and network costs against the workload budget.',
  },
  {
    name: 'RESILIENCE',
    detail: 'failure impact',
    explanation: 'Failure impact informs where resilience belongs in the route.',
    followUp: 'Critical workloads may need redundancy across more than one tier.',
  },
];

function SignalGraph() {
  const [selected, setSelected] = useState(0);
  const signal = DECISION_SIGNALS[selected];
  const positions = [
    { left: '50%', top: '5%' },
    { left: '86%', top: '34%' },
    { left: '74%', top: '81%' },
    { left: '25%', top: '81%' },
    { left: '14%', top: '34%' },
  ];

  return (
    <div className="signal-graph-wrap">
      <div className="visual-topline signal-topline">
        <span>DECISION SIGNALS / 05</span>
      </div>
      <div
        className="signal-graph"
        role="group"
        aria-label="Illustrative workload decision signals"
        onPointerMove={updatePointerLight}
      >
        <svg viewBox="0 0 600 430" preserveAspectRatio="none" aria-hidden="true">
          {DECISION_SIGNALS.map((item, index) => {
            const endPoints = [
              [300, 54, 300, 164],
              [516, 154, 367, 204],
              [444, 355, 340, 255],
              [156, 355, 260, 255],
              [84, 154, 233, 204],
            ][index];
            return (
              <line
                key={item.name}
                className={`signal-edge ${selected === index ? 'is-active' : ''}`}
                x1={endPoints[0]}
                y1={endPoints[1]}
                x2={endPoints[2]}
                y2={endPoints[3]}
              />
            );
          })}
          <line className="signal-travel" x1="300" y1="54" x2="300" y2="164" />
        </svg>
        <div className="signal-center">
          <strong>PLACEMENT</strong>
          <span>signal model</span>
        </div>
        {DECISION_SIGNALS.map((item, index) => (
          <button
            className={`signal-node signal-node-${index} ${selected === index ? 'is-active' : ''}`}
            style={positions[index]}
            key={item.name}
            type="button"
            aria-pressed={selected === index}
            onFocus={() => setSelected(index)}
            onClick={() => setSelected(index)}
          >
            <strong>{item.name}</strong>
            <small>{item.detail}</small>
          </button>
        ))}
      </div>
      <div className="signal-caption" aria-live="polite">
        <strong><i aria-hidden="true" /> {signal.name}</strong>
        <p>{signal.explanation} {signal.followUp}</p>
      </div>
      <p className="visual-caveat">Sample explanations only — no signal is being scored here.</p>
    </div>
  );
}

function PlacementLoop({ setPath }) {
  return (
    <section
      className="story-section placement-loop"
      aria-labelledby="loop-title"
      onPointerMove={updatePointerLight}
    >
      <div className="loop-heading">
        <p className="section-kicker">03 / FROM INPUT TO ROUTE</p>
        <h2 id="loop-title">Describe. Compare. <span>Deploy.</span></h2>
        <p>A workload becomes a recommendation through one transparent visual loop.</p>
      </div>
      <div className="loop-diagram">
        <div className="visual-topline loop-topline">
          <span>THE PLACEMENT LOOP / 03</span>
          <span>ONE SIGNAL <i aria-hidden="true">→</i> ONE ROUTE</span>
        </div>
        <div className="loop-rail" aria-label="Illustrative three-step placement loop">
          <svg viewBox="0 0 900 240" preserveAspectRatio="none" aria-hidden="true">
            <path className="loop-fog" d="M55 130 C210 40 275 205 450 120 S700 45 845 125" />
            <path className="loop-path" d="M55 130 C210 40 275 205 450 120 S700 45 845 125" />
            <circle className="loop-signal" r="4">
              <animateMotion
                dur="9s"
                repeatCount="indefinite"
                path="M55 130 C210 40 275 205 450 120 S700 45 845 125"
              />
            </circle>
            <circle className="loop-signal-static" cx="55" cy="130" r="4" />
          </svg>
          <article className="loop-step loop-step-1">
            <span className="loop-number">01</span>
            <strong>DESCRIBE WORKLOAD</strong>
            <small>requirements in</small>
          </article>
          <article className="loop-step loop-step-2">
            <span className="loop-number">02</span>
            <strong>COMPARE TIERS</strong>
            <small>signals aligned</small>
          </article>
          <article className="loop-step loop-step-3">
            <span className="loop-number">03</span>
            <strong>GET RECOMMENDATION</strong>
            <small>route out</small>
          </article>
        </div>
      </div>
      <button
        className="button button-primary loop-action"
        type="button"
        onClick={() => navigateTo('/analyzer', setPath)}
      >
        Analyze your workload <span aria-hidden="true">→</span>
      </button>
      <p className="visual-caveat">Illustrative workflow — recommendations require an actual analysis.</p>
    </section>
  );
}

function Overview({ setPath }) {
  return (
    <main className="overview-page">
      <section
        className="story-section overview-hero"
        aria-labelledby="overview-title"
        onPointerMove={updatePointerLight}
      >
        <section className="hero-copy">
          <h1
            id="overview-title"
            className="dot-grid-title"
            onPointerMove={updatePointerLight}
          >
            <span className="dot-grid-line" data-grid-text="Deploy AI">
              Deploy <span>AI</span>
            </span>
            <span className="dot-grid-line" data-grid-text="where it">
              where it
            </span>
            <span className="dot-grid-line" data-grid-text="performs best.">
              performs best.
            </span>
          </h1>
          <p className="hero-description">
            EdgePilot finds the right execution tier for your workload — balancing speed,
            privacy, cost, and scale.
          </p>
        </section>
      </section>
      <section
        className="story-section deployment-section"
        aria-labelledby="deployment-title"
        onPointerMove={updatePointerLight}
      >
        <div className="deployment-heading">
          <p className="section-kicker">01 / EXECUTION TIERS</p>
          <h2 id="deployment-title">One workload. Four places to run it.</h2>
        </div>
        <div className="deployment-visual">
          <DeploymentMap />
        </div>
        <div className="execution-summary">
          <span>FOUR TIERS / ONE WORKLOAD</span>
          <div className="execution-tiers" role="list">
            <div role="listitem">
              <strong>On-device</strong>
              <p>Private, immediate execution close to the data.</p>
            </div>
            <div role="listitem">
              <strong>Far edge</strong>
              <p>Nearby compute for responsive workloads.</p>
            </div>
            <div role="listitem">
              <strong>Regional edge</strong>
              <p>Balanced latency, locality, and scale.</p>
            </div>
            <div role="listitem">
              <strong>Cloud</strong>
              <p>Centralized capacity with room to scale.</p>
            </div>
          </div>
        </div>
      </section>
      <section
        className="story-section signals-section"
        aria-labelledby="signals-title"
        onPointerMove={updatePointerLight}
      >
        <div className="story-copy signals-copy">
          <p className="section-kicker">02 / DECISION SIGNALS</p>
          <h2 id="signals-title">
            Placement
            <br />
            follows
            <br />
            <span>the signal.</span>
          </h2>
          <p>
            Latency, bandwidth, privacy, budget, and resilience pull the route in
            different directions.
          </p>
        </div>
        <SignalGraph />
      </section>
      <PlacementLoop setPath={setPath} />
    </main>
  );
}

function SelectField({ label, name, value, onChange }) {
  return (
    <label className="field">
      <span>{label}</span>
      <select name={name} value={value} onChange={onChange}>
        <option value="low">Low</option>
        <option value="medium">Medium</option>
        <option value="high">High</option>
      </select>
    </label>
  );
}

function WorkloadSignalPreview({ workload }) {
  const [pulse, setPulse] = useState(false);
  const pulseTimer = useRef(null);
  const latency = Number(workload.latency_requirement_ms);
  const latencySignal = Math.round((latency / 1000) * 100);
  const bandwidthSignal = { low: 28, medium: 58, high: 88 }[workload.bandwidth_requirement];
  const privacySignal = { low: 28, medium: 58, high: 88 }[workload.privacy_requirement];
  const budget = Number(workload.budget_monthly);
  const budgetSignal = Number.isFinite(budget) ? Math.min(100, Math.max(0, (budget / 10000) * 100)) : 0;
  const values = [
    ['LATENCY', `${latency} ms`, latencySignal],
    ['BANDWIDTH', workload.bandwidth_requirement, bandwidthSignal],
    ['PRIVACY', workload.privacy_requirement, privacySignal],
    ['BUDGET', `₹${workload.budget_monthly || '0'}`, budgetSignal],
  ];
  const previewKey = [
    workload.latency_requirement_ms,
    workload.bandwidth_requirement,
    workload.privacy_requirement,
    workload.budget_monthly,
  ].join('|');

  useEffect(() => {
    setPulse(true);
    window.clearTimeout(pulseTimer.current);
    pulseTimer.current = window.setTimeout(() => setPulse(false), 460);
    return () => window.clearTimeout(pulseTimer.current);
  }, [previewKey]);

  return (
    <section
      className={`workload-review ${pulse ? 'is-updating' : ''}`}
      aria-label="Live workload preview"
      aria-live="polite"
    >
      <div className="preview-heading">
        <div>
          <span className="preview-kicker">LIVE WORKLOAD PREVIEW</span>
          <strong>Signal profile</strong>
          <p className="preview-description">
            A visual summary of your current inputs. Bars are scaled for display, not scores.
          </p>
        </div>
      </div>

      <div className="preview-rail" aria-hidden="true">
        <span className="preview-rail-glow" />
        <i className="preview-particle preview-particle-one" />
        <i className="preview-particle preview-particle-two" />
        <i className="preview-particle preview-particle-three" />
      </div>

      <div className="preview-signals">
        {values.map(([label, value, intensity]) => (
          <div className="preview-signal" key={label}>
            <div className="preview-signal-meta">
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
            <div className="preview-signal-meter" aria-hidden="true">
              <span style={{ '--signal-level': `${intensity}%` }} />
            </div>
          </div>
        ))}
      </div>

      <p className="preview-disclaimer">
        Your inputs are sent for analysis only when you run it. No tier is recommended here.
      </p>
    </section>
  );
}

function Analyzer({ workload, setWorkload, onAnalyze, busy }) {
  const [applicationType, setApplicationType] = useState('');
  const [modelSize, setModelSize] = useState('');
  const [benchmarkProfile, setBenchmarkProfile] = useState('');

  function updateWorkload(event) {
    const { name, value } = event.target;
    setWorkload((current) => ({
      ...current,
      [name]:
        name === 'latency_requirement_ms' ? Number(value) : value,
    }));
  }

  function increaseBudget() {
    setWorkload((current) => {
      const currentBudget = Number(current.budget_monthly);
      const nextBudget = (Number.isFinite(currentBudget) ? currentBudget : 0) + 1000;
      return { ...current, budget_monthly: String(nextBudget) };
    });
  }

  function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.reportValidity()) return;
    const budget = Number(workload.budget_monthly);
    if (!Number.isFinite(budget) || budget < 0) return;

    onAnalyze({
      latency_requirement_ms: Number(workload.latency_requirement_ms),
      bandwidth_requirement: workload.bandwidth_requirement,
      budget_monthly: budget,
      privacy_requirement: workload.privacy_requirement,
      criticality: workload.criticality,
      ...(benchmarkProfile ? BENCHMARK_PROFILES[benchmarkProfile] : {}),
    });
  }

  return (
    <main className="page analyzer-page" onPointerMove={updatePointerLight}>
      <div className="analyzer-atmosphere" aria-hidden="true">
        <span className="analyzer-orbit analyzer-orbit-one" />
        <span className="analyzer-orbit analyzer-orbit-two" />
        <span className="analyzer-signal-mark"><i /><i /><i /></span>
      </div>
      <header className="analyzer-hero">
        <p className="eyebrow analyzer-eyebrow">
          <span className="eyebrow-dot" aria-hidden="true" />
          WORKLOAD ANALYZER <span className="analyzer-eyebrow-meta">/ INPUT → ROUTE</span>
        </p>
        <h1 className="page-title">Shape your deployment <span>route.</span></h1>
        <div className="analyzer-hero-bottom">
          <p className="page-intro">
            Set the conditions your workload needs. Your live signal preview responds as you shape them.
          </p>
          <span className="analyzer-data-note">
            <i aria-hidden="true" />
            Only required fields are sent for analysis
          </span>
        </div>
      </header>
      <form className="form-card analyzer-form" onSubmit={submit}>
        <div className="analyzer-form-layout">
          <div className="analyzer-controls">
            <div className="latency-control">
              <label htmlFor="latency">
                <span>Latency requirement</span>
                <strong>{workload.latency_requirement_ms} ms</strong>
              </label>
              <input
                id="latency"
                name="latency_requirement_ms"
                type="range"
                min="1"
                max="1000"
                step="1"
                value={workload.latency_requirement_ms}
                onChange={updateWorkload}
                style={{ '--latency-progress': `${((Number(workload.latency_requirement_ms) - 1) / 999) * 100}%` }}
                aria-valuetext={`${workload.latency_requirement_ms} milliseconds`}
              />
              <div className="range-labels">
                <span>1 ms</span>
                <span>1,000 ms</span>
              </div>
            </div>
            <div className="form-grid">
              <SelectField
                label="Bandwidth requirement"
                name="bandwidth_requirement"
                value={workload.bandwidth_requirement}
                onChange={updateWorkload}
              />
              <div className="field">
                <label htmlFor="budget-monthly">Monthly budget <small>(INR)</small></label>
                <div className="currency-input">
                  <span aria-hidden="true">₹</span>
                  <input
                    id="budget-monthly"
                    name="budget_monthly"
                    type="number"
                    min="0"
                    step="any"
                    required
                    value={workload.budget_monthly}
                    onChange={updateWorkload}
                    inputMode="decimal"
                  />
                  <button
                    className="budget-increment"
                    type="button"
                    aria-label="Increase monthly budget by ₹1,000"
                    onClick={increaseBudget}
                  >
                    +1,000
                  </button>
                </div>
              </div>
              <SelectField
                label="Privacy requirement"
                name="privacy_requirement"
                value={workload.privacy_requirement}
                onChange={updateWorkload}
              />
              <SelectField
                label="Criticality"
                name="criticality"
                value={workload.criticality}
                onChange={updateWorkload}
              />
            </div>
          </div>

          <WorkloadSignalPreview workload={workload} />
        </div>
        <fieldset className="optional-fields">
          <legend>Optional context — application notes stay local</legend>
          <div className="form-grid">
            <label className="field">
              <span>Application type</span>
              <input
                type="text"
                value={applicationType}
                onChange={(event) => setApplicationType(event.target.value)}
                placeholder="e.g. vision inspection"
              />
            </label>
            <label className="field">
              <span>Model size</span>
              <input
                type="text"
                value={modelSize}
                onChange={(event) => setModelSize(event.target.value)}
                placeholder="e.g. 2B parameters"
              />
            </label>
          </div>
        </fieldset>
        <fieldset className="optional-fields benchmark-profile-fields">
          <legend>Optional Qualcomm inference benchmark match</legend>
          <label className="field" htmlFor="benchmark-profile">
            <span>Benchmark profile</span>
            <select
              id="benchmark-profile"
              value={benchmarkProfile}
              onChange={(event) => setBenchmarkProfile(event.target.value)}
            >
              <option value="">No specific model/device</option>
              <option value="mobilenetS25">MobileNet V2 · Galaxy S25 · TFLite · float</option>
              <option value="mobilenetS24">MobileNet V2 · Galaxy S24 · ONNX Runtime · W8A8</option>
            </select>
            <small>
              Only exact profile matches are returned. Inference latency is not end-to-end latency.
            </small>
          </label>
        </fieldset>
        <div className="form-submit">
          {busy && (
            <p className="loading-message" role="status" aria-live="polite">
              <span className="loading-spinner" aria-hidden="true" />
              Reading workload constraints…
            </p>
          )}
          <button className="button button-primary" type="submit" disabled={busy}>
            {busy ? 'Analyzing…' : 'Run placement analysis'}
            {!busy && <span aria-hidden="true">→</span>}
          </button>
        </div>
      </form>
    </main>
  );
}

function DemoNotice() {
  return (
    <div className="notice demo-notice">
      Demo mode is on. Results are illustrative UI examples, not real benchmarks or
      probabilities.
    </div>
  );
}

function readScores(result, allowIllustrativeScores) {
  const source =
    result.scores || result.tier_scores || result.suitability_scores || {};
  const illustrative = MOCK_RECOMMENDATION.scores;

  return TIERS.map((tier) => {
    const snakeCase = normalizeTierKey(tier);
    const hyphenCase = snakeCase.replaceAll('_', '-');
    const score =
      source[tier] ?? source[snakeCase] ?? source[hyphenCase] ??
      (allowIllustrativeScores ? illustrative[tier] : undefined);
    const numericScore =
      score !== null && score !== undefined && score !== '' && Number.isFinite(Number(score))
        ? Number(score)
        : null;

    return [tier, numericScore];
  });
}

function normalizeTierKey(value) {
  return String(value ?? '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function formatTierName(value) {
  return TIERS.find((tier) => normalizeTierKey(tier) === normalizeTierKey(value)) ?? value;
}

function DeploymentRouteDiagram({ recommendation, scores, hasResult, resultSource }) {
  const [motionAllowed, setMotionAllowed] = useState(
    () => !window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );
  const selectedTier = TIERS.find(
    (tier) => normalizeTierKey(tier) === normalizeTierKey(recommendation),
  );
  const selectedId = selectedTier ? `route-${normalizeTierKey(selectedTier)}` : null;
  const destinations = [
    { tier: TIERS[0], y: 45 },
    { tier: TIERS[1], y: 113 },
    { tier: TIERS[2], y: 181 },
    { tier: TIERS[3], y: 249 },
  ];

  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updateMotionPreference = () => setMotionAllowed(!preference.matches);
    preference.addEventListener('change', updateMotionPreference);
    return () => preference.removeEventListener('change', updateMotionPreference);
  }, []);

  return (
    <div className="deployment-route">
      <div className="deployment-route-heading">
        <span>WORKLOAD ROUTING</span>
        <span>
          {resultSource === 'mock'
            ? 'ILLUSTRATIVE SCORES'
            : hasResult
              ? 'SERVICE SCORES / 100'
              : 'PLACEMENT TIERS / 04'}
        </span>
      </div>
      <div
        className="deployment-route-canvas"
        role="region"
        aria-label="Routing diagram with service scores for each deployment tier"
        tabIndex={0}
      >
        <svg
          viewBox="0 0 520 294"
          role="img"
          aria-label={
            hasResult
              ? `Workload routing and service scores: ${scores.map(([tier, score]) => `${tier}, ${score === null ? 'not provided' : `${score} out of 100`}`).join('; ')}. ${selectedTier ? `${selectedTier} is the recommended tier.` : `The service returned ${recommendation}, which does not match a displayed tier.`}`
              : 'Workload connected to four deployment tiers. Run an analysis to see the service recommendation.'
          }
        >
        <defs>
          <radialGradient id="route-core-glow">
            <stop offset="0" stopColor="#c8b4ff" stopOpacity=".72" />
            <stop offset="1" stopColor="#8769e8" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="route-selected-gradient" x1="0" x2="1">
            <stop offset="0" stopColor="#7abdd2" />
            <stop offset="1" stopColor="#c0a0ff" />
          </linearGradient>
        </defs>
        {destinations.map(({ tier, y }) => {
          const id = `route-${normalizeTierKey(tier)}`;
          const path = `M 118 147 C 220 147, 225 ${y}, 359 ${y}`;
          const selected = hasResult && id === selectedId;
          const score = scores.find(([scoreTier]) => scoreTier === tier)?.[1] ?? null;

          return (
            <g key={tier}>
              <path id={id} className={`route-path ${selected ? 'is-selected' : ''}`} d={path} />
              {selected && (
                <>
                  <path className="route-path route-path-highlight" d={path} />
                  {motionAllowed ? (
                    <circle className="route-packet" r="3.5" aria-hidden="true">
                      <animateMotion dur="5s" repeatCount="indefinite">
                        <mpath href={`#${id}`} />
                      </animateMotion>
                    </circle>
                  ) : (
                    <circle
                      className="route-packet"
                      cx="239"
                      cy={(147 + y) / 2}
                      r="3.5"
                      aria-hidden="true"
                    />
                  )}
                </>
              )}
              <circle
                className={`route-destination ${selected ? 'is-selected' : ''}`}
                cx="359"
                cy={y}
                r={selected ? '8' : '5'}
              />
              {selected && (
                <circle className="route-destination-halo" cx="359" cy={y} r="18" />
              )}
              <text className={`route-label ${selected ? 'is-selected' : ''}`} x="386" y={y - 3}>
                {tier}
              </text>
              <text className={`route-score ${score === null ? 'is-missing' : ''}`} x="386" y={y + 13}>
                {score === null ? 'SCORE NOT PROVIDED' : `SCORE ${score} / 100`}
              </text>
              {score !== null && (
                <>
                  <rect className="route-score-track" x="386" y={y + 19} width="92" height="3" rx="1.5" />
                  <rect
                    className={`route-score-fill ${selected ? 'is-selected' : ''}`}
                    x="386"
                    y={y + 19}
                    width={Math.max(0, Math.min(92, score * 0.92))}
                    height="3"
                    rx="1.5"
                  />
                </>
              )}
              {selected && (
                <text className="route-selected-label" x="386" y={y + 33}>
                  RECOMMENDED
                </text>
              )}
            </g>
          );
        })}
        <circle className="route-core-halo" cx="87" cy="147" r="56" fill="url(#route-core-glow)" />
        <circle className="route-core-ring" cx="87" cy="147" r="31" />
        <circle className="route-core" cx="87" cy="147" r="19" />
        <text className="route-core-title" x="87" y="145" textAnchor="middle">AI</text>
        <text className="route-core-caption" x="87" y="161" textAnchor="middle">WORKLOAD</text>
        {!hasResult && (
          <text className="route-empty-caption" x="258" y="286" textAnchor="middle">
            A ROUTE APPEARS AFTER ANALYSIS
          </text>
        )}
        </svg>
      </div>
      <div className="deployment-route-legend" aria-hidden="true">
        {hasResult ? (
          <span>Suitability scores are returned by the service; they are not benchmark measurements.</span>
        ) : (
          <>
            <span><i /> Workload signal</span>
            <span><i /> Possible tier</span>
          </>
        )}
      </div>
    </div>
  );
}

function InfoCard({ title, items }) {
  const values = Array.isArray(items) && items.length > 0 ? items : [`No ${title.toLowerCase()} returned by the service.`];
  const kind = title.toLowerCase().replace(/[^a-z]+/g, '-');
  const icon = { warnings: '!', 'trade-offs': '↔', assumptions: '⌁' }[kind] ?? '◈';

  return (
    <section className={`info-card info-card-${kind} panel`}>
      <h2>
        <span className="info-card-icon" aria-hidden="true">{icon}</span>
        {title}
      </h2>
      <ul>
        {values.map((item, index) => (
          <li key={`${title}-${index}`}>
            {typeof item === 'string' ? item : JSON.stringify(item)}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Results({
  resultData,
  resultSource,
  reportWorkload,
  simulationData,
  simulating,
  onSimulate,
  onScenarioChange,
  setPath,
  onReport,
  reporting,
}) {
  const baselineLatency = Number(reportWorkload?.latency_requirement_ms ?? 50);
  const [scenarioLatency, setScenarioLatency] = useState(baselineLatency);
  useEffect(() => setScenarioLatency(baselineLatency), [baselineLatency]);
  const hasResult = resultSource !== null;
  const hasLiveResult = resultSource === 'live';
  const result = isRecord(resultData)
    ? resultData
    : {};
  const recommendation =
    result.recommendation || result.recommended_tier || 'Not provided';
  const recommendationLabel = formatTierName(recommendation);
  const estimates = isRecord(result.estimates) ? result.estimates : {};
  const latency = estimates.latency_ms ?? result.latency_estimate_ms;
  const monthlyCost = estimates.monthly_cost ?? estimates.monthly_cost_inr ?? result.monthly_cost;
  const costCurrency =
    estimates.currency ?? result.currency ?? (estimates.monthly_cost_inr != null ? 'INR' : null);
  const monthlyCostLabel =
    monthlyCost == null || monthlyCost === '' || !costCurrency
      ? 'Not provided'
      : costCurrency.toUpperCase() === 'INR'
        ? `₹${monthlyCost}`
        : `${monthlyCost} ${costCurrency.toUpperCase()}`;
  const scores = readScores(result, resultSource === 'mock');
  const resultDetails = isRecord(result.details) ? result.details : {};
  const benchmark = isRecord(resultDetails.benchmark) ? resultDetails.benchmark : null;
  const comparison =
    isRecord(simulationData) && isRecord(simulationData.comparison)
      ? simulationData.comparison
      : null;
  const scoreDeltas = comparison && isRecord(comparison.score_deltas)
    ? comparison.score_deltas
    : {};
  const benchmarkStatusLabel = benchmark?.status
    ? benchmark.status.replaceAll('_', ' ').toUpperCase()
    : hasLiveResult
      ? 'NOT RETURNED'
      : 'NOT REQUESTED';

  return (
    <main className="page results-page">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">
            <span className="eyebrow-dot" aria-hidden="true" />
            PLACEMENT INTELLIGENCE <span className="results-version">/ RESPONSE VIEW</span>
          </p>
          <h1 className="page-title">
            {hasResult ? 'Your deployment route.' : 'Ready when your workload is.'}
          </h1>
          <p className="results-intro">
            {hasResult
              ? 'A clear view of the recommendation and signals returned for this analysis.'
              : 'Run an analysis to see a deployment recommendation from the service.'}
          </p>
        </div>
        <button
          className="button button-outline"
          type="button"
          onClick={() => navigateTo('/analyzer', setPath)}
        >
          Adjust workload <span aria-hidden="true">↻</span>
        </button>
      </div>
      {resultSource === 'mock' && (
        <p className="source-tag">Illustrative mock response · not a live backend recommendation.</p>
      )}
      {!hasResult ? (
        <section className="results-empty panel">
          <span className="results-empty-orbit" aria-hidden="true"><i /></span>
          <div>
            <p className="technical-label">NO ANALYSIS YET</p>
            <h2>Your recommendation will appear here.</h2>
            <p>Nothing is estimated or selected until the recommendation service returns a result.</p>
          </div>
          <button
            className="button button-primary"
            type="button"
            onClick={() => navigateTo('/analyzer', setPath)}
          >
            Analyze a workload <span aria-hidden="true">→</span>
          </button>
        </section>
      ) : (
        <>
          <div className="results-grid">
            <section className="recommendation-card panel">
              <div className="recommendation-heading">
                <div>
                  <p className="technical-label">SERVICE RECOMMENDATION</p>
                  <h2>{recommendationLabel}</h2>
                </div>
                <span className={`recommendation-source ${hasLiveResult ? 'is-live' : 'is-sample'}`}>
                  <i aria-hidden="true" /> {hasLiveResult ? 'LIVE RESPONSE' : 'SAMPLE'}
                </span>
              </div>
              <DeploymentRouteDiagram
                recommendation={recommendation}
                scores={scores}
                hasResult={hasResult}
                resultSource={resultSource}
              />
              <p className="rationale">
                {typeof result.explanation === 'string' && result.explanation
                  ? result.explanation
                  : typeof result.rationale === 'string' && result.rationale
                  ? result.rationale
                  : typeof result.reasoning === 'string' && result.reasoning
                    ? result.reasoning
                    : 'The service did not provide a rationale.'}
              </p>
              <div className="estimate-grid">
                <div>
                  <span>Latency estimate</span>
                  <strong>{latency == null ? 'Not provided' : `${latency} ms`}</strong>
                </div>
                <div>
                  <span>Monthly cost</span>
                  <strong>{monthlyCostLabel}</strong>
                </div>
              </div>
            </section>
          </div>
          <section className="what-if-card panel">
            <div className="what-if-mark" aria-hidden="true">
              <span />
              <i />
            </div>
            <div>
              <p className="technical-label">SCENARIO EXPLORATION</p>
              <h2>What if the latency target changed?</h2>
              <p>
                Recalculate the route with the backend simulator. This is hypothetical; it does not deploy anything.
              </p>
            </div>
            <div className="what-if-controls">
              <label htmlFor="scenario-latency">
                Latency target <strong>{scenarioLatency} ms</strong>
              </label>
              <input
                id="scenario-latency"
                type="range"
                min="1"
                max="1000"
                step="1"
                value={scenarioLatency}
                onChange={(event) => {
                  setScenarioLatency(Number(event.target.value));
                  onScenarioChange();
                }}
                disabled={simulating}
                aria-valuetext={`${scenarioLatency} milliseconds`}
              />
              <button
                className="button button-outline"
                type="button"
                onClick={() => onSimulate({ latency_requirement_ms: scenarioLatency })}
                disabled={!hasLiveResult || simulating || scenarioLatency === baselineLatency}
              >
                {simulating ? 'Simulating…' : 'Simulate what-if'}
              </button>
            </div>
          </section>
          {comparison && (
            <section className="scenario-result panel" aria-live="polite">
              <div className="scenario-result-heading">
                <div>
                  <p className="technical-label">BACKEND SCENARIO RESULT</p>
                  <h2>
                    {comparison.recommendation_changed
                      ? 'The leading tier changed.'
                      : 'The leading tier stayed the same.'}
                  </h2>
                </div>
                <span>
                  {comparison.original_tier
                    ? formatTierName(comparison.original_tier)
                    : 'No feasible tier'}{' '}
                  →{' '}
                  {comparison.new_tier
                    ? formatTierName(comparison.new_tier)
                    : 'No feasible tier'}
                </span>
              </div>
              <p>{comparison.explanation}</p>
              {Object.keys(scoreDeltas).length > 0 && (
                <div className="scenario-score-grid" aria-label="Tier score changes">
                  {Object.entries(scoreDeltas).map(([tier, delta]) => (
                    <div key={tier}>
                      <span>{formatTierName(tier)}</span>
                      <strong>
                        {delta.before} → {delta.after}
                        <small className={delta.delta > 0 ? 'score-up' : delta.delta < 0 ? 'score-down' : ''}>
                          {delta.delta > 0 ? '+' : ''}{delta.delta}
                        </small>
                      </strong>
                    </div>
                  ))}
                </div>
              )}
              {isRecord(comparison.metrics_handling) && (
                <p className="scenario-metrics-note">{comparison.metrics_handling.message}</p>
              )}
              {Array.isArray(comparison.limitations) && comparison.limitations.length > 0 && (
                <ul className="scenario-limitations">
                  {comparison.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
                </ul>
              )}
            </section>
          )}
          <div className="info-grid">
            <InfoCard title="Warnings" items={result.warnings} />
            <InfoCard title="Trade-offs" items={result.tradeoffs} />
            <InfoCard title="Assumptions" items={result.assumptions} />
          </div>
          <div className="result-actions">
            {hasLiveResult && (
              <button
                className="button button-primary"
                type="button"
                onClick={() => onReport(reportWorkload)}
                disabled={reporting}
              >
                {reporting ? 'Preparing PDF…' : 'Download recommendation PDF'}
                {!reporting && <span aria-hidden="true">↓</span>}
              </button>
            )}
          </div>
        </>
      )}
      <aside className="benchmark-status" aria-label="Qualcomm benchmark integration status">
        <span className="benchmark-status-icon" aria-hidden="true">◌</span>
        <span>
          <strong>BENCHMARK CATALOG · {benchmarkStatusLabel}</strong>
          <small>
            {benchmark?.status === 'matched'
              ? `${benchmark.model} on ${benchmark.device}: ${benchmark.inference_latency_ms} ms inference latency (${benchmark.runtime}, ${benchmark.precision}). ${benchmark.note} Source reported by backend: ${benchmark.source_reference}. Provenance is not independently verified.`
              : benchmark?.reason || (hasLiveResult
                ? 'No exact model, device, runtime, and precision match was returned for this workload.'
                : 'Run a live analysis with an optional benchmark profile to check for an exact match.')}
          </small>
        </span>
      </aside>
      <p className="fine-print">
        Benchmark measurements remain distinct from illustrative mock estimates and service-provided heuristic scores.
      </p>
    </main>
  );
}

function ErrorBanner({ message, onDismiss }) {
  if (!message) return null;
  return (
    <div className="error-banner" role="alert">
      <p>{message}</p>
      <button type="button" onClick={onDismiss} aria-label="Dismiss error">
        ×
      </button>
    </div>
  );
}

function Footer({ health, overview }) {
  const status = health === 'online' ? 'BACKEND ONLINE' : health === 'checking' ? 'CHECKING BACKEND' : 'BACKEND UNAVAILABLE';
  return (
    <footer className={`site-footer ${overview ? 'overview-footer' : ''}`}>
      <span>◉ EdgePilot AI / intelligent placement control plane</span>
      <span>
        <i className={`footer-dot ${health}`} aria-hidden="true" />
        {status} · {overview ? 'V0.9.0' : 'v1.0.0'}
      </span>
    </footer>
  );
}

function App() {
  const [path, setPath] = useState(() => {
    const currentPath = window.location.pathname;
    return ROUTES.some(([route]) => route === currentPath) ? currentPath : '/';
  });
  const [mockMode, setMockMode] = useState(false);
  const [health, setHealth] = useState('checking');
  const [workload, setWorkload] = useState(INITIAL_WORKLOAD);
  const [resultData, setResultData] = useState(null);
  const [reportWorkload, setReportWorkload] = useState(null);
  const [simulationData, setSimulationData] = useState(null);
  const [resultSource, setResultSource] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [error, setError] = useState('');
  const [clickRipples, setClickRipples] = useState([]);
  const rippleId = useRef(0);

  function createClickRipple(event, keyboardActivation = false) {
    const target = event.target instanceof Element ? event.target : null;
    const control = target?.closest(
      'button, a, input, select, textarea, summary, [role="button"], [role="link"]',
    );
    if (!control || control.matches(':disabled')) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const bounds = control.getBoundingClientRect();
    const id = rippleId.current++;
    setClickRipples((current) => [
      ...current,
      {
        id,
        x: keyboardActivation ? bounds.left + bounds.width / 2 : event.clientX,
        y: keyboardActivation ? bounds.top + bounds.height / 2 : event.clientY,
      },
    ]);
  }

  useEffect(() => {
    if (!ROUTES.some(([route]) => route === window.location.pathname)) {
      window.history.replaceState({}, '', '/');
    }

    function handlePopState() {
      const nextPath = window.location.pathname;
      const validPath = ROUTES.some(([route]) => route === nextPath);
      if (!validPath) window.history.replaceState({}, '', '/');
      setPath(validPath ? nextPath : '/');
      if (activeLenis) {
        activeLenis.scrollTo(0, { immediate: true });
      } else {
        window.scrollTo({ top: 0, behavior: 'auto' });
      }
    }
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    if (path !== '/') return undefined;
    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
    let lenis = null;
    let gsapInstance = null;
    let ScrollTriggerPlugin = null;
    const updateScroll = () => ScrollTriggerPlugin?.update();
    const tick = (time) => lenis?.raf(time * 1000);
    const stop = () => {
      if (!lenis) return;
      lenis.off('scroll', updateScroll);
      gsapInstance.ticker.remove(tick);
      lenis.destroy();
      if (activeLenis === lenis) activeLenis = null;
      lenis = null;
    };
    let generation = 0;
    const start = async () => {
      if (motionPreference.matches || lenis) return;
      const currentGeneration = ++generation;
      const [lenisModule, gsapModule, scrollTriggerModule] = await Promise.all([
        import('lenis'),
        import('gsap'),
        import('gsap/ScrollTrigger'),
      ]);
      if (currentGeneration !== generation || motionPreference.matches) return;
      const Lenis = lenisModule.default;
      gsapInstance = gsapModule.default;
      ScrollTriggerPlugin = scrollTriggerModule.ScrollTrigger;
      gsapInstance.registerPlugin(ScrollTriggerPlugin);
      lenis = new Lenis({ autoRaf: false, anchors: true });
      activeLenis = lenis;
      lenis.on('scroll', updateScroll);
      gsapInstance.ticker.add(tick);
      gsapInstance.ticker.lagSmoothing(0);
    };
    const syncMotionPreference = () => {
      if (motionPreference.matches) {
        generation += 1;
        stop();
      }
      else start();
    };

    start();
    motionPreference.addEventListener('change', syncMotionPreference);
    return () => {
      motionPreference.removeEventListener('change', syncMotionPreference);
      generation += 1;
      stop();
    };
  }, [path]);

  useLayoutEffect(() => {
    document.querySelectorAll('.app-shell main h1, .app-shell main h2, .app-shell main h3').forEach((heading) => {
      if (heading.classList.contains('dot-grid-title')) return;
      heading.querySelector('.heading-grid-overlay')?.remove();
      const overlay = document.createElement('span');
      overlay.className = 'heading-grid-overlay';
      overlay.setAttribute('aria-hidden', 'true');
      overlay.textContent = heading.innerText.trim();
      heading.append(overlay);
    });
  }, [path, resultData]);

  useEffect(() => {
    if (path !== '/') return undefined;
    const overview = document.querySelector('.overview-page');
    if (!overview) return undefined;

    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
    let context = null;
    let generation = 0;
    const clear = () => {
      generation += 1;
      context?.revert();
      context = null;
      overview.style.removeProperty('--story-progress');
    };
    const animate = async () => {
      if (motionPreference.matches || context) return;
      const currentGeneration = ++generation;
      const [gsapModule, scrollTriggerModule] = await Promise.all([
        import('gsap'),
        import('gsap/ScrollTrigger'),
      ]);
      if (currentGeneration !== generation || motionPreference.matches) return;
      const gsap = gsapModule.default;
      const ScrollTrigger = scrollTriggerModule.ScrollTrigger;
      gsap.registerPlugin(ScrollTrigger);
      context = gsap.context(() => {
        const transitions = [
          { section: '.deployment-section', outgoing: '.overview-hero', incoming: '.deployment-visual' },
          { section: '.signals-section', outgoing: '.deployment-visual', incoming: '.signal-graph-wrap' },
          { section: '.placement-loop', outgoing: '.signal-graph-wrap', incoming: '.loop-diagram' },
        ];

        transitions.forEach(({ section, outgoing, incoming }) => {
          const trigger = overview.querySelector(section);
          const from = overview.querySelector(outgoing);
          const to = overview.querySelector(incoming);
          if (!trigger || !from || !to) return;

          gsap.fromTo(
            from,
            { autoAlpha: 1, y: 0, scale: 1, filter: 'blur(0px)' },
            {
              autoAlpha: 0.38,
              y: -28,
              scale: 0.97,
              filter: 'blur(5px)',
              ease: 'none',
              scrollTrigger: {
                trigger,
                start: 'top 92%',
                end: 'top 30%',
                scrub: 0.8,
              },
            },
          );
          gsap.fromTo(
            to,
            { autoAlpha: 0.58, y: 34, scale: 0.97, filter: 'blur(5px)' },
            {
              autoAlpha: 1,
              y: 0,
              scale: 1,
              filter: 'blur(0px)',
              ease: 'none',
              scrollTrigger: {
                trigger,
                start: 'top 92%',
                end: 'top 30%',
                scrub: 0.8,
              },
            },
          );
        });
        ScrollTrigger.create({
          trigger: overview,
          start: 'top top',
          end: 'bottom bottom',
          onUpdate: (self) => overview.style.setProperty('--story-progress', self.progress),
        });
      }, overview);
      ScrollTrigger.refresh();
    };
    const syncMotionPreference = () => {
      if (motionPreference.matches) clear();
      else animate();
    };

    animate();
    motionPreference.addEventListener('change', syncMotionPreference);
    return () => {
      motionPreference.removeEventListener('change', syncMotionPreference);
      clear();
    };
  }, [path]);

  useEffect(() => {
    const controller = new AbortController();
    checkBackendHealth(controller.signal)
      .then(() => setHealth('online'))
      .catch((requestError) => {
        if (requestError.name !== 'AbortError') setHealth('offline');
      });
    return () => controller.abort();
  }, []);

  async function analyze(request) {
    setAnalyzing(true);
    setError('');
    setResultData(null);
    setReportWorkload(null);
    setSimulationData(null);
    setResultSource(null);
    try {
      if (mockMode) {
        setResultData(MOCK_RECOMMENDATION);
        setResultSource('mock');
      } else {
        const responseData = await getRecommendation(request);
        setResultData(responseData);
        setReportWorkload(request);
        setSimulationData(null);
        setResultSource('live');
      }
      navigateTo('/results', setPath);
    } catch (requestError) {
      const detail =
        requestError instanceof Error && requestError.message
          ? requestError.message
          : 'The request failed.';
      setError(
        `Unable to reach the recommendation service. ${detail} Check the backend/tunnel and CORS configuration, or enable mock mode for a labeled demo.`,
      );
    } finally {
      setAnalyzing(false);
    }
  }

  async function simulate(changes) {
    if (!reportWorkload || mockMode) return;
    setSimulating(true);
    setError('');
    setSimulationData(null);
    try {
      const responseData = await simulateWorkload(reportWorkload, changes);
      setSimulationData(responseData);
    } catch (requestError) {
      const detail =
        requestError instanceof Error && requestError.message
          ? requestError.message
          : 'The scenario request failed.';
      setError(`Unable to simulate this workload. ${detail}`);
    } finally {
      setSimulating(false);
    }
  }

  async function downloadReport(workload) {
    setReporting(true);
    setError('');
    try {
      const blob = await getRecommendationReport(workload);
      if (blob.size === 0) throw new Error('The report service returned an empty PDF.');

      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'EdgePilot_Recommendation_Report.pdf';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (requestError) {
      const detail =
        requestError instanceof Error && requestError.message
          ? requestError.message
          : 'The PDF could not be downloaded.';
      setError(
        `Unable to prepare the recommendation PDF. ${detail} Check the backend/tunnel and CORS configuration.`,
      );
    } finally {
      setReporting(false);
    }
  }

  let page;
  if (path === '/analyzer') {
    page = (
      <Analyzer
        workload={workload}
        setWorkload={setWorkload}
        onAnalyze={analyze}
        busy={analyzing}
      />
    );
  } else if (path === '/results') {
    page = (
      <Results
        resultData={resultData}
        resultSource={resultSource}
        reportWorkload={reportWorkload}
        simulationData={simulationData}
        simulating={simulating}
        onSimulate={simulate}
        onScenarioChange={() => setSimulationData(null)}
        setPath={setPath}
        onReport={downloadReport}
        reporting={reporting}
      />
    );
  } else {
    page = <Overview setPath={setPath} />;
  }

  return (
    <div
      className="app-shell"
      onPointerDownCapture={(event) => createClickRipple(event)}
      onClickCapture={(event) => {
        if (event.detail === 0) createClickRipple(event, true);
      }}
    >
      <Header
        path={path}
        setPath={setPath}
        mockMode={mockMode}
        setMockMode={setMockMode}
        health={health}
      />
      {mockMode && <DemoNotice />}
      <ErrorBanner message={error} onDismiss={() => setError('')} />
      {page}
      <Footer health={health} overview={path === '/'} />
      <div className="click-ripple-layer" aria-hidden="true">
        {clickRipples.map((ripple) => (
          <span
            className="click-ripple"
            key={ripple.id}
            style={{ left: ripple.x, top: ripple.y }}
            onAnimationEnd={() =>
              setClickRipples((current) => current.filter((item) => item.id !== ripple.id))
            }
          />
        ))}
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
