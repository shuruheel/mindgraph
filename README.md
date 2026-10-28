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
| `MINDGRAPH_AUTO_CAPTURE` | on | `off` stops automatic transcript ingestion |

## What happens in a conversation

| Hermes hook | MindGraph behaviour |
|---|---|
| `system_prompt_block` | Static memory instructions (orient → answer → preserve), identical to the MCP server's, so the prompt stays cacheable. |
| `prefetch` | Bounded topic recall (`/retrieve/context`, 5 items, 4,000 characters) for the current message, plus the open-work brief on a conversation's first turn when there is open work. |
| `sync_turn` | Buffers the completed turn. |
| `on_pre_compress`, `on_session_end`, `on_session_switch`, buffer over 24k characters | Ingests the buffered turns as a session transcript (`/ingest/session`) attached to the conversation's MindGraph Session; each turn is sent once. |
| `on_memory_write` | Mirrors Hermes's built-in memory into `/memory/remember` (and `/memory/forget` on replace or remove), keyed by content so replays upsert. |
| `handle_tool_call` | Checks `/agent/governance`, then runs the tool. |

Subagent, cron and flush contexts never write automatically. Each Hermes profile gets its own provider instance, client and session; nothing is shared at module level.

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
- Each tool call first sends its name, action and target node uids to `/agent/governance`.
- No telemetry, background processes or credentials stored outside Hermes.

## Upgrading from 0.x

1.0.0 replaces the five 0.x tools with the mindgraph-mcp surface. `mindgraph_remember` now means `remember`/`forget`. Claims moved to `mindgraph_reason`, entities and notes to `mindgraph_capture`, and goals, decisions and plans to `mindgraph_commit` and `mindgraph_plan`. Live graph state is no longer baked into the system prompt; it arrives through per-message recall.

## Development

```bash
python3 -m pytest                                  # needs mindgraph-sdk importable
node scripts/sync_from_mcp.mjs ../mindgraph-mcp    # regenerate mcp_contract.json
python3 scripts/check_version.py                   # plugin.yaml == pyproject.toml == __init__.py
```

`mcp_contract.json` is generated; edit the MCP server and re-sync instead.

## License

MIT
