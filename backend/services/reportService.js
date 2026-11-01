// services/reportService.js
const PDFDocument = require('pdfkit');

function getMetricValue(metric) {
  const value = metric && typeof metric === 'object' ? metric.value : metric;
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function formatMetric(value) {
  return value === null ? 'Not available' : value.toLocaleString('en-IN');
}

function normalizeTierKey(value) {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function isValidWorkloadValue(value) {
  if (typeof value === 'number') return Number.isFinite(value);
  if (typeof value === 'string') {
    return value.trim() !== ''
      && !['not provided', 'undefined', 'null', 'n/a'].includes(value.trim().toLowerCase());
  }
  return typeof value === 'boolean';
}

function formatWorkloadValue(value, suffix = '') {
  const formattedValue = typeof value === 'number' ? formatMetric(value) : String(value);
  return `${formattedValue}${suffix}`;
}

function resolveWorkloadValue(workload, ...keys) {
  for (const key of keys) {
    if (isValidWorkloadValue(workload[key])) return workload[key];
  }
  return null;
}

function getEvidenceLabel(metric, fallback) {
  const source = metric && typeof metric === 'object'
    ? metric.source || fallback
    : fallback;
  return typeof source === 'string' && source.trim()
    ? source.trim().toLowerCase()
    : 'not provided';
}

function getSourceReference(metric) {
  if (!metric || typeof metric !== 'object') return 'No source reference';
  return metric.source_reference || metric.method || 'No source reference';
}

function checkConstraint(value, limit) {
  if (value === null || typeof limit !== 'number' || !Number.isFinite(limit)) return 'N/A';
  return value <= limit ? 'PASS' : 'FAIL';
}

function formatSlaStatus(status, value, limit) {
  const labels = {
    pass: 'PASS',
    provisional_pass: 'PROVISIONAL PASS',
    provisional_fail: 'PROVISIONAL FAIL',
    fail: 'FAIL',
    unknown: 'N/A'
  };
  return labels[status] || checkConstraint(value, limit);
}

function truncateSource(value) {
  const source = String(value);
  return source.length > 39 ? `${source.slice(0, 36)}...` : source;
}

function generatePdfReport(data, res) {
  const doc = new PDFDocument({ margin: 35, size: 'A4' });

  res.setHeader('Content-Type', 'application/pdf');
  res.setHeader('Content-Disposition', 'attachment; filename="EdgePilot_Architecture_Report.pdf"');

  doc.pipe(res);

  // --- HEADER BAND ---
  doc.rect(0, 0, doc.page.width, 65).fill('#0F172A');

  doc.fillColor('#FFFFFF')
     .fontSize(18)
     .font('Helvetica-Bold')
     .text('EdgePilot Architecture & Metric Report', 35, 18);

  const genDate = new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
  doc.fontSize(8)
     .font('Helvetica')
     .fillColor('#94A3B8')
     .text(`Generated on: ${genDate} | Recommendation report`, 35, 42);

  // --- WORKLOAD SPECIFICATIONS ---
  const workload = data.workload || {};
  const workloadEntries = [
    { label: 'Application', value: workload.application_type },
    { label: 'Latency target', value: resolveWorkloadValue(workload, 'latency_target', 'latency_requirement_ms'), suffix: ' ms' },
    { label: 'Budget', value: resolveWorkloadValue(workload, 'budget', 'budget_monthly'), suffix: ' INR/month' },
    { label: 'Privacy', value: resolveWorkloadValue(workload, 'privacy', 'privacy_requirement') },
    { label: 'Criticality', value: workload.criticality },
    { label: 'Runtime', value: workload.runtime },
    { label: 'Model', value: workload.model_name },
    { label: 'Throughput', value: resolveWorkloadValue(workload, 'throughput', 'expected_qps'), suffix: ' QPS' },
    { label: 'Bandwidth', value: resolveWorkloadValue(workload, 'bandwidth', 'bandwidth_requirement') },
    { label: 'Precision', value: workload.precision },
    { label: 'Device', value: workload.target_device },
    { label: 'Device RAM', value: resolveWorkloadValue(workload, 'device_ram', 'device_available_ram_mb'), suffix: ' MB' }
  ].filter((entry) => isValidWorkloadValue(entry.value));
  const workloadColumns = 3;
  const workloadColumnWidth = 165;
  const workloadRowGap = 4;
  const workloadRows = [];
  doc.font('Helvetica').fontSize(8);
  for (let index = 0; index < workloadEntries.length; index += workloadColumns) {
    const rowEntries = workloadEntries.slice(index, index + workloadColumns).map((entry) => ({
      ...entry,
      text: `${entry.label}: ${formatWorkloadValue(entry.value, entry.suffix)}`
    }));
    const rowHeight = Math.max(
      12,
      ...rowEntries.map((entry) =>
        doc.heightOfString(entry.text, { width: workloadColumnWidth, font: 'Helvetica', fontSize: 8 })
      )
    );
    workloadRows.push({ entries: rowEntries, height: rowHeight });
  }
  const workloadRowsHeight = workloadRows.reduce((total, row) => total + row.height + workloadRowGap, 0);
  const workloadCardHeight = Math.max(50, 33 + workloadRowsHeight);
  doc.rect(35, 75, 525, workloadCardHeight).fillAndStroke('#F8FAFC', '#CBD5E1');
  doc.fillColor('#0F172A').fontSize(9).font('Helvetica-Bold').text('WORKLOAD SPECIFICATIONS', 45, 82);
  doc.fontSize(8).font('Helvetica').fillColor('#334155');
  let workloadY = 98;
  workloadRows.forEach((row) => {
    row.entries.forEach((entry, column) => {
      doc.text(entry.text, 45 + column * 175, workloadY, { width: workloadColumnWidth });
    });
    workloadY += row.height + workloadRowGap;
  });
  const layoutShift = workloadCardHeight - 82;

  // --- RECOMMENDED TIER BANNER ---
  const recTier = data.recommended_tier
    ? String(data.recommended_tier).replace(/[_-]+/g, ' ').toUpperCase()
    : Object.prototype.hasOwnProperty.call(data, 'recommended_tier')
      ? 'NO FEASIBLE TIER'
      : 'NOT PROVIDED';
  doc.rect(35, 167 + layoutShift, 525, 40).fill('#1E40AF');

  doc.fillColor('#FFFFFF').fontSize(8).font('Helvetica-Bold').text('RECOMMENDED DEPLOYMENT TIER', 45, 174 + layoutShift);
  doc.fontSize(14).font('Helvetica-Bold').text(recTier, 45, 186 + layoutShift);

  // --- SECTION 1: STAGE 3 SUMMARY ---
  doc.fillColor('#0F172A').fontSize(11).font('Helvetica-Bold').text('1. Infrastructure Economics & Grounding Summary', 35, 222 + layoutShift);
  doc.rect(35, 235 + layoutShift, 525, 1).fill('#CBD5E1');

  const metrics = data.metrics_by_tier || {};
  const tierEstimates = data.details && data.details.tier_estimates
    ? data.details.tier_estimates
    : {};
  const recKey = normalizeTierKey(data.recommended_tier);
  const recData = metrics[recKey] || {};
  const recEstimate = tierEstimates[recKey] || {};
  const recommendationEstimates = data.estimates || {};

  const recLat = getMetricValue(recData.latency_ms)
    ?? getMetricValue(recEstimate.latency_ms)
    ?? getMetricValue(recommendationEstimates.latency_ms);
  const recCost = getMetricValue(recData.monthly_cost_inr)
    ?? getMetricValue(recEstimate.monthly_cost_inr)
    ?? getMetricValue(recommendationEstimates.monthly_cost_inr)
    ?? getMetricValue(recommendationEstimates.monthly_cost);
  const recLatencyEvidence = getEvidenceLabel(
    recData.latency_ms,
    recEstimate.latency_source || recommendationEstimates.latency_source
  );
  const recCostEvidence = getEvidenceLabel(
    recData.monthly_cost_inr,
    recEstimate.cost_source || recommendationEstimates.cost_source
  );

  doc.fillColor('#334155').fontSize(9).font('Helvetica');
  doc.text(`• End-to-End Latency: ${formatMetric(recLat)}${recLat === null ? '' : ' ms'}`, 45, 244 + layoutShift);
  doc.text(`• Estimated Monthly Operating Cost: ${recCost === null ? 'Not available' : `INR ${formatMetric(recCost)} / month`}`, 45, 258 + layoutShift);
  const scores = data.scores || {};
  const scoreSummary = ['on_device', 'far_edge', 'regional_edge', 'cloud']
    .map((tier) => {
      const score = scores[tier] ?? scores[tier.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())];
      return `${tier.replace(/_/g, ' ')}: ${typeof score === 'number' && Number.isFinite(score) ? score : 'Not provided'}`;
    })
    .join(' | ');
  doc.text(`Suitability scores / 100: ${scoreSummary}`, 45, 272 + layoutShift, { width: 505 });
  doc.fontSize(7).fillColor('#64748B')
    .text('Scores are ranking indicators, not benchmark measurements, probabilities, or deployment guarantees.', 45, 282 + layoutShift, { width: 505 });

  // --- SECTION 2: STAGE 3 METRIC PROVENANCE TABLE ---
  doc.fillColor('#0F172A').fontSize(11).font('Helvetica-Bold').text('2. Tier Comparison: Latency, Cost & Evidence', 35, 300 + layoutShift);
  doc.rect(35, 313 + layoutShift, 525, 1).fill('#CBD5E1');

  let yPos = 320 + layoutShift;

  // Header Row
  doc.rect(35, yPos, 525, 20).fill('#E2E8F0');
  doc.fillColor('#0F172A').fontSize(8).font('Helvetica-Bold');
  doc.text('TIER', 42, yPos + 6);
  doc.text('LATENCY', 112, yPos + 6);
  doc.text('COST / MO.', 170, yPos + 6);
  doc.text('LATENCY EVIDENCE', 250, yPos + 6);
  doc.text('COST EVIDENCE', 363, yPos + 6);
  doc.text('SLA / BUDGET', 478, yPos + 6);

  yPos += 20;

  const tiers = ['on_device', 'far_edge', 'regional_edge', 'cloud'];
  const latencyTargetValue = resolveWorkloadValue(workload, 'latency_target', 'latency_requirement_ms');
  const latencyTarget = typeof latencyTargetValue === 'number' && Number.isFinite(latencyTargetValue)
    ? latencyTargetValue
    : null;
  const budgetValue = resolveWorkloadValue(workload, 'budget', 'budget_monthly');
  const monthlyBudget = typeof budgetValue === 'number' && Number.isFinite(budgetValue)
    ? budgetValue
    : null;

  tiers.forEach((tKey) => {
    const tData = metrics[tKey] || {};
    const estimate = tierEstimates[tKey] || {};

    const latObj = tData.latency_ms;
    const latValue = getMetricValue(latObj) ?? getMetricValue(estimate.latency_ms);
    const latVal = formatMetric(latValue);
    const latSrc = latObj && typeof latObj === 'object'
      ? getSourceReference(latObj)
      : 'No source reference';

    const costObj = tData.monthly_cost_inr;
    const costValue = getMetricValue(costObj) ?? getMetricValue(estimate.monthly_cost_inr);
    const costSource = costObj && typeof costObj === 'object'
      ? getSourceReference(costObj)
      : 'No source reference';
    const latencyEvidence = getEvidenceLabel(latObj, estimate.latency_source);
    const costEvidence = getEvidenceLabel(costObj, estimate.cost_source);
    const slaCheck = data.details && data.details.sla_checks
      ? data.details.sla_checks[tKey]
      : null;
    const rowHeight = 34;

    const isSelected = tKey === recKey;
    doc.rect(35, yPos, 525, rowHeight).fill(isSelected ? '#DBEAFE' : (yPos % 2 === 0 ? '#FFFFFF' : '#F8FAFC'));

    doc.fillColor('#0F172A').fontSize(8).font('Helvetica-Bold');
    doc.text(tKey.replace(/_/g, ' ').toUpperCase(), 42, yPos + 6, { width: 66 });

    doc.font('Helvetica').fillColor('#334155');
    doc.text(`${latVal}${latVal === 'Not available' ? '' : ' ms'}`, 112, yPos + 6, { width: 54 });
    doc.text(costValue === null ? 'Not available' : `INR ${formatMetric(costValue)}`, 170, yPos + 6, { width: 75 });
    doc.text(`${latencyEvidence}: ${truncateSource(latSrc)}`, 250, yPos + 4, { width: 108, height: rowHeight - 4, ellipsis: true });
    doc.text(`${costEvidence}: ${truncateSource(costSource)}`, 363, yPos + 4, { width: 108, height: rowHeight - 4, ellipsis: true });
    doc.text(
      `Lat ${formatSlaStatus(slaCheck && slaCheck.latency_status, latValue, latencyTarget)}\nCost ${formatSlaStatus(slaCheck && slaCheck.cost_status, costValue, monthlyBudget)}`,
      478,
      yPos + 3,
      { width: 78, height: rowHeight - 3 }
    );

    yPos += rowHeight;
  });

  // --- SECTION 3: DETAILED COMPONENT BREAKDOWN ---
  yPos += 15;
  doc.fillColor('#0F172A').fontSize(11).font('Helvetica-Bold').text('3. Detailed Component Breakdown (Selected Tier)', 35, yPos);
  doc.rect(35, yPos + 13, 525, 1).fill('#CBD5E1');

  yPos += 22;

  const latComp = recData.latency_ms && typeof recData.latency_ms === 'object'
    ? (recData.latency_ms.latency_components_ms || {})
    : {};
  const costComp = recData.monthly_cost_inr && typeof recData.monthly_cost_inr === 'object'
    ? (recData.monthly_cost_inr.cost_components_inr || {})
    : {};

  doc.fillColor('#1E293B').fontSize(8).font('Helvetica-Bold').text('Latency Components (ms):', 45, yPos);
  yPos += 12;
  doc.font('Helvetica').fillColor('#475569');
  let latText = Object.entries(latComp).map(([k, v]) => `${k}: ${v}ms`).join(' | ') || 'N/A';
  doc.text(latText, 45, yPos, { width: 505 });

  yPos += 20;
  doc.fillColor('#1E293B').fontSize(8).font('Helvetica-Bold').text('Cost Components (INR):', 45, yPos);
  yPos += 12;
  doc.font('Helvetica').fillColor('#475569');
  let costText = Object.entries(costComp).map(([k, v]) => `${k}: INR ${v}`).join(' | ') || 'N/A';
  doc.text(costText, 45, yPos, { width: 505 });

  const assumptions = [
    ...(recData.latency_ms && Array.isArray(recData.latency_ms.assumptions) ? recData.latency_ms.assumptions : []),
    ...(recData.monthly_cost_inr && Array.isArray(recData.monthly_cost_inr.assumptions) ? recData.monthly_cost_inr.assumptions : [])
  ];
  yPos += 20;
  doc.fillColor('#1E293B').fontSize(8).font('Helvetica-Bold').text('Evidence & assumptions:', 45, yPos);
  yPos += 12;
  const evidenceNotes = [
    `Selected-tier source type: latency ${recLatencyEvidence}; cost ${recCostEvidence}.`,
    'Constraint checks compare supplied values to workload limits; checks based on estimates are provisional.',
    assumptions.length ? assumptions.join('; ') : 'No metric-specific assumptions were supplied.'
  ].filter(Boolean).join(' ');
  doc.font('Helvetica').fillColor('#475569').text(evidenceNotes, 45, yPos, { width: 505 });
  yPos += doc.heightOfString(evidenceNotes, { width: 505, font: 'Helvetica', fontSize: 8 }) + 8;

  const hasTierMetrics = tiers.some((tier) => {
    const tierData = metrics[tier] || {};
    const estimate = tierEstimates[tier] || {};
    return getMetricValue(tierData.latency_ms) !== null
      || getMetricValue(tierData.monthly_cost_inr) !== null
      || getMetricValue(estimate.latency_ms) !== null
      || getMetricValue(estimate.monthly_cost_inr) !== null;
  });
  if (!hasTierMetrics) {
    yPos += 20;
    doc.fillColor('#475569').fontSize(8).font('Helvetica')
      .text('No workload-matched latency or cost evidence was supplied. These values are left unavailable rather than guessed.', 45, yPos, { width: 505 });
  }

  const explanation = data.explanation || data.rationale;
  if (typeof explanation === 'string' && explanation.trim()) {
    yPos += 22;
    doc.fillColor('#1E293B').fontSize(8).font('Helvetica-Bold').text('Recommendation rationale:', 45, yPos);
    yPos += 12;
    doc.font('Helvetica').fillColor('#475569').text(explanation.trim(), 45, yPos, { width: 505 });
    yPos += doc.heightOfString(explanation.trim(), { width: 505, font: 'Helvetica', fontSize: 8 }) + 8;
  }

  const limitationText = 'Limitations: Estimated figures are provisional until validated with representative application measurements and workload-matched pricing. Verify the selected tier against production latency, throughput, memory, privacy, and criticality requirements before deployment.';
  const limitationHeight = doc.heightOfString(limitationText, { width: 505, font: 'Helvetica', fontSize: 8 });
  if (yPos + limitationHeight > 755) {
    doc.addPage();
    yPos = 45;
  }
  doc.fillColor('#475569').fontSize(8).font('Helvetica')
    .text(limitationText, 45, yPos, { width: 505 });

  // Footer
  doc.rect(35, 780, 525, 1).fill('#CBD5E1');
  doc.fillColor('#94A3B8').fontSize(8).text('Confidential — EdgePilot System Automated Stage 3 Report', 35, 788, { align: 'center' });

  doc.end();
}

module.exports = { generatePdfReport };
