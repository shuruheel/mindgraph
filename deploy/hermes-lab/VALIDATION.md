# Initial deployment validation — 2026-11-14 UTC

This is an operational smoke record, not a comparative memory evaluation.
The user authorized synthetic writes using the existing benchmark key; its
organization already contained other data. No credentials are recorded here.

## Deployed environment

- Fly app: `mindgraph-hermes-lab`, personal organization, `iad`.
- Machine: `83dd705f7e0068`; one shared CPU, 1 GB RAM.
- Encrypted 3 GB volume: `vol_r7y8z18e08xl9yyr`, mounted at `/data`.
- Image: `registry.fly.io/mindgraph-hermes-lab:deployment-01M7BQ2EK7HR9A0FN4R6QJDS8B`.
- Image digest: `sha256:e73c42ea270f221eaa83fa720d8897a878b10d1a2e4ab51b69cbd1667bc7b053`.
- Hermes: `ae1ff71c39d8527227400c8e71acf9c57a8a59c6`.
- Plugin: v1.2.0, `2abbfd03b73c6e369ab645bcb747cc6804555507`.
- Python 3.14.0, SQLite 3.53.4, SDK 0.17.0, pytest 9.2.0.
- Lab harness SHA256: `577df897f52b67ac0ae10d86a988e2f79a94c42d15784ae9b88ab3dde7807931`.
- No Fly services configured; access is through Fly SSH. Runtime UID is 10000.
- Model: OpenAI `gpt-6-luna`, Responses transport, reasoning disabled.
  This is a model alias. Runtime session records confirm the requested model;
  they do not identify an immutable model snapshot.

## Remote checks

| Check | Result | Evidence on volume |
|---|---|---|
| Unit suite | 468 passed, 33 host tests skipped | `20261114T002413Z-unit-checks-gfc2nbyi/` |
| Real Hermes host suite | 33 passed | `20261114T002315Z-host-checks-vzno5ckz/` |
| Offline provider scenarios | 6/6 passed; 14/14 transcript rows accepted | `20261114T002431Z-offline-checks-macaoz34/` |
| Mounted-volume restart | sealed batch digest and transcript unchanged across different kernel boot IDs | `restart-proof-69vo8jss/restart.json` |
| Native CLI flag forwarding | `hermes-lab hermes chat --help` prints Hermes help | checked through Fly SSH |
| Native command failure | invalid Hermes command exits 2; Fly SSH exits nonzero (1) | checked through Fly SSH |

All evidence directory paths above are relative to `/data/runs`.
The restart probe used its own synthetic queue, outside the live profile, and
verified one pending batch after reboot. It did not submit that probe to the API.
The deployed initializer also preserved the existing model/plugin configuration
across image updates and a subsequent explicit machine restart.

The host/unit/offline suites ran before the final CLI argument-forwarding fix;
the final wrapper's help and failure paths were then exercised remotely.
Local Ruff, shell syntax checks and diff whitespace checks passed. Independent
read-only review of volume initialization, credential isolation, source pins,
and exit propagation found no actionable defects.

## Live conversation and recall

Evidence: `/data/runs/live-smoke-k9095dux/` (`metadata.json`, seed/recall prompts,
logs, and `receipt.json`). Each invocation was limited to three tool iterations
and a 90-second Hermes run budget. The CLI's reported durations were 33 seconds
for seed and 93 seconds for recall; the run budget is not a hard process deadline.

1. In a new Hermes session, asked it to remember the synthetic project fact:
   `Project HermesLabK9095DUX has the mascot teal otter.`
2. Hermes invoked `mindgraph_remember` and confirmed storage. The ordinary
   transcript capture also produced document `7271c9bf-27dc-43de-aa45-3223779c7f1f`,
   job `d05dd082-690e-492c-8ae5-5a55b7f53782`; a subsequent SDK read reported
   `completed`.
3. Restarted the whole Fly Machine. Started a distinct Hermes session, without
   resuming the seed session, and asked which mascot that project had chosen.
4. Hermes reported one recalled memory, used `mindgraph_memory`, and answered:
   “The chosen mascot for Project HermesLabK9095DUX is a teal otter.” Both
   invocations exited successfully.

The recall conversation also produced a delivered capture batch; both extraction
jobs were subsequently confirmed `completed`. Session counters record two model
API calls per conversation (four total).

Seed session: `local-44f73f805beffa738ea02dca3b15ccdb91c1c1bc895374f0600c1920d8d0ef81`.
Recall session: `local-31f5a5f2d384b24e5d3727f71ca004c35e3b01f2862bf3625f7523c4f8dd614a`.

This demonstrates a working model, plugin tools, capture submission, completed
extraction and cross-session recall after reboot. Explicit remembering and
ordinary capture were both present, so this does not isolate their contribution.
It does not establish correction/deletion quality, outage recovery against the
live service, multilingual recall, isolated-host capture, or agent efficacy.
The six-scenario **live** outcome suite has not been run here.

The native `chat` path did not emit the requested `--usage-file` artifacts.
Session counters were instead saved in `receipt.json`; Hermes marked model cost
`unknown`, so a zero estimate must not be treated as free usage. Backend extraction
spend is also not visible to this client. Future budgeted evaluations need a
verified usage ledger before making cost claims.
