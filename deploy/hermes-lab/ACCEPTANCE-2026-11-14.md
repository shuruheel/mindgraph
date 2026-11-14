# Broader acceptance progress — 2026-11-14

Status: **not yet accepted**. Candidate
`8dd05a9ad61f24ed964b60a7df604cbd8f25fee9` is deployed in the private lab;
[draft PR #11](https://github.com/shuruheel/mindgraph/pull/11) carries the changes.
The original failed `e7c348` run remains unchanged.

## Candidate checks

- 475 unit tests passed locally and on the Fly lab; 33 host tests passed against
  Hermes `ae1ff71c39d8527227400c8e71acf9c57a8a59c6`.
- Final candidate CI passed Python 3.11/3.13, real Hermes/catalog validation,
  version consistency and secret scanning. Ruff and diff checks passed.
- Independent contract review cleared delivery/mirror gates, retrieval outcome
  reporting, task scoping and topic attribution after two false-pass defects
  were fixed. Independent experiment review cleared the frozen protocol.
- Input barriers now require delivery and completed extraction. Negative checks
  require successful retrieval; topic expectations must belong to the run.
  Live profiles and failed reports are retained.

## Backend blocker and repair rehearsal

Text-only retrieval and automatic context retrieval reproduce
`Storage error: corrupted index` in the authorized shared benchmark graph.
Snapshot probes isolate the failure to `node_search:search_text_fts`; the tested
label and summary queries succeed. These are diagnostics, not acceptance runs.

An isolated fresh snapshot was repaired with Mnestic 0.19.2's transactional
`::reindex node_search`. The 2GB rehearsal exhausted memory after backup and its
failure is retained. The successful rehearsal used two performance CPUs and
8GB RAM:

- Supported database backup: 132.27 seconds, 5,642,457,088 bytes.
- Rebuild: 162,405 base rows, 166.84 seconds; identical base count and hash.
- Previously failing raw query: succeeded with 883 candidates.
- Backup integrity check and restoration into a separate empty database:
  passed with matching base hash (220.09 seconds).
- Exact deployed server binary, SHA-256
  `0a6776b15c2a4adb58fd90c5d40083a461b1079d91a3efc8555d671624e9a7ba`,
  reopened the repaired copy and returned 10 text results with HTTP 200.
  Its control plane was a local fixture, with no production credentials or
  model calls; background workers were disabled. An initial fixture auth error
  and a 180-second cold-open timeout were retained. With a 600-second cold-open
  allowance, tenant initialization took 307.45 seconds and the first text query
  a further 12.13 seconds. This does not change the plugin recall deadline.

Production has not been repaired. The prepared procedure pauses incoming service
traffic, takes a live backup, rebuilds only the affected derived index with
8GB RAM, verifies base hashes, and restores the exact original server image and
configuration before resuming traffic. It never promotes a snapshot clone.
The estimated shared API interruption is 15–20 minutes. There is no global
active-job endpoint, and unfinished jobs may be cancelled without automatic
replay. Explicit maintenance approval was requested; test-write authorization
alone was not treated as permission for that interruption.

The latest authorized-tenant job inventory contained 18 terminal jobs and no
active jobs. This is not proof of quiescence across all tenants or schedulers.
Private raw reports, graph-derived data and operational configuration remain
outside this repository under `/tmp/hermes-acceptance-fix` and the isolated
repair volume. Temporary repair machines are stopped while approval is pending.

## Remaining gates

No development or confirmation suite has been run in this new phase yet.
After backend repair, follow [the frozen protocol](../../evals/LIVE-ACCEPTANCE.md):
one labelled development suite, two fresh 6/6 confirmations with complete input
and retrieval gates, then the actual-Hermes capture/new-session recall pair.
Do not claim broader acceptance or publish these changes as qualified before
those gates pass. The pending release remains distinct from released v1.2.0.
