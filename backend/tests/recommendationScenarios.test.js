jest.mock('pdfkit', () => class MockPDFDocument {
  constructor() {
    this.page = { width: 595 };
    this.textValues = [];
    global.scenarioReportDocument = this;
  }

  pipe() { return this; }
  rect() { return this; }
  fill() { return this; }
  fillAndStroke() { return this; }
  fillColor() { return this; }
  fontSize() { return this; }
  font() { return this; }
  text(value) {
    this.textValues.push(String(value));
    return this;
  }
  heightOfString(value) {
    return Math.max(12, Math.ceil(String(value).length / 90) * 10);
  }
  addPage() { return this; }
  end() { return this; }
});

const { calculateSuitability } = require('../services/suitabilityService');
const { generatePdfReport } = require('../services/reportService');

const scenarios = {
  onDevicePreferred: {
    target_device: 'Samsung Galaxy S25 (Family)',
    runtime: 'tflite',
    latency_target: 50,
    budget: 1000,
    privacy: 'high',
    criticality: 'high',
    bandwidth_requirement: 'medium'
  },
  cloudTierFlip: {
    target_device: 'Samsung Galaxy S25 (Family)',
    runtime: 'tflite',
    latency_target: 200,
    budget: 200,
    privacy: 'low',
    criticality: 'low',
    bandwidth_requirement: 'medium'
  },
  impossibleSla: {
    latency_target: 5,
    budget: 50,
    privacy: 'low',
    criticality: 'low',
    bandwidth_requirement: 'medium'
  },
  optionalInputsOmitted: {
    latency_target: 100,
    budget: 500,
    privacy: 'medium',
    criticality: 'medium',
    bandwidth_requirement: 'medium'
  }
};

async function evaluateScenario(name, workload) {
  const result = await calculateSuitability(workload);
  global.scenarioReportDocument = undefined;
  generatePdfReport(result, { setHeader: jest.fn() });
  const reportText = global.scenarioReportDocument.textValues;
  const output = {
    inputs: workload,
    scores: result.scores,
    sla: result.details.sla_checks,
    recommended_tier: result.recommended_tier,
    rationale: result.explanation,
    warnings: result.warnings
  };

  console.log(`[${name}] ${JSON.stringify(output, null, 2)}`);
  return { result, reportText };
}

function getTierSla(reportText, tierName) {
  const tierIndex = reportText.findIndex((text) => text === tierName);
  if (tierIndex === -1) return null;
  return reportText.slice(tierIndex + 1).find((text) => text.startsWith('Lat ')) || null;
}

describe('EdgePilot recommendation and report scenarios', () => {
  afterEach(() => {
    delete global.scenarioReportDocument;
  });

  test('Scenario 1: On-Device preferred when local latency, cost and privacy fit', async () => {
    const { result, reportText } = await evaluateScenario(
      'Scenario 1: On-Device Preferred',
      scenarios.onDevicePreferred
    );

    expect({
      recommended_tier: result.recommended_tier,
      on_device_sla: getTierSla(reportText, 'ON DEVICE'),
      rationale_mentions_local_latency_and_privacy:
        /latency.*privacy.*local execution/i.test(result.explanation)
    }).toEqual({
      recommended_tier: 'on_device',
      on_device_sla: 'Lat PROVISIONAL PASS\nCost PROVISIONAL PASS',
      rationale_mentions_local_latency_and_privacy: true
    });
  });

  test('Scenario 2: relaxed constraints allow the requested Cloud/Far Edge tier flip', async () => {
    const { result, reportText } = await evaluateScenario(
      'Scenario 2: Cloud Tier Flip',
      scenarios.cloudTierFlip
    );

    const selectedTier = result.recommended_tier === 'cloud'
      ? 'CLOUD'
      : result.recommended_tier === 'far_edge'
        ? 'FAR EDGE'
        : null;
    expect({
      recommended_tier_is_cloud_or_far_edge: ['cloud', 'far_edge'].includes(result.recommended_tier),
      on_device_sla: getTierSla(reportText, 'ON DEVICE'),
      selected_tier_sla: selectedTier ? getTierSla(reportText, selectedTier) : null,
      rationale_mentions_cost_latency_privacy:
        /lower.*cost.*relaxed latency.*privacy/i.test(result.explanation)
    }).toEqual({
      recommended_tier_is_cloud_or_far_edge: true,
      on_device_sla: 'Lat PROVISIONAL PASS\nCost PROVISIONAL FAIL',
      selected_tier_sla: 'Lat PROVISIONAL PASS\nCost PROVISIONAL FAIL',
      rationale_mentions_cost_latency_privacy: true
    });
  });

  test('Scenario 3: estimated SLA violations are labeled provisional, not verified failures', async () => {
    const { result, reportText } = await evaluateScenario(
      'Scenario 3: Impossible SLAs',
      scenarios.impossibleSla
    );

    expect({
      all_tiers_show_provisional_failures:
        reportText.filter((text) => text.includes('Lat PROVISIONAL FAIL\nCost PROVISIONAL FAIL')).length === 4,
      provisional_recommendation_selected:
        result.recommended_tier !== null && result.details.status === 'provisional_sla_failure',
      provisional_warning_present:
        result.warnings.some((warning) => warning.includes('estimated SLA overrun'))
    }).toEqual({
      all_tiers_show_provisional_failures: true,
      provisional_recommendation_selected: true,
      provisional_warning_present: true
    });
  });

  test('Scenario 4: optional workload fields are omitted from the specifications block', async () => {
    const { result, reportText } = await evaluateScenario(
      'Scenario 4: Optional Inputs Omitted',
      scenarios.optionalInputsOmitted
    );

    const headingIndex = reportText.indexOf('WORKLOAD SPECIFICATIONS');
    const nextHeadingIndex = reportText.indexOf('RECOMMENDED DEPLOYMENT TIER', headingIndex);
    const workloadBlock = reportText.slice(headingIndex + 1, nextHeadingIndex).join('\n');

    expect(headingIndex).toBeGreaterThanOrEqual(0);
    expect(workloadBlock).not.toMatch(/Throughput|Device RAM|Not provided|Not available/i);
  });
});
