# Getting credible benchmark and cost data into Person 2's engine

## Do not confuse inference time and user-perceived response time

Qualcomm AI Hub Workbench can profile a model on a real supported device, reporting processing times, memory and compute units. Its *model inference latency* is not the same as a remote application's end-to-end latency (which includes request serialization, upload, network travel, queues, inference, return transfer, and app handling).

Only pass full comparable test-path latency in `metrics_by_tier[tier]['latency_ms']`.
If you only have an AI Hub profiling number, use `inference_latency_ms`; this will be stored as extra evidence but will NOT, on its own, satisfy the `latency_requirement_ms` check.

## Steps to gather useful real data

1. Identify one small demo AI model and one specific device/runtime (e.g., a supported image-classification model) and document model ID, model build/version and exact target hardware.
2. Use Qualcomm AI Hub Workbench to profile its inference on real hardware. Record device, runtime, mean/p50/p95 or reported latency, memory, model size and profiling conditions.
3. For a real remote edge/cloud candidate, run test requests from the same user network under representative payload sizes and collect measured end-to-end latency. Unless you have actual far-edge/regional-edge compute servers, mark these as unknown or modeled, not measured.
4. Ask Person 3 for comparable monthly costs in **INR** under specified request volume, compute rates, egress and capital amortization assumptions.
5. Supply tier-specific metrics to `recommend()` with `source` and `source_note`. Supply genuine numbers only. A single provider/device sample is NOT enough to generalize all workloads.
6. Evaluate different workloads (real-time camera, high-volume analytics, offline device), and record where heuristic rankings disagree with measured evidence.

## Tier-metric input schema

Python dict, optional separate file passed to `--metrics`:

```json
{
  "on_device": {
    "source": "measured",
    "source_note": "Place your real benchmark report ID, hardware, test date, and conditions here",
    "inference_latency_ms": 0.0
  }
}
```

The zero in this illustration is a placeholder only; before submitting real metrics, replace it with an actual positive measurement. For a real end-to-end test, add `latency_ms`. For monthly budget analysis, add `monthly_cost_inr`. `model_compatible` can be true/false if verified. Never put private API keys in `source_note`.

Allowed `source` values:

- `measured`: independently observed values under documented conditions
- `quoted`: documented vendor quote / pricing contract
- `estimated`: justified cost/network model with explicit assumptions
- `demo`: fictional fixture; intentionally ignored by the recommendation engine

## Official Qualcomm starting points

- Qualcomm AI Hub Workbench get started: https://aihub.qualcomm.com/get-started
- Profiling/inference examples: https://workbench.aihub.qualcomm.com/docs/hub/inference_examples.html
- Qualcomm AI Inference Suite: https://www.qualcomm.com/developer/software/qualcomm-ai-inference-suite

**Qualcomm inference playground and Workbench are separate services:** the first can generate explanation text using hosted LLMs, the second can collect on-device model performance data.
