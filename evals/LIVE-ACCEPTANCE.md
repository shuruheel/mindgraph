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

## Phase 5: sole supersession ownership after e7a96f — 2026-11-15

Phase 4 is closed. Development e7a96f remains mechanically 6/6 with 14 accepted
rows and six completed jobs, but **failed independent source review**. An
uncertified ordinary extraction edge pointed from the initial $8,000 assertion
to the corrected $12,500 assertion, causing recall to mark the correction as
superseded. Seven newly certified revisions were correct; reviewing only those
certificates missed the other producer. Preserve the report, failed source
review, retirement supplement, all 13 ledger entries and all **51 reserved
reviews**. No phase-4 confirmations or actual-Hermes calls ran.

This continuation qualifies one concrete ownership fix: for enabled, configured,
fully framed single-user session transcripts, source-backed final review owns
supersession. Ordinary layer Supersedes output is deferred and legacy collision
review is skipped in this scope. Other node/provenance writes remain available;
unsupported or disabled sources retain ordinary behavior. This also narrows
legacy collision judgments for admitted transcripts. An immutable internal
admission record binds source membership and fingerprint under the storage
write fence. Source drift or lost eligibility must fail required review, including
resume, instead of silently succeeding with a skip. Admission must survive typed
chunk updates without replacing content or extraction checkpoints. Offline tests
and independent contract review must clear these properties before deployment.

Freeze the changed core/plugin SHAs, image/configuration, contract and helper
hashes, hosted checks and private preflight before `phase5-development-1`.
Only after 6/6 and independent source review may `phase5-confirmation-1`, then
`phase5-confirmation-2`, run on precisely the same immutable candidate. Both
must also pass 6/6 and source review before the unchanged actual-Hermes pair.
Any failed prerequisite, score, execution or source review closes the phase.
No unchanged rerun, substitution, score change or paid diagnostic is added.
All six scenarios, model settings, recall defaults, mirror and capture gates,
source predicates and actual-agent prompts remain unchanged.

Independent review must inspect the **complete recalled context**, every newly
certified revision, and incoming/outgoing Supersedes edges for every recalled
item and every node extracted from this run, including uncertified edges and
their endpoint nodes. Collect these exact-UID records only after all scored
probes; no extra search/context queries or retrieval warming during the suite.
Preserve collection failures as failed execution. This evidence expansion does
not change the scorer or turn its old pass into a source-review pass.

Append a phase-5 ledger extension carrying every prior reservation ID and the
failed phase-4 source-review hash. Raise cumulative ceilings to **ten suites,
60 suite jobs, 140 suite rows and 73 review reservations**. The new development
plus two confirmations reserve 18 reviews; retain the untouched four-agent-call
allowance (at most four more reviews). No refunds or resets. Enforce terminal
failure and same-candidate source review before each next reservation. Two agent
calls remain the normal successful path; the prior diagnosed-replacement rule
alone permits the other two, and a successful pair is terminal.

Raise the review-stage planning allowance to **$16**. Carry the phase-4 estimate
of $12.773068 without credit and add six newly allowed reservations at the same
75,000-input/4,096-output estimate and higher ordinary Sol route rates:
$1.507836 additional, **$14.280904 carried estimate**. This is not a measured bill
or hard token/spend cap; extraction, embeddings and Hermes calls remain excluded.
Retain actual provider telemetry. Independent protocol review must clear the
frozen artifacts before paid ingestion. Passing qualifies this warmed private
candidate and these scenarios only; production deployment, general correction
accuracy and exhaustive alias reconciliation remain outside this acceptance.

## Phase 6: whole-assertion support after a70fa1 — 2026-11-15

Phase 5 is closed. Development a70fa1 failed prerequisites after eight accepted
rows and three jobs; no recall was measured. Planned extraction deferrals became
job warnings. Partial independent source review additionally found a certified
retirement of a still-true budget history: the old assertion included both 8,000
and the later 12,500 correction, while its selected old quote supported only
8,000. Preserve that review, the unchanged failed score/report, all 14 ledger
entries and **57 reserved reviews**, including unused portions. No confirmations
or actual-Hermes calls ran. The partial review is not an acceptance review pass.

This phase qualifies the informational-deferral fix and a conservative source
support guard. Allowed choices bind exact old/new support tuples. Each assertion's
bounded literal quantities must occur in its chosen owning user turn; an Entity
uses only its selected summary-edit span on the old side. Same-document choices
must run forward between distinct user turns. Unsupported numeric notation
conservatively excludes tuples. Full candidates, source text and anchors remain
in the audit; eligible targets/pairs may narrow. These checks do not establish
semantic entailment, atomicity, polarity or universal correction correctness.
The model must preserve still-true histories and decline uncertainty. Independent
source review still checks every actual retirement and recalled assertion.

Before private paid development, freeze exact core/plugin/cloud/engine SHAs,
built image digest/configuration, helper hashes, contract review and preflight.
Require exact-candidate revision/choice/history tests, the ordinary-deferral job
regression, the saved phase-5 input eligibility replay, strict Clippy and format.
The fully passing 5c87e94 hosted suite is baseline evidence only. Full new-candidate
hosted checks may run alongside private development, but must pass before final
acceptance. Validation records distinguish the source/tested revision and scope;
no interrupted build or prior-candidate pass substitutes for a changed-path gate.

Run only `phase6-development-1`, then (after 6/6 and independent full source
review) `phase6-confirmation-1` and `phase6-confirmation-2` on the same immutable
candidate. Each must pass 6/6 and independent review before proceeding. Any failed
prerequisite, execution, score or review closes the phase. No unchanged rerun,
rescoring, paid diagnostic or replacement suite is allowed. All six scenarios,
model settings, recall defaults, clean job/mirror/capture gates, expanded edge
collection and actual-Hermes pair requirements remain unchanged. A partial
source failure from a prerequisite-failed run cannot qualify any subsequent gate.

Append a phase-6 ledger extension carrying every previous reservation ID and the
phase-5 partial source-review hash. Raise cumulative ceilings to **eleven suites,
66 suite jobs, 154 suite rows and 79 review reservations**. Reserve 18 reviews
for development and two confirmations; retain at most four agent captures. No
refunds or resets. Same-candidate full source review gates each next reservation.
Two agent calls remain the normal successful path; only the existing diagnosed
replacement rule permits the other two, and a successful pair is terminal.

Keep the **$16 review-stage planning allowance**. Carry $14.280904 without credit
and add six newly allowed Sol reservations at the same 75,000-input/4,096-output
estimate and recorded higher ordinary-route rates: $1.507836 additional,
**$15.788740 carried estimate**. This is not a measured bill or hard token/spend
cap; extraction, embeddings and Hermes calls remain excluded. Retain actual
provider telemetry. Independent protocol review must clear the frozen artifacts
before paid ingestion. Qualification remains limited to the warmed private
candidate and these functional scenarios, with no production deployment claim.

## Phase 7: explicit historical rejection after a4a07a — 2026-11-15

Phase 6 is closed. Development 54e4d9 and confirmation ab7983 passed 6/6 and
independent source review. Confirmation a4a07a remains **5/6**, despite fourteen
accepted rows and six clean jobs. Its retained Observation explicitly said the
initial $8,000 figure was superseded by a correction, without repeating $12,500.
Independent review found valid history; the frozen scorer required retirement
metadata or the new value in the same assertion. Do not rescore, supersede this
history, pool the old scores with the new instrument, or reuse a prior run as a
new confirmation. Preserve all seventeen entries and **75 reserved reviews**.
No actual-Hermes acceptance calls ran.

This phase changes the evaluation instrument only. The private backend remains
core `49482433c8de2abfb0f93a15569feb62ee5170b7` and release image digest
`63bc31e0264867427579636aedaf804d2d0a73943e8f8439c99e1830c14176ad`.
Plugin runtime behavior, scenarios, expected answers, defaults and model settings
remain unchanged. Freeze the new plugin/scorer/helper identities before running.
Reuse exact-backend validation and the full passing CI run 43754502269; require
new plugin/evaluator tests, real-host checks, observed image/configuration and
preflight evidence. No backend rebuild or production deployment is part of this
instrument repair.

The separate `historical-budget-rejection-v1` predicate applies only to the
corrected-fact scenario. It requires a complete displayed summary naming the
exact project, pilot-budget attribute and old amount in a past recorded/stated
clause, followed by a direct rejection of that figure. Only the implemented,
bounded grammar qualifies; unknown forms retain failure behavior. Noun labels
may name the old figure, but explicit active/current claims in labels conflict
and are refused. Negation, questions, hypotheticals, another subject or field,
trailing active assertions and metadata-only cues do not qualify. The supported
$12,500 answer must still occur in assertion content independently of history.
No retirement flag is invented and stored nodes are unchanged.

The twenty positive/adversarial calibration fixtures were frozen before
implementation at SHA256
`ee8042bdcce7965f9451bceda99d8b82933da84d9a2229cbd0e3cfcbb579b43d`.
They include the saved failure, bare initial wording, future/conditional/negated
corrections, wrong subjects/fields, label conflicts, trailing current assertions,
metadata-only cues, missing replacement answers and an unrecognized history form.
Retain the original-scorer failure log and the repaired offline test results as
calibration evidence, not live qualification or rescoring of a4a07a.

Every exemption records UID, exact displayed assertion, stale phrase and rule.
An independent assistant source reviewer must explicitly confirm each as supported
history and not a current assertion; uncertainty fails the review. A model's
`no_revision` reason alone is insufficient. The review record binds the assertion
hash to two distinct forward, complete plain-user turns in the captured source.
The recording helper checks complete exemption coverage, exact UTF-8 quotes,
role/hash framing, live captured document/chunk membership and ExtractedFrom
provenance before recording a passed review. Document and source-edge snapshots
are collected only after scored probes, alongside the existing full retirement
collection. No additional search/context probes run during the suite.

Run one `phase7-development-1`, then only after 6/6 and a full independent source
review, `phase7-confirmation-1` and `phase7-confirmation-2` on the same immutable
candidate. Both must pass the same mechanical and source gates before the
unchanged real-Hermes seed/new-session pair. A failed input, execution, score or
source review closes this phase; no rerun, substitution, diagnostic call or
post-hoc rule change is permitted. Retain all prior capture/job/mirror, latency,
negative-control and actual-agent requirements. A mechanical pass with historical
exemptions is provisional until their required source review passes.

Append a phase-7 extension preserving every prior reservation ID and the failed
confirmation-review hash. Raise cumulative limits to **fourteen suites, 84 suite
jobs, 196 suite rows and 97 review reservations**: eighteen reviews for three
fresh suites, plus the unchanged at-most-four agent captures. No refunds or
resets; the successful agent path still uses two calls and is terminal.

Under the standing instruction to continue this private acceptance work, raise
the review-stage planning allowance to **$22**. Carry $15.788740 without credit
and add eighteen newly allowed reservations at the same 75,000-input/4,096-output
Sol planning rate: $4.523508 additional, **$20.312248 carried estimate**. This is
not a measured bill or hard token/spend cap; extraction, embedding and Hermes
calls remain excluded. Record actual provider usage. Independent protocol review
and final artifact preflight must clear before paid ingestion. Qualification is
limited to these warmed private recall/retirement scenarios; cold latency,
general extraction correctness and exhaustive reconciliation remain unqualified.

## Phase 8: separate generated attribution after 76f301 — 2026-11-15

Phase 7 is closed after development 76f301 scored **5/6**. Fourteen rows were
accepted, six jobs completed cleanly, and recall stayed below three seconds.
The preference probe recalled an obsolete current Constraint. Its summary mixed
the user's prose requirement with “as confirmed by the assistant”; the reviewer
correctly refused whole-node retirement. Independent review confirmed a real
reconciliation failure, with all six other certificates supported. No historical
scoring exemption was used. Preserve all eighteen entries and **81 review
reservations**, including this failed score and its independent diagnosis. No
confirmation or actual-agent calls ran in phase 7.

The new private backend candidate adds prospective extraction cleanup under the
existing framed single-user admission. Core source
`75460c2fe940693440808a83e6d14a786ca0a945` also merges current main
`800f601`; the newer subject/name-capture features remain disabled in the private
runtime. The earlier 37c3276 build was interrupted after discovering the PR
merge conflict and is not validation evidence. Guidance separates user propositions from
routine acknowledgments while preserving substantive assistant information.
Deterministic cleanup removes only the exact terminal attribution clause from a
new Constraint summary with a nonempty description, preserving its entire prefix,
label, properties and captured source. Unknown or qualified forms remain intact.
The original and resulting summaries and rule ID are retained in the new node's
ExtractedFrom location audit alongside its citation anchor. Existing deduplicated
nodes are not rewritten. Whole-assertion revision rules, source fences and
certificates remain unchanged. This does not repair pre-existing mixed nodes,
prove general extraction correctness, or guarantee a separately extracted
acknowledgment node. The precise contract is in the candidate's
`docs/specs/transcript-revisions.md`.

Freeze the backend source/image, plugin/protocol and all helper identities before
execution. Require the four new mocked-provider-to-real-storage/prefix-refusal
tests, all existing revision tests and the ordinary-retirement ownership test,
strict Clippy and formatting, a fresh image/configuration observation, fresh
plugin and real-host checks, and private search/context preflight. Distinguish
private exact-source validation from hosted PR merge-candidate validation. Full
hosted backend checks must pass before final acceptance. No production deployment.

Use the unchanged phase-7 scorer, fixtures, six scenarios, expected answers,
models, recall defaults, capture/job/mirror/latency gates and source collection.
After probes, independent source review must additionally inspect every collected
`extraction_normalization` audit: only the terminal unqualified attribution was
removed, all prefix content remains, the captured source remains intact, and no
audit claims to rewrite an existing reused node. Any uncertainty or material
content loss fails acceptance. Preserve all existing per-UID history-exemption
proofs and complete retirement/source-review gates.

Run only `phase8-development-1`, followed by `phase8-confirmation-1` and
`phase8-confirmation-2` on the same immutable candidate, each requiring 6/6 and a
passed independent source review before the next reservation. A failed input,
execution, score or source review closes this phase. No unchanged rerun,
rescoring, substitution or paid diagnostic is allowed. Only after both fresh
confirmations may the unchanged real-Hermes seed/new-session pair run; the normal
successful path is two calls, with the existing diagnosed replacement rule and
four-call maximum unchanged. Successful actual-agent acceptance is terminal.

Carry all prior reservations without refund. Append a phase-8 extension binding
the failed phase-7 diagnosis and prior entry IDs. Raise cumulative ceilings by
one suite to **fifteen suites, 90 suite jobs, 210 suite rows and 103 reviews**.
The eighteen newly reserved suite reviews plus at most four agent captures fit
81 + 18 + 4 = 103. Keep the **$22 review-stage planning allowance**: carry
$20.312248 and add the six newly allowed Sol reviews at the same planning rate,
$1.507836, for **$21.820084**. This remains an estimate excluding extraction,
embeddings and Hermes calls, not a measured bill or hard spend cap. Retain actual
provider telemetry. Independent protocol review and immutable final preflight
must clear before paid ingestion. Qualification remains limited to these warmed
private functional scenarios.
