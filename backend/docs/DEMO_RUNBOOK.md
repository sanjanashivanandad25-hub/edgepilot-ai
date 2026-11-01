# Three reliable scenarios for your team demo

Run in terminal from project root, or POST the sample request fields to Person 3's API.

## A. Privacy-heavy, short-deadline workload

Input `examples/request_v1.json`. Expected: preliminary `on_device` (with default heuristic profiles); no verified costs/latencies. Use the UI to show score breakdown and the deterministic explanation.

```bash
python3 -m ai_engine.cli --input examples/request_v1.json
```

## B. Same requirements, insufficient local device memory

Input `examples/request_enhanced.json`. Device RAM 1024 MB vs model requirement 2048 MB. The local option must score 0 **because it is blocked**, and a remote tier should be recommended. Graph should update to the selected tier.

```bash
python3 -m ai_engine.cli --input examples/request_enhanced.json
```

## C. Network outage

Set `network_available=false` or `require_offline=true`. All network-tier options should be rejected. With enough local RAM, on-device wins. With insufficient local RAM too, the decision becomes `recommended_tier=null`; that's a valid outcome and the UI needs an informative empty state.

## D. Scale-heavy workload

Set `concurrent_users=50000`, `latency_requirement_ms=400`, and low privacy/criticality. With default heuristics, cloud tends to win. Be transparent that actual placements depend on architecture and cost data.

## E. Challenge the recommendation

```python
from ai_engine.sensitivity import compare_scenarios
from ai_engine.recommender import recommend

original = {"workload": {"latency_requirement_ms": 50, "bandwidth_requirement": "medium", "budget_monthly": 1000, "privacy_requirement": "high", "criticality": "high"}}
print(compare_scenarios(original, {"model_ram_required_mb": 4096, "device_available_ram_mb": 1024}))
```

Tell judges: **suitability scores are transparent heuristics; verified latency and costs must come from documented benchmarks and estimator inputs.** Avoid displaying the team's static mock ₹800/25ms figures as measured production performance.
