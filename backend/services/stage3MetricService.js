const fs = require("fs");
const path = require("path");

function readJson(filename) {
  const fullPath = path.join(
    __dirname,
    "..",
    "examples",
    filename
  );

  return JSON.parse(
    fs.readFileSync(fullPath, "utf8")
  );
}

function getMetricsForWorkload(workload) {
  // Demo fixtures are returned for every workload; they are illustrative, not device-matched.
  return {
    metrics_by_tier: readJson(
      "stage6_pareto_tradeoff_metrics_DEMO.json"
    ),
    cost_curves: readJson(
      "stage6_cost_curves_DEMO.json"
    ),
    evidence_mode: "illustrative_estimates"
  };
}

module.exports = { getMetricsForWorkload };