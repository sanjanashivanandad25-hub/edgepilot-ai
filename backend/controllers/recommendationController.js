// controllers/recommendationController.js
const { calculateScoresAndEstimates } = require('../services/scoringService');
const { generateExplanationAndArchitecture } = require('../services/explanationService');
const { calculateDetailedCosts } = require('../services/costService');
const { runSimulation } = require('../services/simulationService');

// Primary Recommendation Endpoint (Async for Python execution)
const getRecommendation = async (req, res) => {
  const { workload } = req.body;

  if (!workload) {
    return res.status(400).json({
      error: {
        code: "INVALID_REQUEST",
        message: "A valid workload object is required."
      }
    });
  }

  // Await Python recommendation engine execution
  const aiResult = await calculateScoresAndEstimates(workload);
  const metadata = generateExplanationAndArchitecture(aiResult.recommended_tier);

  return res.status(200).json({
    recommended_tier: aiResult.recommended_tier,
    scores: aiResult.scores,
    estimates: aiResult.estimates,
    explanation: aiResult.explanation || metadata.explanation,
    tradeoffs: aiResult.tradeoffs || metadata.tradeoffs,
    warnings: aiResult.warnings || metadata.warnings,
    assumptions: aiResult.assumptions || metadata.assumptions,
    architecture: aiResult.architecture || metadata.architecture
  });
};

// Cost Analysis Endpoint
const getCostAnalysis = (req, res) => {
  const { workload } = req.body;

  if (!workload) {
    return res.status(400).json({
      error: {
        code: "INVALID_REQUEST",
        message: "A valid workload object is required."
      }
    });
  }

  const costAnalysis = calculateDetailedCosts(workload);
  return res.status(200).json(costAnalysis);
};

// Simulation Endpoint
// Inside controllers/recommendationController.js
const handleSimulation = async (req, res) => {
  const { baseline_workload, modified_workload } = req.body;

  if (!baseline_workload || !modified_workload) {
    return res.status(400).json({
      error: {
        code: "INVALID_REQUEST",
        message: "Both 'baseline_workload' and 'modified_workload' objects are required."
      }
    });
  }

  const simulationResult = await runSimulation(baseline_workload, modified_workload);
  return res.status(200).json(simulationResult);
};
const { generatePdfReport } = require('../services/reportService');

const downloadReport = async (req, res) => {
  const recommendationData = req.body;

  if (!recommendationData || !recommendationData.recommended_tier) {
    return res.status(400).json({
      error: {
        code: "INVALID_REQUEST",
        message: "Valid recommendation payload is required to generate a PDF report."
      }
    });
  }

  try {
    const pdfBuffer = await generatePdfReport(recommendationData);
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', 'attachment; filename=EdgePilot_Recommendation_Report.pdf');
    return res.status(200).send(pdfBuffer);
  } catch (error) {
    return res.status(500).json({
      error: {
        code: "INTERNAL_ERROR",
        message: "Failed to generate PDF report."
      }
    });
  }
};

module.exports = { getRecommendation, getCostAnalysis, handleSimulation, downloadReport };
