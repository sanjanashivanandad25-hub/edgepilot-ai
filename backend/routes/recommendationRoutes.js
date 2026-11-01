const express = require('express');
const router = express.Router();
const { getRecommendation, getCostAnalysis } = require('../controllers/recommendationController');
const { downloadReport } = require('../controllers/recommendationController');
// Health Check
router.get('/health', (req, res) => {
  res.status(200).json({
    status: "ok",
    service: "edge-vs-cloud-backend",
    message: "Backend is running"
  });
});

// Recommendation Endpoint
router.post('/recommend', getRecommendation);

// Task 2: Cost Estimation Endpoint
router.post('/cost', getCostAnalysis);
router.post('/report', downloadReport);

module.exports = router;