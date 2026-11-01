jest.mock('pdfkit', () => class MockPDFDocument {
  constructor() {
    this.page = { width: 595 };
    this.textValues = [];
    global.reportDocument = this;
  }

  pipe() { return this; }
  rect() { return this; }
  fill() { return this; }
  fillAndStroke() { return this; }
  fillColor() { return this; }
  fontSize() { return this; }
  font() { return this; }
  text(value) {
    this.textValues.push(value);
    return this;
  }
  heightOfString(value) {
    return Math.max(12, Math.ceil(String(value).length / 90) * 10);
  }
  end() { return this; }
});

const { generatePdfReport } = require('../services/reportService');

describe('PDF report metric rendering', () => {
  afterEach(() => {
    delete global.reportDocument;
  });

  test('renders missing latency and cost as not available instead of zero', () => {
    const response = { setHeader: jest.fn() };

    generatePdfReport({
      recommended_tier: 'on_device',
      metrics_by_tier: {}
    }, response);

    expect(global.reportDocument.textValues).toContain(
      '• End-to-End Latency: Not available'
    );
    expect(global.reportDocument.textValues).toContain(
      '• Estimated Monthly Operating Cost: Not available'
    );
    expect(global.reportDocument.textValues).toContain('Not available');
    expect(global.reportDocument.textValues).toContain(
      'No workload-matched latency or cost evidence was supplied. These values are left unavailable rather than guessed.'
    );
    expect(global.reportDocument.textValues).not.toContain('INR 0');
  });

  test('reports when no tier passes the supplied latency and budget limits', () => {
    const response = { setHeader: jest.fn() };

    generatePdfReport({
      recommended_tier: null,
      scores: { on_device: 0, far_edge: 20, regional_edge: 10, cloud: 40 },
      workload: { latency_target: 200, budget: 200, privacy: 'low', criticality: 'high' },
      metrics_by_tier: {}
    }, response);

    const renderedText = global.reportDocument.textValues.map(String).join('\n');
    expect(renderedText).toContain('NO FEASIBLE TIER');
    expect(renderedText).toContain('Latency target: 200 ms');
    expect(renderedText).toContain('Budget: 200 INR/month');
    expect(renderedText).toContain('Privacy: low');
    expect(renderedText).toContain('Criticality: high');
  });

  test('preserves a real zero cost rather than treating it as missing', () => {
    const response = { setHeader: jest.fn() };

    generatePdfReport({
      recommended_tier: 'on_device',
      metrics_by_tier: {
        on_device: {
          latency_ms: { value: 0 },
          monthly_cost_inr: { value: 0 }
        }
      }
    }, response);

    expect(global.reportDocument.textValues).toContain(
      '• End-to-End Latency: 0 ms'
    );
    expect(global.reportDocument.textValues).toContain(
      '• Estimated Monthly Operating Cost: INR 0 / month'
    );
  });

  test('includes submitted workload, recommendation scores, and rationale', () => {
    const response = { setHeader: jest.fn() };

    generatePdfReport({
      recommended_tier: 'on_device',
      workload: {
        model_name: 'mobilenet_v2',
        target_device: 'Galaxy S25',
        latency_requirement_ms: 0,
        budget_monthly: 1000,
        bandwidth_requirement: 'medium',
        privacy_requirement: 'high',
        criticality: 'high'
      },
      scores: {
        on_device: 80,
        far_edge: 60,
        regional_edge: 70,
        cloud: 50
      },
      explanation: 'On-device is the top-scoring feasible tier.'
    }, response);

    expect(global.reportDocument.textValues).toContain('Model: mobilenet_v2');
    expect(global.reportDocument.textValues).toContain('Device: Galaxy S25');
    expect(global.reportDocument.textValues).toContain('Latency target: 0 ms');
    expect(global.reportDocument.textValues).toContain('Budget: 1,000 INR/month');
    expect(global.reportDocument.textValues).toContain(
      'Suitability scores / 100: on device: 80 | far edge: 60 | regional edge: 70 | cloud: 50'
    );
    expect(global.reportDocument.textValues).toContain('On-device is the top-scoring feasible tier.');
  });

  test('prints only provided workload values and omits missing-input warnings', () => {
    const response = { setHeader: jest.fn() };

    generatePdfReport({
      recommended_tier: 'on_device',
      workload: {
        application_type: 'smart_camera',
        latency_target: 0,
        budget: 1000,
        runtime: 'tflite',
        model_name: 'mobilenet_v2',
        throughput: null,
        bandwidth: 'medium',
        precision: 'float',
        target_device: 'Galaxy S25',
        device_ram: 'Not provided'
      },
      metrics_by_tier: {}
    }, response);

    const renderedText = global.reportDocument.textValues.map(String).join('\n');
    expect(renderedText).toContain('Application: smart_camera');
    expect(renderedText).toContain('Latency target: 0 ms');
    expect(renderedText).toContain('Budget: 1,000 INR/month');
    expect(renderedText).toContain('Device: Galaxy S25');
    expect(renderedText).not.toContain('Throughput:');
    expect(renderedText).not.toContain('Device RAM:');
    expect(renderedText).not.toContain('Recommendation inputs not provided');
  });

  test('preserves the dynamic recommendation rationale', () => {
    const response = { setHeader: jest.fn() };

    generatePdfReport({
      recommended_tier: 'on_device',
      explanation: 'On-device ranks first with a provisional, uncalibrated suitability score.',
      metrics_by_tier: {}
    }, response);

    expect(global.reportDocument.textValues).toContain(
      'On-device ranks first with a provisional, uncalibrated suitability score.'
    );
    expect(global.reportDocument.textValues).not.toContain(
      'On-device ranks first with an optimal suitability score of 86.2/100.'
    );
  });

  test('uses recommendation estimates when tier metrics are not included', () => {
    const response = { setHeader: jest.fn() };

    generatePdfReport({
      recommended_tier: 'regional-edge',
      estimates: {
        latency_ms: 42,
        monthly_cost: 1800
      },
      details: {
        tier_estimates: {
          regional_edge: {
            latency_ms: 42,
            latency_source: 'estimated',
            monthly_cost_inr: 1800,
            cost_source: 'estimated'
          }
        }
      }
    }, response);

    expect(global.reportDocument.textValues).toContain('REGIONAL EDGE');
    expect(global.reportDocument.textValues).toContain('• End-to-End Latency: 42 ms');
    expect(global.reportDocument.textValues).toContain(
      '• Estimated Monthly Operating Cost: INR 1,800 / month'
    );
    expect(global.reportDocument.textValues).toContain('42 ms');
    expect(global.reportDocument.textValues).toContain('INR 1,800');
    expect(global.reportDocument.textValues.some((value) =>
      String(value).includes('latency estimated; cost estimated')
    )).toBe(true);
    expect(global.reportDocument.textValues).not.toContain(
      'No workload-matched latency or cost evidence was supplied. These values are left unavailable rather than guessed.'
    );
  });

  test('labels metric evidence and checks each tier against workload limits', () => {
    const response = { setHeader: jest.fn() };

    generatePdfReport({
      recommended_tier: 'on_device',
      workload: {
        latency_target: 50,
        budget: 1000,
        privacy: 'low',
        criticality: 'high'
      },
      scores: { on_device: 86.2 },
      metrics_by_tier: {
        on_device: {
          latency_ms: {
            value: 15,
            source: 'estimated',
            source_reference: 'Illustrative profile',
            assumptions: ['Representative workload has not been benchmarked.']
          },
          monthly_cost_inr: {
            value: 900,
            source: 'estimated',
            source_reference: 'Illustrative monthly cost',
            assumptions: ['Pricing is not a provider quote.']
          }
        },
        cloud: {
          latency_ms: { value: 120, source: 'measured', source_reference: 'Load test' },
          monthly_cost_inr: { value: 1200, source: 'estimated', source_reference: 'Cost estimate' }
        }
      }
    }, response);

    expect(global.reportDocument.textValues).toContain('Lat PASS\nCost PASS');
    expect(global.reportDocument.textValues).toContain('Lat FAIL\nCost FAIL');
    expect(global.reportDocument.textValues).toContain('Privacy: low');
    expect(global.reportDocument.textValues).toContain('Criticality: high');
    expect(global.reportDocument.textValues).toContain(
      'Scores are ranking indicators, not benchmark measurements, probabilities, or deployment guarantees.'
    );
    expect(global.reportDocument.textValues.some((value) =>
      String(value).includes('Selected-tier source type: latency estimated; cost estimated.')
    )).toBe(true);
    expect(global.reportDocument.textValues.some((value) =>
      String(value).includes('Recommendation inputs not provided')
    )).toBe(false);
    expect(global.reportDocument.textValues.some((value) =>
      String(value).includes('Representative workload has not been benchmarked.')
    )).toBe(true);
    expect(global.reportDocument.textValues.some((value) =>
      String(value).includes('Limitations: Estimated figures are provisional')
    )).toBe(true);
  });
});
