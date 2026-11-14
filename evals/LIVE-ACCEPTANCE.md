# Live acceptance qualification

## Amendment after development run d2b302

The original `d2b302` report remains 4/6 and is not rescored. Before any further
paid runs, the next development phase tightens the scorer: expected and stale
phrases are evaluated in the renderer's structured displayed assertion, with
retirement taken from structured server status. Annotations and source titles
cannot supply either. Arbitrary brackets in assertion text are preserved.
Raw rendered text remains the input for forbidden-text checks. A `LATER
STATEMENT` cross-reference alone neither retires an
old assertion nor establishes the replacement answer. Existing positive
correction sentences and authoritative retirement markers remain supported.

This fixes a reproduced false-pass path introduced by rendering the server's
restatement cue. Scenario text, required facts, negative checks, recall defaults
and confirmation gates are unchanged. The overall budget is **not reset**:
one suite/six jobs/14 rows has been consumed; at most two further development
suites and two confirmation suites remain, plus the original four-agent-call
allowance. Backend revision review is not qualified by this amendment: its
contract, opt-in configuration, resource budget and immutable source must be
reviewed and recorded before testing it live.

## Original protocol

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


## Source-backed backend development amendment (2026-11-14)

The original d2b302 result remains 4/6. Continue with the same six scenarios,
scorer, recall defaults and remaining budget (two development suites, two
confirmation suites, four agent invocations). Do not reset counters or rescore
old reports. This development uses the reviewed opt-in backend candidate on a
private Fly machine with an isolated copy of the repaired benchmark graph,
8 GB RAM, authenticated benchmark identity and all Cloud background workers
disabled with `MINDGRAPH_RELEASE_SMOKE_MODE=true`. No public service or production
graph writes are part of this backend experiment. Record the clone's source,
base-row count/hash and candidate/config/image hashes before the first run.

Require immutable plugin, Cloud, core and Mnestic SHAs, image digest, host/model
identity and effective settings in each run manifest. Verify the clone's exact
text/semantic lookups and credential-free gates before model work. Pin extraction
models to the recorded production configuration; enable transcript review only
for the authenticated test uploader plus fresh profile namespace. Record chunk
review coverage, unsupported-source skips, model requests/usage and certificate
counts alongside the unchanged delivery and extraction gates. Unsupported
review does not itself establish reconciliation; stale assertions still fail.

The additional review stage permits one call per supported chunk, 64 candidates,
24,000 source characters, 64,000 evidence characters and 4,096 output tokens.
No automatic re-review or extra probe may bypass the suite/agent limits. Across
remaining authorized runs, allow at most 28 additional review calls (24 suite
jobs plus at most four agent captures). Stop if this cap or the existing job/call
budget is exhausted. GPT-5.4 Nano via OpenRouter is the recorded curation model.
On 2026-11-14 its provider page lists $0.20/$1.25 per million input/output tokens
($0.22/$1.375 for the higher-priced listed route). A conservative planning
allowance of 300,000 input plus 4,096 output tokens per call gives about $2.01
for 28 calls at that higher rate; reserve $3 for this added stage. This is an
estimate, not an observed bill or a tokenizer guarantee; preserve reported
usage and do not claim exact total experiment spending. Pricing source:
https://openrouter.ai/openai/gpt-5.4-nano

Passing this private-backend experiment establishes functional acceptance only
for its recorded artifacts and deployment. It does not establish production
latency under concurrent traffic or enable the feature for unrelated users.
Production delivery requires its own concrete artifact/config preflight.
Independent protocol review is required before these additional paid calls.
