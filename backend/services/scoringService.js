const { calculateSuitability } = require('./suitabilityService');

async function calculateScoresAndEstimates(workload = {}) {
  const workloadInput = workload.workload || workload;
  return calculateSuitability(workloadInput);
}

module.exports = { calculateScoresAndEstimates };
