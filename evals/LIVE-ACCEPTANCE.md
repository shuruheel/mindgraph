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


## V2 revision follow-up after development 05a4d6

Run 05a4d6 failed input prerequisites after four delivered rows and two jobs;
no recall probe was scored. Its report remains 0/6, alongside d2b302 at 4/6.
The conservative reservation is retained in full: **one development suite, two
confirmation suites, four agent invocations and 22 review reservations remain**.

The next candidate follows the backend's
[source-backed revision contract](https://github.com/shuruheel/mindgraph-rs/blob/fix/transcript-revision-review/docs/specs/transcript-revisions.md).
Pin that contract's committed SHA and hash in the deployment manifest; the branch
link is navigation, not immutable evidence. It uses hash-bound actual user turns
instead of treating extraction citation hints as semantic proof, permits wholly
atomic Concept propositions, and applies certified exact-span Entity summary
edits without retiring Entity identities. Summary edits invalidate old vectors;
server-owned audit certificates provide durable targets for embedding recovery.
Source deletion retracts the unchanged correction span while preserving unrelated
later edits. These are experimental backend behaviors, disabled by default.

The collector retains both Supersedes and Describes certificates, affected node
versions, review request/response evidence when lifecycle fences permit its
persistence, and provider telemetry. Preserve the first defective development-2
collector output and its separately hashed supplemental collection. No collector
change alters the scorer or the old report.

All earlier scenario, deadline, confirmation and stopping rules remain in force.
The $3 estimate above covers added review calls only. Regenerating corrected
summary embeddings is additional work within the same bounded extraction jobs;
record embedding requests/tokens alongside review usage rather than treating that
estimate as total experiment cost. Scripted semantic verdicts validate mechanical
constraints, not model judgment. A passing private deployment establishes these
six functional scenarios, not general correction accuracy or arbitrary shared
Entity safety.

## Phase 2: candidate selection after 5d4704

The original development phase is closed: d2b302 remains 4/6; 05a4d6 and
5d4704 remain 0/6 with failed input prerequisites and no scored recall probes.
The last run delivered two rows and one job, which ended `completed_with_errors`.
Its one review request used 6,369 input and 241 output tokens. Six extracted
representations all cited one user turn; the model returned identical old/new
UIDs while explaining that no correction was justified. Validation rejected it
before persistence. The complete conservative reservation is retained.

Under the standing instruction to continue until broader acceptance succeeds,
preregister this separate continuation before further model calls:

- One additional development suite, named `phase2-development-1`, on a new
  immutable candidate that fixes this reproduced candidate-selection defect.
  Offline tests must prove no model call for one user turn plus an assistant
  echo, rejection of self/unchanged-turn proposals, and preservation of legitimate
  corrections across two user turns in one transcript. Independent contract and
  protocol reviews must pass before execution.
- Carry forward the two untouched confirmation suites and four agent invocations.
  Both confirmations must pass 6/6 on the passing phase-2 candidate before the
  actual-Hermes pair. Every scenario, scorer, prerequisite, recall default and
  agent prompt remains unchanged. A failed phase-2 development or confirmation
  ends this phase; no automatic rerun or conversion of confirmation to development.
- Raise the cumulative reservation ceiling explicitly from five to six suites,
  from 30/70 to 36/84 suite jobs/rows, and from 28 to 34 review calls. Preserve the
  existing three ledger entries, all unused portions of their reservations and
  their original candidate identities. Record the phase-2 protocol hash and
  prerequisite reservation IDs in a separate ledger extension; do not reset it.
- At the previously recorded higher route rates and conservative 300,000 input
  plus 4,096 output tokens per call, 34 reviews estimate $2.44, still within the
  $3 review-stage planning allowance. This excludes extraction, embeddings and
  Hermes calls; retain actual request/token telemetry rather than claiming a bill.

The new backend conservatively leaves corrections wholly within one user turn
unsupported; distinct user turns within one transcript remain eligible. A skip
does not prove reconciliation. The unchanged stale-assertion checks still apply.
Passing would qualify only the recorded private deployment and frozen functional
scenarios. It would not qualify production or general correction accuracy.

## Phase 3: structured review with GPT-6.1 Sol — 2026-11-14

The four development suites remain failed and retain their original scores,
artifacts and reservations. Five subsequent diagnostic phases also failed;
none is relabeled as a suite or a confirmation. The separately frozen
`SOL-REASONING-DIAGNOSTIC.md` pair passed both mechanical and independent
source-backed review on core `6acffc549058f6b0bcc5f27e80c99d6308c1f22f`.
Its manifest is `e067a98a256f587049382bfdd675cbba8ec0f2db9e6ef2aac493cddd28009be6`.
That result covers two known development fixtures with no graph writes. It does
not establish general semantic safety: a prior Luna proposal passed structural
validation while selecting an unsupported assistant endpoint, and was rejected
by the independent oracle. Preserve that failure and this limitation.

This phase adds exactly one fresh ingestion development suite, then permits the
two untouched confirmations only if it passes. All three must use the same
immutable plugin/backend/configuration identity and unchanged six-scenario
scorer. Use the private repaired clone, fresh profile and codenames each time,
default recall settings and the existing successful-request/three-second gates.
Every receipt and ingestion job must complete without errors before recall
probes. Preserve the mirror remember/forget acknowledgments, negative cases,
retirement checks, full raw reports and revision certificates. Each passing
suite also needs independent source-backed review of its certificates and
selected assertion endpoints before the next suite or actual-agent pair may
start; a structural or scorer pass alone is insufficient. Record that review
and its artifact hash in the existing reservation. No failed
confirmation becomes development, and no unchanged-candidate suite is rerun.
Failure closes this phase. Two 6/6 confirmations are required before the
unchanged actual-Hermes pair (four-invocation ceiling and replacement-pair gates
remain in force). The agent itself continues using the frozen Luna setup.

The backend keeps all prior model/routing settings except curation becomes
`openai/gpt-6.1-sol`. Its mandatory provider-default reasoning is effective even
with the global hybrid-reasoning switch off; the adapter omits the unsupported
disable flag and temperature. Strict schema and supported-parameter routing
remain enabled; 4096 tokens include reasoning plus visible output. Freeze the
built image digest, core/cloud/engine/plugin SHAs, runtime config, health/deep
identity, preflight, helper hashes and validation in the backend manifest before
paid ingestion. The lab remains private and the prototype remains opt-in.

The ledger must preserve all ten preceding entries: four failed suites, five
failed diagnostics and the passed Sol diagnostic, totaling 33 review
reservations. Append a phase-3 extension only after its terminal passed verdict
is archived. Raise cumulative ceilings from six to seven suites, 36 to 42 suite
jobs, 84 to 98 suite rows, and 49 to 55 review reservations. The added development
reserves six reviews; two confirmations and four possible agent captures retain
their 16 reservations. No refunds, reset, rescoring or automatic expansion.

Explicitly raise the review-stage planning allowance from $5 to $10 for the
curation-model change. Carry the prior $4.228664 planning allowance without
credit, and estimate all 22 future reviews (development, confirmations and
maximum agent captures) at 75000 input plus 4096 output tokens and the recorded
higher ordinary Sol route's $2.75/M cache-write input and $11/M output rates:
$5.528732 additional, $9.757396 carried total. This is a planning estimate based
on bounded review inputs and prior usage, not a guaranteed token/spend cap or a
measured bill. Preserve actual token telemetry; extraction, embedding and
Hermes model costs remain excluded. Success qualifies this private candidate
and these functional scenarios only, not production or general memory efficacy.

## Phase 4: compact support presentation after 9d47e2 — 2026-11-14

Phase 3 is closed. Development af67d4 passed 6/6 and independent source review;
confirmation 9d47e2 failed prerequisites with eight accepted rows and three jobs.
Its corrected-fact job exceeded the 64,000-character review prompt budget before
calling Sol. No recall was measured. Preserve both results, the 12 prior ledger
entries and all **45 consumed review reservations**, including unused portions.

Under the standing instruction to continue to broader acceptance, this separate
phase qualifies a concrete prompt-representation fix. Full version, fingerprint
and provenance evidence remains server-side in review_input and validation;
the model receives every support's complete owning user turn, offsets and
node/document/chunk IDs, every target/pair/identity, all node properties and full
source text. No target or semantic input is dropped. Keep the 64,000-character
evidence-plus-schema limit, unchanged response schema/decoder/fences, one request
per supported chunk and 4,096 output tokens. Record the actual prompt, its size,
and full audit input, including failures before model requests. Demonstrate the
size failure and its correction offline. The post-run failed-current-node
snapshot is a reconstruction; the original oversized input was not retained.
Do not call it an exact replay. No paid diagnostic calls are added in this phase.

Freeze the changed core/plugin SHAs, image/configuration, helper hashes, tests,
source snapshot and preflight before one `phase4-development-1` suite. If it
passes 6/6 plus independent source review, require fresh
`phase4-confirmation-1` and `phase4-confirmation-2`, both 6/6 and independently
reviewed, on precisely that same candidate. The earlier development pass cannot
qualify changed code. A failed prerequisite, score or review closes this phase;
no unchanged rerun, rescore or substitution is permitted. All prior six scenarios,
receipt/job/mirror gates, default recall settings, source review and actual-Hermes
pair requirements remain unchanged. The model configuration is unchanged from
phase 3, including Sol's mandatory default reasoning and Luna for actual Hermes.

Raise cumulative ceilings explicitly to **nine suites, 54 suite jobs, 126 suite
rows and 67 review reservations**. The new development and two confirmations
reserve 18 reviews; the untouched four-agent-call allowance reserves at most
four more. Append a phase-4 extension with the protocol hash and all prerequisite
reservation IDs; do not reset or refund any earlier entry. All confirmations
and agent calls remain gated by same-candidate independent reviews. The successful
normal path uses two agent calls; the existing diagnosed-replacement rule alone
permits the other two.

Raise the review-stage planning allowance to **$14**. Carry $9.757396 from phase 3
without credit and add the 12 newly allowed Sol reservations at the same
75,000-input/4,096-output planning estimate and higher ordinary-route rates:
$3.015672 additional, **$12.773068 carried estimate**. This is neither a measured
bill nor a hard tokenizer/spend cap; extraction, embeddings and Hermes calls
remain excluded. Retain actual provider telemetry. Independent contract and
protocol review must clear the artifacts before paid ingestion. Qualification
remains limited to this warmed private deployment and these functional scenarios;
search bounds and uneditable aliases preclude exhaustive reconciliation claims.
