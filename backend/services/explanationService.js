// services/explanationService.js

const TIER_METADATA = {
  on_device: {
    explanation: "On-device processing is selected to guarantee near-zero latency, maximum privacy, and complete independence from network availability.",
    tradeoffs: [
      "Constrained by local hardware compute limits",
      "Higher initial device hardware cost"
    ],
    warnings: [
      "Ensure local device has sufficient battery and thermal dissipation capacity."
    ],
    assumptions: [
      "Assumes model size fits within local device RAM/NPU memory constraints."
    ],
    architecture: {
      nodes: [
        { id: "device", label: "User Device (Local Engine)", type: "device" }
      ],
      connections: []
    }
  },
  far_edge: {
    explanation: "Far edge deployment balances low-latency localized response with moderate compute power directly near the user premises.",
    tradeoffs: [
      "Requires local gateway edge infrastructure",
      "Slightly higher latency than pure on-device execution"
    ],
    warnings: [],
    assumptions: [
      "Assumes local network link (Wi-Fi/LAN) maintains sub-10ms latency."
    ],
    architecture: {
      nodes: [
        { id: "device", label: "User Device", type: "device" },
        { id: "far_edge", label: "Local On-Prem Gateway", type: "edge" }
      ],
      connections: [
        { source: "device", target: "far_edge" }
      ]
    }
  },
  regional_edge: {
    explanation: "Regional edge provides a strong balance of latency, data-transfer efficiency, cost, privacy, and system availability.",
    tradeoffs: [
      "Higher operational cost than pure on-device",
      "Requires regional edge infrastructure subscription"
    ],
    warnings: [],
    assumptions: [
      "Assumes regional edge node is hosted within 50 km of the source location."
    ],
    architecture: {
      nodes: [
        { id: "device", label: "User Device", type: "device" },
        { id: "edge", label: "Regional Edge Node", type: "edge" },
        { id: "cloud", label: "Cloud Server", type: "cloud" }
      ],
      connections: [
        { source: "device", target: "edge" },
        { source: "edge", target: "cloud" }
      ]
    }
  },
  cloud: {
    explanation: "Centralized cloud deployment leverages massive compute resources for complex AI model workloads and unlimited horizontal scaling.",
    tradeoffs: [
      "Higher network latency dependent on WAN connectivity",
      "Increased monthly data transfer expenses"
    ],
    warnings: [
      "Cloud latency may fluctuate significantly under network congestion."
    ],
    assumptions: [
      "Assumes reliable internet connection with high bandwidth availability."
    ],
    architecture: {
      nodes: [
        { id: "device", label: "User Device", type: "device" },
        { id: "cloud", label: "Central Cloud Provider", type: "cloud" }
      ],
      connections: [
        { source: "device", target: "cloud" }
      ]
    }
  }
};

function generateExplanationAndArchitecture(recommendedTier) {
  return TIER_METADATA[recommendedTier] || TIER_METADATA.cloud;
}

module.exports = { generateExplanationAndArchitecture };