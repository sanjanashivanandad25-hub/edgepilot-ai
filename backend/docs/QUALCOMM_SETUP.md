# Qualcomm Cloud AI explanation integration (Person 2)

## What is already implemented

`ai_engine/explain.py` contains a working **OpenAI-compatible REST client adapter** that calls a configured provider's `/chat/completions` endpoint with a model, prompt, and request data. There is no default hardcoded API endpoint or model ID because the selected Qualcomm AI Inference Suite playground and its supported models can vary by provider/region/account.

Official Qualcomm product page explicitly supports Python SDK and OpenAI-compatible APIs: https://www.qualcomm.com/developer/software/qualcomm-ai-inference-suite

## Steps requiring your account

1. Choose the Qualcomm AI Inference Suite developer playground listed on the official Qualcomm product page, create/sign into a playground account, and obtain an API key.
2. Copy the **exact chat-completions API base URL** and **supported model ID** from that playground's REST docs/examples. The base URL should end at the versioned API root (`.../v1`, if that is what the provider documents); the adapter appends `/chat/completions`.
3. Set environment variables in the terminal, preferably using a private `.env` file loaded by your backend framework or local shell:

```bash
export QUALCOMM_API_KEY='YOUR_PRIVATE_KEY'
export QUALCOMM_BASE_URL='https://YOUR_PROVIDER_API_BASE_URL'
export QUALCOMM_MODEL='PROVIDER_MODEL_ID'
```

4. Run:

```bash
python3 -m ai_engine.cli --input examples/request_v1.json --qualcomm
```

5. Check that the output explanation is generated and does not contain the `Qualcomm explanation unavailable` fallback warning. If the account is misconfigured or unavailable, the engine falls back automatically.

## What cannot be verified until you connect credentials

The request/response adapter and fallback are unit-tested with a fake HTTP provider. The exact Qualcomm playground endpoint, actual available model, key permissions, model response format and quota require an authorized live call. This package **does not falsely claim it already made a successful real Qualcomm request**.

If a playground offers only Qualcomm's SDK-specific transport rather than the OpenAI-compatible endpoint expected by this adapter, replace the internals of `QualcommExplainer.explain()` using the official `python-imagine-sdk` as documented by your chosen provider. Its interface should remain `explain(workload, tier, scores, blocked, assumptions, default_text) -> str`.

## Safety and robustness decisions

- The decision engine always chooses the tier **before** calling the LLM. The LLM can change prose only, not numbers, scores, architecture or feasibility decisions.
- A deterministic explanation is used when the external service is unavailable, times out, rejects input or produces a suspicious quantitative guarantee.
- Do not provide the API key to Person 1's frontend. Put it only on Person 3's backend secrets/environment.
- The explainer only sends workload preferences and calculated results; do not expand the workload to include customer data or confidential medical/identity information.
- API calls time out by default after 8 seconds. Person 3 may cache generated explanations and disable LLM generation during heavy traffic.
