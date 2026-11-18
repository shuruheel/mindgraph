# Recreated private Hermes lab: attributed correction and readiness

Prospective qualification, 2026-11-18 UTC. The owner explicitly authorized
recreating the deleted private lab. This is separate from closed phases 9–11
and the never-run gaps-followup design. No old result is rerun or rescored.
No production deployment or graph mutation is included.

## Candidate and environment

Freeze core c34ce2140a8791a70027ac7bd055694a712986ae, cloud
c1812793e29cb7de91633a058f60f2d8351c04e2 (private readiness plus smoke-mode provider-timer suppression),
Mnestic c3571877fff959e7dc0556022c2d1298638e9e2f, RocksDB
986b8b9f20893dec811d8ecdb97b6a47f20d322d, plugin
f5d964ba21c79a39f9e02f056e21bd80e12b1efc and Hermes
ae1ff71c39d8527227400c8e71acf9c57a8a59c6. Freeze image and binary digests,
configuration, helper/source hashes and two freshly generated profile UUIDs
before live calls. Required focused tests, host tests and independent source and
protocol review must pass; candidate CI must pass before final acceptance.

The recreated backend has its own new volume and initially empty graph under
the authorized benchmark organization. It shares authentication/control-plane
metadata but does not use production graph storage. Smoke mode disables shared
background workers. No public services, schedules, alternate replicas or
experiments. Backend: iad, performance 2 CPU, 8 GB, 30 GB volume. Lab: iad,
shared 1 CPU, 1 GB, 3 GB volume. Preserve failures and raw records locally and
on the private volume. Do not claim equivalence to the deleted 161k-node clone.

Current identity policy is MINDGRAPH_TRANSCRIPT_REVISIONS=1 plus the single
authenticated uploader 9e4d554d-6a82-4ef0-b1c1-461167a1d11c in
MINDGRAPH_TRANSCRIPT_REVISION_UPLOADERS. Same-speaker author digests come from
strictly parsed, hash-bound framing; no operator author mapping or SINGLE_USER
flag. Freeze expected actual CLI author uid:10000, explicit is_bot:false.
Uploader/profile/author matching scopes revision; it is not transport speaker
authentication. No flag-off/resume/reprocess is used to release admission.
MINDGRAPH_EMBEDDING_KEEPWARM_SECS=0 is explicitly frozen; the new cloud
source also suppresses this timer in smoke mode regardless of that setting.

Models: actual Hermes uses OpenAI Responses gpt-6-luna, reasoning none, 3 turns,
90-second run budget, 120-second outer timeout. Extraction retains four
anthropic/claude-haiku-5.5 passes and qwen/qwen3.6-plus epistemic pass; default
qwen/qwen3.6-plus; embeddings text-embedding-3-small (1536). Transcript review
uses explicit MINDGRAPH_LLM_MODEL_TRANSCRIPT_REVISION=openai/gpt-6.1-sol,
medium reasoning, required strict schema, 4096 output tokens. Retain current
core bounds: 32 current assertions, 64 candidates, 8 searches of 16 hits,
24k source characters and 64k prompt characters, one intact chunk per source.
No model/provider switch after freeze.

## Readiness qualification

The original setup is closed as failed, without any cold or Hermes trial.
It created fixture UID `5309a5c5-584b-4768-8949-762cff030a74`, but its automatic
embedding returned OpenAI 401 because the workspace credential was stale.
Preserve the failed fixture record (SHA256
`7d694b2fe1164e7280d8c3ba4309be7418844b75a77b2f7d6a70ec8c415f04d0`) and
original protocol. The old backend also scheduled embedding keep-warm calls
outside tenant counters. Their total attempt count and cost are unknown,
including a brief valid-key interval before the timer was disabled. Do not
claim complete historical setup accounting or an overall measured bill.

This amended setup changes the cloud source, disables the timer explicitly,
and uses the verified benchmark-repository OPENAI_API_KEY. Before recovery,
verify the installed credential fingerprint, image/binary/configuration and
catalog authentication. Catalog access alone is not embedding success.

The one reserved POST /embeddings/refresh of that UID completed with HTTP200,
requested=1, embedded=1, failed=0, skipped=0, and no fallback warning. Both
reserved internal embedding attempts remain consumed. Its frozen recovery gate
failed because it incorrectly required GraphNode.embedding_ref to be nonnull.
Preserve that failed record, SHA256
`baea448d716afd709aa03afbdd63f7973289f1324ed21c8b61dbbc662c7c4acb`, without
rescoring. Pinned source review establishes that embedding writes use the
separate node_embedding relation; the node field is not a presence indicator.
GET /node/{uid}/embedding reads that relation and makes no provider request.

This second setup amendment permits only a fresh, exclusive read-only fixture
verification: one GET node and one GET its stored embedding. Freeze the verified
runtime and both failed-record hashes. Require the same live UID/label/summary/
props and a vector with exactly1536 finite values and nonzero norm. A missing,
changed or invalid result fails terminally. No refresh, new node, provider call,
client retry or retrospective acceptance of either failed record. Retain the
separate read-only result and independently approve it before warming/freeze.
Then enable warm-org for this existing tenant. Logs must confirm the provider
timer is not scheduled. The fixture remains the same OrionColdLab Tuesday
09:40 UTC / copper badger Concept. This is setup, not a measured request.

The first candidate a805710ba1209a34f3f6b4fc79dad88a420c25b367a55d903012ff9c7fae8085
closed on its first cold trial: the two-second health request gap spanned a
161.459ms server bind-to-ready interval, so no 503 was observed. It performed no
authenticated graph query or Hermes call. Preserve its failed trial
c5e3b2811e51349d2d6735b8b8dc9cda18d90e5eaf637618fb3b46f25ac91ed2 and ledger
f23d1e3195ca600a7fd3354580fb5ffa3e32a6f0c6893becb09e5db66269856c, including its
unused second reservation. Do not rescore or refund either reservation.

This prospective instrument amendment uses helpers-v4, manifest-cold-v2.json
and budget-cold-v2.json alongside the unchanged old files. Reserve exactly two
new cold trials: four cumulative cold reservations, one previously executed.
Only health request timeout/cadence and attempt telemetry change; require the
same actual503/Retry-After gate and fail terminally if it is missed again.
No artificial delay, backend change or relaxed acceptance. Six maximum Hermes
calls/jobs/review slots remain unchanged; both profiles are still unused and
retain the same frozen prompts/identities. Bind the old manifest, failed trial
and ledger into the new candidate. No cold/CLI execution before revised
independent preflight.

The initial deployment/configuration restart is setup, not a trial. Reserve
exactly two measured restart trials durably before either starts. Run serially
after all builds stop, with no active extraction or background work. Each trial
has 240 seconds from restart request to ready, health polling with 25ms sleeps and a
100ms socket timeout per health request. Record wall-clock start/end and monotonic
elapsed time for successful and failed health attempts; this socket timeout is
not asserted to be a strict whole-request deadline. The remote dispatch marker precedes the actual
restart API request by its transfer cost; retain both timestamps, apply the
240-second bound from the earlier marker conservatively, and report that
orchestration overhead separately. Connection failures during bounded health polling
are recorded; failures on measured requests are terminal. Ignore the old ready
process until a restart transition is observed. During warming, exactly one
unauthenticated POST /search must return 503/server_warming and Retry-After:2;
if the warming window is missed this gate fails, no replacement trial.

After ready the first authenticated graph operation is context retrieval for
"For the OrionColdLab internal test project, what are the service window and
mascot?" with node_limit5, article/chunk/expansion limits0, default relevance.
Require HTTP200, fixture facts in node assertions and <=3 seconds. Then one
text search "OrionColdLab" limit5 must return the fixture and <=3 seconds.
No redirects, SDK retries or additional warm-up queries. Both trials must pass.
Record boot-to-ready separately from ready-to-response, raw responses, machine
configuration and startup timings. This establishes readiness behavior on the
small recreated graph, not boot<=3s or a speedup on the deleted large graph.
The compact backfill change has unit/source evidence; its large-graph latency
benefit remains unmeasured in this qualification.

## Wiki-off configuration phase after the closed seed

The prior candidate2670104fed3a6c6f69bd9c2bb253e49a54ab2bd57fe740b37fa9dde396d666f2
is closed after A-seed. One actual Hermes call delivered two rows and one clean
extraction job, but backend automatic Wiki compilation spawned an unexpected
second job. That job was cancelled; its result has no provider telemetry, so
its attempts/cost remain unknown. Preserve the failed stage and both jobs.
No correction or probe was run in that phase, and no transcript-review provider
request occurred. The controlled policy restart replaces the process-local
job registry; smoke mode disables periodic snapshots and automatic resume.
Bind archived completed/cancelled receipts, verified process replacement and
fresh job GET observations. A current404 is only unavailable history, never
terminal or zero-usage proof; if a job remains visible it must retain its archived
terminal status. No active current private jobs may remain before new calls. Do not rescore or reuse its seed as a passed stage.

The only backend configuration change is MINDGRAPH_WIKI_AUTOCOMPILE=off,
verified to disable both initial and resumed automatic Wiki scheduling. There
is no per-request Wiki opt-out for the plugin to send. Image, source, models,
readiness flags and hardware remain unchanged. Automatic Wiki ownership,
child-job linkage and telemetry are separate unqualified backend lifecycle
work; this qualification does not claim to fix them.

Use new root /data/hermes-attributed-followup, helpers-v5 and a separate ledger,
with two fresh profile UUIDs/project codes and unchanged prompt templates.
The graph is REUSED and contains the failed seed's extracted nodes; fresh
profiles are not a fresh graph. Independently inspect actual injected context
and source bindings for interference. Allow at most six new calls/jobs/review
slots: maximum seven cumulative Hermes calls, eight cumulative owned jobs if
all new captures complete, and seven review reservations. The old seed's
reservation is consumed. Six new transcript reviews retain the $2 planning
allowance; historical Wiki/provider cost remains incomplete.

Inherit the two independently accepted cold results with exact candidate/result
hashes as evidence from the PRIOR configuration and graph state. No new cold
reservation or restart trial is performed in this phase. Do not claim a new
cold measurement for wiki-off or the now-populated graph. The ledger must label
this evidence as inherited, preserve the prior failed agent stage and all four
cumulative cold reservations, and require final installed preflight before
new model calls. All unexpected-job, accounting, source, semantic and terminal
failure gates remain unchanged.

## Actual Hermes correction sequences

After both cold trials pass, use two fresh persistent profiles A/B with random
Zephyr codes, exactly three distinct sessions each and at most six CLI calls.
Prompts, with CODE substituted once before freeze:

A-seed: For project CODE, I always want status reports as long-form prose documents. Reply only Noted. Do not use tools.
A-correction: Change of plan for project CODE: I no longer want prose. Send status reports as a five-bullet summary from now on. Reply only Noted. Do not use tools.
A-probe: For project CODE, how do I want status reports formatted now? Answer using your available context. Do not use tools.
B-seed: The approved budget for the CODE pilot is $8,000. Reply only Noted. Do not use tools.
B-correction: Correction: I misread the sheet. The CODE pilot budget is $12,500, not $8,000. Reply only Noted. Do not use tools.
B-probe: What is the approved budget for the CODE pilot? Answer using your available context. Do not use tools.

Seed/correction answer must be Noted with an optional period. Each call must
capture exactly two transcript rows in one delivered batch, one clean completed
extraction job and one supported chunk. No tools, extra messages, native memory
facts, pending capture or mirror work. Advance only after these input gates.
Use the passive gateway observer: authoritative manager return, exact prompt,
profile/session identity, one prefetch, monotonic outer and engine durations.
Offline fake-server tests exercise all six frozen prompts through the pinned
real MemoryManager; real chunk shape is established only by live job evidence.

Before each probe, independently review all collected source certificates,
retirement endpoints, uncertified Supersedes edges, exclusions, normalization
audits and source versions. At least one valid revision must connect THIS
profile's seed and correction documents, same actor and project, and the exact
report-format/five-bullet or budget/$12,500 replacement. Full source turns are
fetched by UID; current review reports intentionally omit cross-document raw
text. A matching unrelated certificate cannot qualify. Wrong uploader/author,
bots, mixed authors/framing, role-body spoofing and altered/deleted provenance
must remain refused under the offline storage/admission controls.

For correction stages, skipped_prompt_budget, no pair, no eligible assertion,
unsupported identity, incomplete review or semantic uncertainty fails even if
the final answer could be recalled. Current prompt trimming is retained and its
counts recorded; no extra review calls or tuning. Clean seed/probe jobs may
have no pair; a prompt-budget or unsupported-identity skip still fails here.

Probe current answer must appear in the manager's actual context and affirmative
final answer. The 3-second deadline applies to recall only (outer manager and
engine separately); the final answer retains the 90/120-second Hermes limits. Use frozen plugin
scorer v3 and its fixtures; never alter wording rules after observation. Current
stale prose/$8,000 assertions fail. Any historical exemption requires the same
explicit source proofs as phase11, adapted to verified attributed framing and exactly this sequence's distinct
seed/correction documents in that order (not upload timestamps),
plus independent semantic approval. Ambiguous/contradictory answers fail.
After probe capture completes, review every further certificate/exclusion and
answer. A-probe must pass before B-seed. Final B-probe review is terminal.

## Accounting and terminal rules

Separate exclusive ledger. Reserve each CLI/job/review slot before launch;
failed and interrupted reservations remain counted. Max6 CLI calls,6 jobs,
6 transcript-review requests; no replacement, retry, resume or rescore. The
review-only planning allowance is $2 (archived rate 6 × $0.251306 = $1.507836),
not a total bill/cap. Extraction, embeddings (including the preserved failed fixture attempt, bounded recovery and two cold
context queries), Hermes calls and hosting are additional authorized work.
Retain actual job provider telemetry including by_layer.transcript_revision,
failed attempts and usage. Do not claim a measured bill from token estimates.

Always collect receipts, pending batches and already-dispatched jobs on failure.
Reconcile lost receipts by exact owned batch tag without resubmitting. Stop the
owned gateway on failure; cancel only outstanding jobs belonging to this run.
Unexpected extra jobs/chunks/review attempts count as overrun and invalidate the
run even if already billed. Unknown accounting remains incomplete and cannot
pass. No later launch follows a failed/interrupted gate. Failure diagnosis and
any changed candidate require a separately reviewed protocol; no unchanged
sampling until success. Final independent review determines acceptance.
