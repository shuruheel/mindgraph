# Changelog

## Unreleased

### Added

- **Durable capture.** Completed turns are committed to a per-profile queue on
  disk (`$HERMES_HOME/mindgraph/capture.db`) before `sync_turn` returns and are
  delivered at least once, in order. A crash, a kill or an outage delays
  capture instead of losing it; the next start delivers what was left.
- **Retries without duplicates.** `/ingest/session` has no idempotency key, so
  each batch carries a tag in its transcript title. A batch is marked as
  possibly sent before its request goes out, and an attempt of unknown outcome
  (a timeout, a 5xx, a process killed mid-send) is looked up among the
  server's jobs and transcript Documents before it is resent.
- **Delivery off Hermes's worker.** Transcripts are sent on the provider's own
  thread; `sync_turn` never waits on the network.
- **Capture status.** `mindgraph_memory` `status` reports the queue (buffered,
  pending, parked, dropped, last delivery) and what became of delivered
  extraction jobs.
- **Pre-compress checkpoint (Hermes checkpoint API v2).** With
  `compression.checkpoint_required: true`, the transcript rows about to be
  compressed are committed before the call returns, and a failed commit raises.
- **Recall relevance floor.** An item is injected only when it mentions two
  distinct query terms (one when the query has one), compared by stem.
- **Recall deadline** (`MINDGRAPH_RECALL_DEADLINE_MS`, 3 s default), with the
  conversation's last recall as the fallback and a background retry.
- **Conversational recall.** A message without a subject of its own borrows
  the previous message's terms. Queries are Unicode-aware.
- **No repeated recall.** An item already injected in the conversation is not
  injected again until compression or a status change.
- **Recall settings**: `MINDGRAPH_RECALL`, `MINDGRAPH_RECALL_LIMIT`,
  `MINDGRAPH_RECALL_MAX_CHARS`, `MINDGRAPH_RECALL_FLOOR`,
  `MINDGRAPH_RECALL_RERANK`, `MINDGRAPH_PROJECT_UID`, and a workspace→Project
  map in `$HERMES_HOME/mindgraph/workspaces.json`.
- `mindgraph_retrieve` `context`: `as_of` and `retrieval_mode`, and the
  server's own text rendering (dated items, supersession and conflict markers)
  unless `format: "json"` is asked for. Matches mindgraph-mcp 0.25.0.
- Real-host tests (`tests/host`, the `host` CI job), cross-door request parity
  tests, a contract-drift workflow, and the memory outcome suite (`evals/`).

### Changed

- Requires `mindgraph-sdk` 0.17.
- Transcript titles end in ` · <tag>`.
- Recalled items are one line each with type, status, stated date and source,
  under "Related memory (most relevant first)".
- The open-work brief is looked up beside the recall, not before it.
- Messages shorter than twelve characters are recalled on when they carry a
  content term ("k8s?"); the previous fixed cutoff is gone.
- Undelivered transcript text now rests on disk in the profile directory until
  MindGraph accepts it.

### Fixed

- Superseded items were never marked. `/retrieve/context` sends `superseded`
  as an object naming the head of the chain; the renderer only recognized
  `true`. Recall, `mindgraph_memory` and `mindgraph_retrieve` now show
  `SUPERSEDED by <what replaced it>`, and unresolved conflicts are marked.
- After compression a conversation was briefed on open work a second time.
- The server-rendered context merged in 1.0.0's follow-up could never appear:
  no request asked for it and SDK 0.16 could not.
- A failing server no longer makes the provider drop its oldest buffered turns
  past 200,000 characters without a trace.

## 1.0.0 (2026-10-28)

The mindgraph-mcp general tool surface on Hermes's current `MemoryProvider`
contract. See the README's "Upgrading from 0.x".
