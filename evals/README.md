# Memory outcome suite

Six scripted scenarios that ask one question each: after Hermes has talked
about something, does the next conversation get the right memory back?

| Scenario | What is seeded | What the probe must get |
|---|---|---|
| `preference_change` | a preference, then its replacement in a later conversation | the new one; the old one absent or marked superseded |
| `corrected_fact` | a figure, then an explicit correction | the corrected figure; the wrong one never shown as current |
| `interrupted_work` | a durable task and progress notes, then the process dies | the open-work brief naming the task on the first message |
| `cross_session_decision` | a decision and its reason | both, from a new conversation that asks without naming it |
| `unrelated_project` | facts about one project | nothing, when the message is about something else |
| `deletion` | a built-in memory entry, then its removal | the removed text must not come back |

Each run drives the provider through the hook order Hermes uses
(`on_turn_start` → `prefetch` → `sync_turn` → `queue_prefetch`, then
`on_session_end`), waits for the extraction jobs its receipts name, and probes
from a new provider instance.

## Running

The [2026-11-18 recreated-lab report](../deploy/hermes-lab/ACCEPTANCE-2026-11-18.md)
records two accepted cold readiness observations and a closed actual-Hermes
stale-preference failure on its pinned integration candidate. It is separate
from this six-scenario harness and from released plugin 1.3.0. Its
[frozen protocol](RECREATED-LAB-PROTOCOL.md) preserves the source, accounting and
terminal gates; a correct model answer did not override stale recalled context.

```bash
# Harness self-test against a scripted stand-in. Proves the runner and the
# scoring work. It says nothing about memory quality.
python -m evals.run --offline

# The measurement: a real MindGraph org. Use a dedicated test org: the run
# writes transcripts, a task and memory entries into it.
MINDGRAPH_EVAL_API_KEY=mg_... python -m evals.run --report evals/report.json
```

`MINDGRAPH_EVAL_BASE_URL` overrides the endpoint. Every run stamps its facts
with a fresh codename, so earlier runs in the same org do not answer for it.

## What is measured

- **Outcome**: per scenario, the expected phrases present and the stale or
  forbidden phrases absent (or carried only on an item marked superseded).
- **Irrelevant context**: injected items that mention none of the scenario's
  subject terms.
- **Recall latency**: wall time of `prefetch`, per probe; p50 and max.
- **Token overhead**: injected characters per probe (÷ 4 as a token estimate).
- **Capture durability**: turns synced versus transcript rows the server
  accepted; batches left pending, parked or dropped.
- **Extraction**: jobs created, how each ended, and final gate verification duration
  (earlier input barriers are excluded; this is not total extraction latency).

Not measured: whether a model uses the context well (that needs an agent in
the loop), and dollars (the client cannot see the server's model spend;
ingested characters and job counts are the proxy).

## Completion and attribution gates

The runner keeps input providers alive until transcript delivery, every extraction
job and native-memory mirrors settle. `--wait` bounds the shared input-completion
budget. A missing receipt, failed extraction or incomplete mirror invalidates all
probes; it cannot become a passing deletion/unrelated result. Remember/delete
acknowledgements are retained in the JSON report, including matching node IDs.
A failed or timed-out probe also fails even when its fallback text is empty.
Topic expectations must occur in recalled items attributable to the run; an
unrelated automatic work brief cannot supply an expected answer. Interrupted
work uses its created task UID as the provider's explicit resume target.

Live profiles are retained by default. Use `--home /path/to/new/profile` to select
where; existing paths are refused to prevent accidental reuse. Keep these
profiles and raw reports private: a shared graph can return existing user data.
See [the qualification protocol](LIVE-ACCEPTANCE.md) for candidate identity,
confirmation runs, budgets and the limits of the resulting acceptance claim.

## Actual CLI capture-only profiles

Use [capture-only.yaml](capture-only.yaml) in a fresh, dedicated Hermes profile
when measuring automatic recall and transcript capture. Its explicit
`platform_toolsets.cli: []` removes model-callable tools while keeping the
MindGraph memory provider active. A prompt saying “Do not use tools” is
insufficient: an actual correction session invoked memory tools and invalidated
its capture-only run.

The host tests check both Hermes tool selection and the complete CLI against
local model/API stand-ins. They require an empty model tool list, recalled
context in the actual model request, and one captured user/assistant exchange.
These are integration checks, not live memory-quality evidence.

The latest actual-Hermes run follows the [transport reproduction protocol](TRANSPORT-REPRODUCTION-PROTOCOL.md).
Its [closed result](../deploy/hermes-lab/TRANSPORT-REPRODUCTION-2026-11-18.md) failed
independent source review despite passing runtime capture gates. The preceding
[current-assertion protocol](CURRENT-ASSERTION-ACCEPTANCE-PROTOCOL.md) and
[transport failure](../deploy/hermes-lab/CURRENT-ASSERTION-ACCEPTANCE-2026-11-18.md)
remain preserved. Neither run establishes broader acceptance.
