# Live acceptance qualification

This protocol follows the failed `e7c348` run on 2026-11-14. That run and its
separate recovery diagnostics remain unchanged. It exposed an incomplete-input
measurement, default-deadline misses, irrelevant recall and a reproducible
backend `Storage error: corrupted index` on text retrieval.

## Gates frozen before candidate runs

Use the pinned Hermes host from CI and an immutable plugin candidate SHA.
Record source/input hashes, backend/image identity when available, runtime
settings, profile path and every raw report. Use a fresh local profile and a
fresh synthetic project codename for each run. The authorized backend org is
shared: this is functional acceptance, not an isolated efficacy benchmark.

Keep the existing six scenarios and their expected/stale/forbidden phrases.
Before any probe, every transcript must have a delivery receipt and every
extraction job must finish `completed`. Missing job receipts, pending/dropped/
failed batches, unacknowledged mirror operations and failed extraction are
failed prerequisites; do not score an empty recall as a passing negative.
Every probe must also complete retrieval successfully within the unchanged
deadline; an error, timeout or unattempted lookup fails even when no forbidden
text appears. Topic expectations must come from a recalled item attributable to
this run, never merely from an unrelated open-work brief.
Preference changes are ingested in conversation order with a completion barrier.
Deletion must have a searchable remember acknowledgement followed by a matching
forget acknowledgement before checking that the deleted text is absent.

The interrupted-work probe uses the task UID returned by its own create call,
through the provider's explicit active-task setting. This scopes the experiment
in the shared graph without changing the expected task. Unrelated-query recall
still reads the shared graph and must return no topic items; open-work context
remains excluded from that scenario's item count, as before.

Use production defaults: the three-second recall deadline, five injected items,
4,000-character rendering budget and relevance floor enabled. Do not increase
these to make a failed candidate pass. Explicit retrieval tools retain their
separate graph-expansion controls; automatic first-message recall uses direct
matches to avoid extra graph traversal on its response deadline.

## Runs and stopping rules

- For each implementation change, run local regression/host checks before one
  labelled live development pass. Preserve failures; do not repeat an unchanged
  candidate until a random passing result appears.
- At most three development passes in this phase, each justified by a concrete
  fix. Backend/index repair is recorded separately from plugin changes.
- Qualify the final immutable candidate with two fresh confirmation runs, both
  **6/6 with all input gates satisfied**, under unchanged settings and scorer.
- Then verify capture and new-session recall through actual Hermes using the
  configured GPT-6 Luna model. Limit each invocation to three tool iterations,
  a 90-second run budget and an outer process deadline. Retain session records.
- Budget: at most five six-scenario suites (30 small transcript extraction jobs,
  70 transcript rows) in this phase, plus at most four short agent invocations.
  No paid judge, bulk corpus ingestion or benchmark comparison. Server extraction
  model/cost and current Hermes dollar accounting are not observable; do not
  claim an exact dollar total. Record job and call counts instead.
- On a failed prerequisite or confirmation, retain the evidence and investigate;
  no successful broad-acceptance claim is allowed. A changed design starts a new
  explicitly labelled development phase, not a replacement score for an old run.

Independent contract review covers the delivery/mirror gates, task scoping and
runtime request changes before delivery. A passing result establishes these
functional scenarios on the recorded candidate and backend; it does not establish
multilingual quality, isolated plugin-host capture, or general agent efficacy.

## Actual-Hermes conversation pair (frozen before model calls)

Use one fresh profile and fresh `Orion` plus six random hexadecimal digits.
Seed prompt: "For the {code} internal test project, the service window is Tuesday
09:40 UTC and the mascot is copper badger. Reply only Noted. Do not use tools."
Probe prompt in a genuinely new Hermes session with no prior chat messages:
"For the {code} internal test project, what are the service window and mascot?
Answer using your available context. Do not use tools."

Require no explicit memory/retrieval tool calls in either session. Before the
probe, verify the seed transcript's accepted receipt and completed extraction
job, with no pending/dropped/failed capture. Save the actual session IDs, prompt
and response records, automatic-recall outcome and injected context. The probe
must have successful automatic retrieval under the frozen defaults, with the
seed project and both facts present in its injected context; its final answer
must contain `Tuesday`, `09:40 UTC`, and `copper badger`. Check that no native
MEMORY.md/USER.md entry or earlier conversation supplies those facts. A passing
answer without this capture-and-injection evidence is insufficient.

Two invocations suffice for this pair. The remaining two-call allowance may only
be used after diagnosing a concrete failure and recording a new candidate/run;
retain the failed pair. Each suite/agent run manifest must record and assert the
effective recall deadline, item limit, character budget and relevance floor,
plus candidate/host/input hashes, backend identity and model identity. Manifests
are saved before scoring; inherited environment overrides cannot silently alter
the frozen defaults.
