# EdgePilot 3-minute judge demo (team rehearsal)

## 0:00–0:25 The problem (Person 1)
"Teams can run AI on a phone, access edge, regional edge or cloud, but deployment choices trade latency, privacy, scale and cost. EdgePilot translates workload constraints into an auditable, explainable choice."

## 0:25–1:10 The measurable proof (Person 2)
Select MobileNetV2 + Galaxy S25 (Family) + TFLite + float. Show your Workbench result and raw job reference: **0.45 ms on-device model inference only**. The benchmark is exact-match evidence, not overall response latency or cloud comparison. Show missing data as unknown and surface the weighted factor contributions.

## 1:10–1:45 The what-if flip (Person 1 + Person 2)
Start with memory requirement 256 MB and available memory 1,024 MB (hypothetical input values); change availability to 128 MB. Show a computed switch from on-device to far edge under the engine's demo assumptions. Present new infeasibility reasons, not just a recolored badge. Simulated costs are withheld when scenario assumptions change and no fresh estimate is supplied.

## 1:45–2:20 Explain / challenge decision (Person 2)
Click 'Why not cloud?' and show Qualcomm-hosted explanation with `answer_source='qualcomm_llm'`. Show comparison with the selected tier, caveats, and the deterministic fallback when the provider is unavailable. Never pretend fallback prose came from Qualcomm.

## 2:20–2:45 Trade-offs (Person 3)
Display illustrative Pareto frontier, hybrid candidate and cost break-even model. Clearly label demo prices/latencies as illustrative; add genuine provider data later. A hybrid option is optional async analytics and requires consent/policy checks and measurements.

## 2:45–3:00 Reliability and close (all)
Show Stage 7 audit and one contradictory/offline scenario. Explain no deployment action is triggered. Close: 'This is a benchmark-aware advisor with explainable, auditable decisions and reproducible what-if analysis.'

## Judge questions to practice

- **Why does the S25 show 0.45 ms?** That is Qualcomm Workbench model inference timing for one exact configuration; not full application delay.
- **Are the scores probabilities?** No; transparent heuristic suitability indices; measured cost/latency can influence them when supplied for the same workload.
- **Can you guarantee the recommendation?** No. The audit checks internal consistency and flags missing evidence.
- **How do you estimate monthly cost?** Backend cost model with fixed/variable components and declared assumptions; synthetic fixture isn't a provider quote.
- **What happens without Qualcomm?** Deterministic scoring and explanation remain available; source field and warnings disclose fallback.
- **Can you actually deploy edge or cloud from the app?** Not yet. The project recommends architectures; it doesn't provision infrastructure.

## Acceptance for a real hackathon demo

A demo is ready only when Person 1 and 3 have the live integration running; Person 2's local passing tests alone are insufficient. Record working API calls/screenshots, avoid exposing API keys, and retain the Workbench evidence link separately from user data.
