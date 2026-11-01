// services/costService.js

/**
 * Computes multi-factor monthly costs for each deployment tier.
 *
 * Formulas:
 * - Total Monthly Requests = requests_per_day * 30
 * - Compute Hours = (Total Requests * compute_time_ms) / (1000 * 3600)
 * - Data Transfer (GB) = (Total Requests * data_per_request_mb) / 1024
 */
function calculateDetailedCosts(workload = {}) {
  const {
    requests_per_day = 10000,
    compute_time_ms = 100,
    data_per_request_mb = 0.5
  } = workload;

  const totalMonthlyRequests = requests_per_day * 30;
  const computeHours = (totalMonthlyRequests * (compute_time_ms / 1000)) / 3600;
  const dataTransferGB = (totalMonthlyRequests * data_per_request_mb) / 1024;

  // Rate Cards (INR estimates)
  const TIER_RATES = {
    on_device: {
      computeRatePerHour: 0,
      dataRatePerGB: 0,
      hardwareAmortizationMonthly: 300 // Local device power/hardware wear
    },
    far_edge: {
      computeRatePerHour: 4.5,
      dataRatePerGB: 1.5,
      hardwareAmortizationMonthly: 250
    },
    regional_edge: {
      computeRatePerHour: 7.0,
      dataRatePerGB: 3.0,
      hardwareAmortizationMonthly: 150
    },
    cloud: {
      computeRatePerHour: 10.0,
      dataRatePerGB: 5.0,
      hardwareAmortizationMonthly: 0
    }
  };

  const detailedBreakdown = {};

  for (const [tier, rates] of Object.entries(TIER_RATES)) {
    const computeCost = Math.round(computeHours * rates.computeRatePerHour);
    const dataTransferCost = Math.round(dataTransferGB * rates.dataRatePerGB);
    const hardwareCost = rates.hardwareAmortizationMonthly;
    const totalCost = computeCost + dataTransferCost + hardwareCost;

    detailedBreakdown[tier] = {
      compute_cost: computeCost,
      data_transfer_cost: dataTransferCost,
      hardware_cost: hardwareCost,
      total_monthly_cost: totalCost,
      currency: "INR"
    };
  }

  return {
    summary: {
      on_device: detailedBreakdown.on_device.total_monthly_cost,
      far_edge: detailedBreakdown.far_edge.total_monthly_cost,
      regional_edge: detailedBreakdown.regional_edge.total_monthly_cost,
      cloud: detailedBreakdown.cloud.total_monthly_cost
    },
    breakdown: detailedBreakdown
  };
}

module.exports = { calculateDetailedCosts };
