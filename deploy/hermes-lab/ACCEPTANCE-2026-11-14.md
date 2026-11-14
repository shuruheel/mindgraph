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

Production repair completed after explicit owner approval. Traffic was paused
from 16:08:31 to 16:26:34 UTC (18m03s). The live database was backed up and only
the affected derived index rebuilt; no snapshot clone replaced live data.

- 162,406 base rows; identical before/after SHA-256
  `a7b73b4528cc35910939f37b0f7ad55d23a53445329ce6c65fb288cbd5f13f20`.
- Backup: 5,642,469,376 bytes, SHA-256
  `ed74a21d26c4b4583560733afae706399ff1e7089b3aa8b218df12b89c9f0e1a`;
  full SQLite integrity check passed. Backup and receipts remain on the
  production volume under `/data/maintenance/approved-20261114T1608Z/`.
- Backup took 122.52s; index rebuild 132.98s. Previously failing raw query
  returned 883 candidates.
- Original server image restored. Fly CLI retained an entrypoint override;
  configuration comparison caught it, and an exact Machines API update removed
  it before traffic resumed.
- The original 4GB allocation repeatedly OOM-killed cold startup. Restoring
  service required **8GB**; configuration otherwise matches the original.
  Observed cold peak RSS was about 4.88GB, settling near 1.9GB. Do not revert
  the memory allocation without a verified startup fix.
- Public verification: healthy/ready, text retrieval HTTP 200 (10 results,
  1.205s), direct context 2.021s, expanded context 2.805s; corrected budget
  present. These diagnostics are separate from acceptance scores.

The pre-maintenance authorized-tenant inventory contained 18 terminal jobs and
no active jobs; shutdown reported `Drained`. This is not proof of quiescence
across all tenants or schedulers.
Private raw reports, graph-derived data and operational configuration remain
outside this repository under `/tmp/hermes-acceptance-fix` and the isolated
repair volume. Temporary repair machines are stopped; the persistent lab remains.

## Remaining gates

Development run `d2b302` on candidate `8dd05a9` passed **4/6**. All 14 transcript
rows were delivered, all six extraction jobs completed, and every probe had a
successful retrieval within three seconds (maximum 2.612s). Interrupted work,
cross-session decision, unrelated query and deletion passed. Preference change
and corrected fact failed because obsolete duplicates remained unmarked.
The original report is retained at
`/data/runs/20261114T162805Z-development-1-4ddxu0if/report.json` on the lab and
in the private local evidence directory. A launcher import error before any
API calls is retained separately and is not counted as an executed suite.

Diagnosis found two plugin integration gaps: omitted capture timestamps on
session ingestion and dropped `later_statements` cues on recall. Follow-up
changes preserve stable capture time across retries, distinguish it from
original event time, retain timestamp precision, and display the server's
restatement cues without inventing supersession. Checkpoint and mixed captures
omit original-turn timestamps. A persistent profile UUID namespaces captures;
it does not authenticate speakers. Live scoring now uses the actual displayed
assertions and structured retirement status, preventing source titles or
later-statement references from supplying false evidence.

Local validation: 486 unit tests and 33 real-Hermes host tests passed; Ruff
passed. Independent contract and scorer/protocol reviews found no remaining
blocking plugin defects. These changes have not had a live acceptance run.

Independent diagnosis confirms that metadata alone cannot resolve the stale
duplicates: backend write-time review covers Claims but the same obsolete fact
also appears as Preference/Constraint/Concept. Source-backed revision
reconciliation is needed; choosing the newest node or hiding stale phrases
would conceal the defect. Backend implementation is not yet qualified.

Continue under [the frozen protocol](../../evals/LIVE-ACCEPTANCE.md): at most two
further development suites in this phase, then two fresh 6/6 confirmations on
one immutable candidate, then the actual-Hermes capture/new-session recall pair.
Consumed so far: one suite, six extraction jobs, 14 rows, zero agent model calls.
Do not claim broader acceptance or publish these changes as qualified before
those gates pass. The pending release remains distinct from released v1.2.0.
