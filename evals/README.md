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
- **Extraction**: jobs created, how each ended, and seconds until the last
  one finished.

Not measured: whether a model uses the context well (that needs an agent in
the loop), and dollars (the client cannot see the server's model spend;
ingested characters and job counts are the proxy).
