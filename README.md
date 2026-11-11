# mindgraph — Hermes memory provider

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[MindGraph](https://mindgraph.cloud) typed knowledge-graph memory for [Hermes Agent](https://github.com/NousResearch/hermes-agent), as a `MemoryProvider` plugin. The tools are the general profile of the [`mindgraph-mcp`](https://github.com/shuruheel/mindgraph-mcp) server, so a Hermes agent and an MCP client see the same memory surface.

## Install

```bash
hermes plugins install mindgraph   # from the Hermes plugin catalog; prompts for MINDGRAPH_API_KEY
hermes memory setup                # pick "mindgraph"
```

Get an API key at [mindgraph.cloud](https://mindgraph.cloud). Hermes installs the Python dependencies from `pyproject.toml` and requires Hermes 0.22.0 or later.

Optional settings, read per profile from Hermes's secret scope (`.env`):

| Variable | Default | Effect |
|---|---|---|
| `MINDGRAPH_BASE_URL` | `https://api.mindgraph.cloud` | API endpoint (self-hosted servers) |
| `MINDGRAPH_AGENT_ID` | `hermes` | Provenance stamped on every write |
| `MINDGRAPH_ORG_ID` | — | Org header for keys with access to several orgs |
| `MINDGRAPH_GOVERNANCE` | on | `off` skips the per-call governance checkpoint |
| `MINDGRAPH_AUTO_CAPTURE` | on | `off` stops automatic transcript ingestion (and the capture queue) |
| `MINDGRAPH_RECALL` | on | `off` stops per-message recall and the open-work brief; the tools still work |
| `MINDGRAPH_RECALL_LIMIT` | `5` | Items injected per message (1–20) |
| `MINDGRAPH_RECALL_MAX_CHARS` | `4000` | Character budget of the injected block (512–24000) |
| `MINDGRAPH_RECALL_DEADLINE_MS` | `3000` | How long a turn waits for recall (250–6000) |
| `MINDGRAPH_RECALL_FLOOR` | on | `off` injects the server's top matches without the relevance floor |
| `MINDGRAPH_RECALL_RERANK` | server default | `on` / `off` for the server's question-aware rerank |
| `MINDGRAPH_PROJECT_UID` | — | Bound recall to one corpus Project (see [Recall scope](#recall-scope)) |

## What happens in a conversation

| Hermes hook | MindGraph behaviour |
|---|---|
| `system_prompt_block` | Static memory instructions (orient → answer → preserve), identical to the MCP server's, so the prompt stays cacheable. |
| `prefetch` | Recall for the current message (below), plus the open-work brief on a conversation's first turn when there is open work. |
| `queue_prefetch` | Retries a recall that failed, on its own thread. A healthy conversation makes no extra request. |
| `sync_turn` | Commits the completed turn to the profile's capture queue on disk. It never waits on the network. |
| `on_pre_compress`, `on_session_end`, `on_session_switch`, queue over 24k characters | Seals the queue into batches and ingests them as session transcripts (`/ingest/session`) attached to the conversation's MindGraph Session. |
| `on_memory_write` | Mirrors Hermes's built-in memory into `/memory/remember` (and `/memory/forget` on replace or remove), keyed by content so replays upsert. |
| `handle_tool_call` | Checks `/agent/governance`, then runs the tool. |

Subagent, cron and flush contexts never write automatically (the one exception is a [required checkpoint](#pre-compress-checkpoint)). Each Hermes profile gets its own provider instance, client, session and queue; nothing is shared at module level.

### Recall

Recall runs before every model call, so it is built around three things a person notices: a turn that waits, context about the wrong thing, and the same items repeated.

- **Query.** The message is reduced to its content terms (`/retrieve/context` matches any query word, so a full sentence dilutes it). A message with no subject of its own, such as "what did we decide?", borrows the previous message's terms. Text in scripts written without word spaces is sent whole.
- **Relevance floor.** An item is injected only when it mentions two distinct query terms (one, when the query has one), comparing words by stem so "policies" matches "policy". The server always returns its best matches; for an unrelated message those are still unrelated. When terms were borrowed, a match on one of the message's own terms is enough and is listed first, so "what about Postgres?" is answered about Postgres.
- **Deadline.** The live call gets `MINDGRAPH_RECALL_DEADLINE_MS`. Past it the turn proceeds, using the conversation's last recall when that is on topic, and the late answer is kept for the next message.
- **No repeats.** An item already injected in the conversation is not injected again until compression drops it or its status changes.

Each item is one line: type, label, status (`SUPERSEDED by …`, a non-accepted truth status, outside its validity window), summary, the date it was stated and its source.

The floor is lexical, so a question in one language will not match memory written in another; set `MINDGRAPH_RECALL_FLOOR=off` for cross-language use.

#### Recall scope

By default recall searches everything the key can read. To bound it to one corpus Project, set `MINDGRAPH_PROJECT_UID`, or map workspaces to Projects in `$HERMES_HOME/mindgraph/workspaces.json`:

```json
{ "/Users/me/code/voya": "project-uid-1", "/Users/me/code": "project-uid-2" }
```

The longest path that contains the conversation's working directory wins. A bound is opt-in for a reason: a Project's boundary is its member documents, and the session transcripts this provider ingests are not members, so a bounded recall does not see past conversations.

### Capture

A completed turn is written to `$HERMES_HOME/mindgraph/capture.db` (SQLite, mode 0600) before `sync_turn` returns, and deleted from it once MindGraph has accepted it. A batch leaves the queue only on the server's acceptance, so:

- a crash or kill loses nothing: the next start delivers what was left;
- an outage delays capture: batches are retried with backoff, oldest first, and stay in order;
- a request whose outcome is unknown is not ingested twice. The deployed `/ingest/session` does not act on an idempotency key yet, so each batch's tag is in its transcript title (`Hermes session <id> · <tag>`). A batch is marked as possibly sent before its request goes out, and the next attempt, in this process or a later one, looks for the tag among the server's jobs and then among its transcript Documents before it sends again. If neither lookup can answer, the batch waits. Each batch is also sent with an `idempotency_key` when the installed `mindgraph-sdk` has that argument (no published version does yet), so a server that supports the key returns the first transcript on a resend;
- a request the server refuses outright is parked with its text and tried again at each start;
- `/undo` removes every unsent turn of that conversation, including the undone turn if Hermes delivers it after the undo. Hermes does not say how far an undo went, so this errs toward not sending; the count is in status.

Delivery runs on a thread of the provider's own. `sync_turn` never waits for it, and the boundary hooks wait a few seconds at most, so a slow server delays capture and not Hermes.

Up to 20 MB of undelivered text is held. Past that the oldest undelivered batches are dropped, logged and counted. `mindgraph_memory` with `action: "status"` reports the queue (buffered, pending, parked, dropped, discarded by undo, last delivery and its job) and what became of delivered extraction jobs.

If the profile directory cannot hold the queue, turns are held in memory for the life of the process and status says so.

### Pre-compress checkpoint

The provider implements Hermes's checkpoint API v2 whenever its queue is on disk. With `compression.checkpoint_required: true`, Hermes hands over the user and assistant text about to be compressed; the provider commits the rows it has not already captured before returning, and raises if it cannot, so Hermes keeps the uncompressed transcript. "Committed" means on disk in the profile's queue; delivery to MindGraph follows as above. This applies in every agent context, including the subagents Hermes loads a provider into for exactly this purpose. Without the requirement, a checkpoint only flushes the queued turns, and non-primary contexts write nothing.

## Tools

| Tool | Actions |
|---|---|
| `mindgraph_memory` | `status`; `context` with mode `topic`, `continuity` or `resume` |
| `mindgraph_capture` | entity, observation, source, snippet, concept, journal, lesson, skill |
| `mindgraph_reason` | claim, question, open_question, hypothesis, theory, paradigm, anomaly, assumption |
| `mindgraph_commit` | goal, project, milestone, open_decision, add_option, add_constraint, resolve_decision, get_open_decisions |
| `mindgraph_plan` | tasks, plans, leases, iterations, executions, procedures, risk assessments |
| `mindgraph_retrieve` | text, context, semantic, hybrid, structured lists, preferences, layer, recent, traversals, document_index |
| `mindgraph_remember` | remember (upsert by `custom_id`), forget |
| `mindgraph_series_query` | list_for_entity, latest, window, aggregate |
| `mindgraph_ingest` | chunk, document, session, job_status |
| `mindgraph_synthesize` | signals, run, job_status |
| `mindgraph_ontology` | schemas, query, objects, proposals, link, extract |

The MCP server's generated per-object-type ontology tools are not exposed (Hermes fixes a provider's tool list before the provider can fetch the ontology); `mindgraph_ontology` covers the same reads. Failed calls return `{"error", "code", "retriable", "status"}` from the server's typed error, never an empty result.

## Data and network disclosure

- Every tool call, recall and capture goes to the configured MindGraph API (`api.mindgraph.cloud` by default) under your `MINDGRAPH_API_KEY`.
- With automatic capture on (the default), the user and assistant text of each completed turn is sent for extraction. Tool calls and tool output are not sent. Hermes redacts secrets before providers see the text.
- Until MindGraph accepts it, that text rests in `$HERMES_HOME/mindgraph/capture.db`, readable only by the profile's owner. Delivered text is deleted from the file; a receipt (job id, document uid, digests of what was sent) is kept for 30 days.
- With `compression.checkpoint_required: true`, the user and assistant text of a transcript about to be compressed is captured too, including in subagents.
- Recall sends the content words of the current message (and of the previous one, for a follow-up without a subject) as the search query.
- Each tool call first sends its name, action and target node uids to `/agent/governance`.
- No telemetry and no credentials stored outside Hermes. One short-lived background thread per start delivers transcripts left by an earlier process.

## Upgrading from 0.x

1.0.0 replaces the five 0.x tools with the mindgraph-mcp surface. `mindgraph_remember` now means `remember`/`forget`. Claims moved to `mindgraph_reason`, entities and notes to `mindgraph_capture`, and goals, decisions and plans to `mindgraph_commit` and `mindgraph_plan`. Live graph state is no longer baked into the system prompt; it arrives through per-message recall.

## Development

```bash
python3 -m pytest                                  # needs mindgraph-sdk importable
python3 -m evals.run --offline                     # outcome-suite harness self-test (evals/README.md)
node scripts/sync_from_mcp.mjs ../mindgraph-mcp    # regenerate mcp_contract.json
node scripts/gen_mcp_fixtures.mjs ../mindgraph-mcp # regenerate tests/fixtures/mcp_requests.json
python3 scripts/check_version.py                   # plugin.yaml == pyproject.toml == __init__.py
```

`mcp_contract.json` is generated; edit the MCP server and re-sync instead. Point both scripts at a released `v*` tag of mindgraph-mcp with its dependencies installed (`npm ci`); they use that checkout's esbuild and install nothing here.

`tests/fixtures/mcp_requests.json` records the HTTP requests the MCP server's own handlers send for a fixed set of tool calls; `tests/test_mcp_request_parity.py` replays the same calls through this plugin and asserts the same requests. `tests/test_contract_parity.py` fails when the contract advertises a parameter no handler reads.

The `contract-drift` workflow (weekly, on demand, and on PRs touching the contract, scripts, handlers, renderer or fixtures) regenerates both files from the latest mindgraph-mcp `v*` tag and fails when they differ from the checked-in copies. To fix it, run both scripts against that tag, port the handler changes the diff shows, and commit the regenerated files. The ordinary test workflow needs no Node.

`tests/host` runs the plugin inside real Hermes: its plugin loader, its `MemoryProvider` ABC and its `MemoryManager`, against a MindGraph stand-in on a local socket. It needs a hermes-agent checkout installed from its lockfile and `HERMES_HOST_TESTS=1`; the `host` CI job does both at the commit pinned in `.github/workflows/test.yml`. When you bump that pin, a failure is an upstream contract change to port. `tests/test_wire.py` runs a subset over the same socket without Hermes.

`evals/` is the memory outcome suite: six scripted scenarios (a changed preference, a corrected fact, interrupted work, a decision recalled across conversations, an unrelated message, a deletion) that measure what the next conversation gets back. The `eval` workflow runs it against a real org on demand; see `evals/README.md`.

## License

MIT
