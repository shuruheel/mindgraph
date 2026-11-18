# Author-ID quantity guard: private Hermes qualification

**Phase 3 failed and is closed.** The correction invoked explicit memory tools
despite the prompt, violating the capture-only conditions. The preceding [phase-2 failure](ACCEPTANCE-2026-11-18.md)
remains closed; a correct answer did not excuse its stale injected Preference.
This successor uses the [prospective protocol](../../evals/AUTHOR-ID-ACCEPTANCE-PROTOCOL.md)
and preserves the same prompts, scorer, models, latency bounds and failure gates.

## Candidate

Core `1a59daee38519224cf33f6e7a97ab1ba14fec37f` ([merged PR206](https://github.com/shuruheel/mindgraph-rs/pull/206)) recognizes only a complete,
verified author ID in a leading attribution when checking asserted quantities.
Original evidence and factual-amount checks remain intact. The candidate also
integrates main's turn-held identity-choice and document-deletion fixes; any live conclusions concern this complete candidate and cannot establish isolated causality.

Cloud runtime source remains `c1812793e29cb7de91633a058f60f2d8351c04e2`.
Plugin integration candidate remains `f5d964ba21c79a39f9e02f056e21bd80e12b1efc`,
Hermes `ae1ff71c39d8527227400c8e71acf9c57a8a59c6`. This is not qualification of
published plugin 1.3.0. No production rollout or package publication is included.

## Offline evidence

Independent source and protocol reviews are READY. Exact-candidate remote tests:

| Group | Passed |
|---|---:|
| Source identity | 4 |
| Revision storage guards | 21 |
| Revision selection, decoding and writes | 60 |
| Document deletion | 8 |

These cover the observed three Preference aliases and atomic Concept, conservative
quantity boundaries, actual-turn identity/support combinations, invalid-response
refusal, and both document-deletion orders. Installed runtime identity and independent preflight passed before live calls. Exact-candidate CI run
44263744167, attempt 1, subsequently reached terminal success; macOS was skipped.
The source merged as `f9e0e266331ea608e467d9d304995185c986639f` after release review.
This establishes source-delivery readiness, not successful live acceptance.

The earlier `3e93a12` candidate passed CI and 58 focused revision tests. An
intermediate `c5eaf9c` test fixture reused identical old/new turns and produced
59 passes/1 failure. The successor changes only that fixture, distinguishes the
turns and explicitly proves support eligibility. Neither intermediate was deployed
for phase 3 or consumed its model-call allowance.

## Live scope and limits

Two fresh profiles use the existing private graph. This is a reused graph, not
an empty-data experiment. At most six serial Hermes calls test preference and
budget correction; any failure closes the run. Independent source review gates
both probes. Invalid-answer completion remains a failure even if extraction
reports a completed job.

Phase 3 consumed two Hermes calls, two owned jobs and two review reservations.
Cumulative consumption is six calls, seven jobs and six review reservations,
plus two direct tool invocations outside the job ledger. The four unused phase-3
calls are forfeited; no unchanged retry or substitute probe ran. Earlier cancelled-job, Wiki and embedding-timer
usage remains unknown. No new cold trials are included, and the earlier cold
results belong only to their earlier source/configuration/graph state.

## Closed live result

Manifest SHA256: `7baa71498b0e260bf3bf1c6e7bb3fd420b7950f465d7091a5616b04f441a33cd`.
Installed image: `sha256:8b826ac7b24e188d15dc93a5e5c806724f1c957fe20bf51c2c97897e2c29565e`.
Installed binary: `41a03c36ba00996d04c7db3d040467c0cf8abe5478cc3973d1f22980e2fc0722`.

A-seed passed with two captured rows, one delivered batch and a clean extraction
job (`b6487e96-12ae-4e58-a280-c74915b2d7ed`). A-correction used a distinct new
session but produced six messages: the user, two tool-call/response pairs, and
`Noted.`. The assertion “session contains prior or extra conversation” therefore
identified extra tool interactions, not demonstrated session reuse.

`mindgraph_reason` supplied a descriptive string as `supersedes_uid` and received
404 (“resolution target not found”). `mindgraph_remember` then reported an
inserted, embedded node `2098d2a3-94b3-4168-acb0-e47dca5317de`. Prompt wording
alone had not enforced the intended zero-tool environment. The owned gateway
stopped; extraction job `ed69c458-3c94-4f5e-ac55-c6ac73c032ae` was cancelled.
A read-only lookup after cancellation confirmed the independent direct-tool node
remained present. Capture cleanup did not reverse that write. Its provider telemetry remains unavailable, so reported
`review_requests: 0` is not evidence of complete zero usage.

No probe or B stage ran. No clean correction, author-ID fix acceptance or recall
success follows. Independent failure review confirmed these limits. A successor
must enforce Hermes tool selection and qualify that changed configuration before
new live calls; this run stays closed.

| Preserved evidence | SHA256 |
|---|---|
| Failed correction result | `aaf928f9f6cbeec62a8e91adbb2fe5dc50debdcca4ed0adff1539336bf97cc66` |
| Actual messages | `d8bbae9500724c7c3a2f476bde144e090a844744c0a3c11deb79216ce4d83a89` |
| Terminal accounting | `ce76785f577fa48bc724deabc44f82a4203d5b8d3ab2a142b09610a6c79d694a` |
| Closed ledger | `eac92e51601ac6128358f909de7a676bb1d1d274b7efcfb2aac3408cf57dc376` |
