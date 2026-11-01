// services/simulationService.js
const { calculateScoresAndEstimates } = require('./scoringService');

/**
 * Compares a baseline workload against a modified/degraded workload.
 * Handles both "what-if" parameter tweaks and network failure simulations.
 */
async function runSimulation(baselineWorkload = {}, modifiedWorkload = {}) {
  // 1. Evaluate baseline workload
  const baselineResult = await calculateScoresAndEstimates(baselineWorkload);

  // 2. Evaluate simulated/modified workload
  const simulatedResult = await calculateScoresAndEstimates(modifiedWorkload);

  const tierShifted = baselineResult.recommended_tier !== simulatedResult.recommended_tier;

  // 3. Construct explanatory context for the simulation
  let impactExplanation = "";
  if (tierShifted) {
    impactExplanation = `Workload modifications caused the recommended tier to shift from '${baselineResult.recommended_tier}' to '${simulatedResult.recommended_tier}'.`;
  } else {
    impactExplanation = `The '${simulatedResult.recommended_tier}' tier remains optimal despite parameter adjustments.`;
  }

  // Safe delta calculation helper
  const calcDiff = (simScores = {}, baseScores = {}) => ({
    on_device: (simScores.on_device || 0) - (baseScores.on_device || 0),
    far_edge: (simScores.far_edge || 0) - (baseScores.far_edge || 0),
    regional_edge: (simScores.regional_edge || 0) - (baseScores.regional_edge || 0),
    cloud: (simScores.cloud || 0) - (baseScores.cloud || 0)
  });

  return {
    simulation_status: "completed",
    tier_changed: tierShifted,
    baseline: {
      recommended_tier: baselineResult.recommended_tier,
      scores: baselineResult.scores,
      estimates: baselineResult.estimates
    },
    simulated: {
      recommended_tier: simulatedResult.recommended_tier,
      scores: simulatedResult.scores,
      estimates: simulatedResult.estimates
    },
    impact_analysis: {
      explanation: impactExplanation,
      score_differences: calcDiff(simulatedResult.scores, baselineResult.scores)
    }
  };
}

module.exports = { runSimulation };
