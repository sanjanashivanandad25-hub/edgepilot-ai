# Stage 8 Quick Start

1. Run `unzip -n ~/Downloads/edgepilot_stage8_final_handoff_patch.zip -d .` from the current `edgepilot_person2_handoff` root.
2. Run `python3 -m unittest discover -s tests -v` (expected 233 tests for unchanged earlier stages).
3. Run `python3 -m scripts.stage7_validation_matrix --output /tmp/edgepilot_stage7_matrix.json` (expected 10/10).
4. Run `python3 -m scripts.stage8_smoke_test --output /tmp/edgepilot_stage8_smoke.json` (expected 10/10).
5. Run `python3 -m ai_engine.team_cli --operation recommend --input examples/request_s25_match.json --benchmark-dir benchmarks --output /tmp/edgepilot_stage8_recommend.json`.
6. Run `python3 -m ai_engine.team_cli --operation simulate --input examples/request_stage5_s25_hardware.json --changes examples/stage5_changes_memory_drop.json --benchmark-dir benchmarks --output /tmp/edgepilot_stage8_simulate.json`.
7. If the real Qualcomm service works in your terminal: `set -a; source .env; set +a; python3 -m ai_engine.team_cli --operation explain --input examples/request_s25_match.json --question why_not_tier --alternative-tier cloud --qualcomm --output /tmp/edgepilot_stage8_qualcomm.json`.
8. Read `docs/STAGE_8_TEAM_HANDOFF.md`, then export a clean ZIP using `python3 -m scripts.stage8_export_handoff --output dist/edgepilot_person2_team_handoff.zip --include-evidence`.
9. Share the generated ZIP with Persons 1 and 3 and send them `docs/HACKATHON_DEMO_SCRIPT.md`.

The Stage 8 patch itself does **not** contain your private `.env` or Qualcomm authentication. It also doesn't include your actual local S24 benchmark record; your export does, if `--include-evidence` is selected and the file exists.
