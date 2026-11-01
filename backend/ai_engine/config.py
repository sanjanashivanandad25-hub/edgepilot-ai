"""Illustrative ordinal profiles, NOT hardware benchmarks or latency predictions.

Team definitions (agree with teammates):
- on_device: inference executes on the user's own hardware.
- far_edge: nearby far-edge/access-network compute, generally closest network hop.
- regional_edge: regional data center, generally farther than far edge.
- cloud: centralized, elastic cloud infrastructure.

All 0-100 values encode transparent demo assumptions, NOT measurements.
"""
TIERS = ("on_device", "far_edge", "regional_edge", "cloud")
FACTORS = ("latency", "privacy", "data_locality", "resilience", "scalability", "affordability")
PROFILES = {
    "on_device": {"latency": 96, "privacy": 97, "data_locality": 60, "resilience": 45, "scalability": 35},
    "far_edge": {"latency": 86, "privacy": 72, "data_locality": 60, "resilience": 65, "scalability": 66},
    "regional_edge": {"latency": 74, "privacy": 65, "data_locality": 60, "resilience": 100, "scalability": 85},
    "cloud": {"latency": 52, "privacy": 48, "data_locality": 60, "resilience": 80, "scalability": 98},
}
TRADEOFFS = {
    "on_device": ["Local hardware capacity and thermal/power limits may restrict which models run.",
                  "Model updates, monitoring and scaling across devices require additional operations."],
    "far_edge": ["Requires deployed far-edge infrastructure and a functioning network path.",
                 "Compute availability and latency depend on the exact access-network location."],
    "regional_edge": ["Requires regional edge infrastructure and network connectivity.",
                      "Off-device processing needs suitable data protection and access controls."],
    "cloud": ["Network transfer adds variability and may increase operating costs.",
              "Privacy, data residency and service outages need explicit mitigation."],
}
LABELS = {"on_device":"On-device", "far_edge":"Far edge", "regional_edge":"Regional edge", "cloud":"Cloud"}
