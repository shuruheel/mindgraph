# Recreated private Hermes lab — 2026-11-18 UTC

**Phase 2 failed and is closed.** Its first recall probe injected an obsolete
Preference as current. The two earlier cold readiness trials passed independent
review. This report does not reopen closed
phases 10 or 11, or claim a new six-scenario suite result.

## Candidate and scope

The owner authorized recreating the deleted private Fly lab. Both machines
have dedicated volumes and no public services. The backend has its own graph;
authentication and organization metadata use the existing control plane.

| Component | Tested identity |
|---|---|
| Plugin integration candidate | `f5d964ba21c79a39f9e02f056e21bd80e12b1efc` |
| Hermes | `ae1ff71c39d8527227400c8e71acf9c57a8a59c6` |
| MindGraph core | `c34ce2140a8791a70027ac7bd055694a712986ae` |
| Cloud | `c1812793e29cb7de91633a058f60f2d8351c04e2` |
| Mnestic | `c3571877fff959e7dc0556022c2d1298638e9e2f` |
| RocksDB | `986b8b9f20893dec811d8ecdb97b6a47f20d322d` |
| Phase-2 manifest SHA256 | `957f8c1c5f5831a7c88302033c6c7f6c51d0e007b9099815a0409e5dd6bf69b6` |
| Protocol SHA256 | `32c5485c083c2e2c8ae20c87e46dbad39793960c122614b94b03bae70a2b70c5` |
| Backend binary SHA256 | `c29e6e96b0ecfeeddc12f0acc7f594a40574635c34fc9f3f3b1c301207518173` |
| Backend image digest | `sha256:7a19dc8a9e62fff31f440d8808d6f01265ba3499ed90ae09fb2b5f0eaeb2ecd2` |

This evidence belongs to the integration candidate above. Plugin 1.3.0 was
released separately; these results do not qualify that different source tree.
No plugin runtime/version change or production rollout is part of this report.

Backend: iad, performance-2 CPU / 8 GB / 30 GB volume. Hermes lab: iad,
shared-1 CPU / 1 GB / 3 GB volume. Runtime: Python 3.14.0, SQLite 3.53.4,
SDK 0.17.0. Hermes uses `gpt-6-luna` through OpenAI Responses, reasoning none;
transcript review uses `openai/gpt-6.1-sol`, medium reasoning, strict schema,
4096 output tokens. Extraction uses four `anthropic/claude-haiku-5.5` passes
and `qwen/qwen3.6-plus`; embeddings use `text-embedding-3-small` (1536).

The private backend enables required-tenant warming, attributed transcript
revision for the authorized uploader, and disables embedding keep-warm and
automatic Wiki compilation. Actor binding uses captured profile and author
framing, not an operator-supplied single-user override. This scope is not
transport-level speaker authentication.

## Cold readiness

Cloud PR [258](https://github.com/shuruheel/mindgraph-cloud/pull/258) makes
required private tenants open and warm before readiness. Direct requests
receive `503/server_warming` with `Retry-After: 2` during that interval.
Smoke mode also suppresses the scheduled paid embedding timer.

Two measured trials passed, with all builds stopped and no concurrent extraction:

| Trial | Dispatch marker to ready | First context request | First text search |
|---|---:|---:|---:|
| 1 | 3.375 s | 1.006 s | 0.020 s |
| 2 | 2.955 s | 0.428 s | 0.019 s |

Both observed the required 503, a replaced process, matching ready identity,
and the exact fixture facts/UID. Marker transfer overhead preceded restart by
0.450 s and 0.545 s respectively and is included in the conservative ready
interval. The queries passed the unchanged three-second bound.

These are two observations on the small recreated graph, before Wiki was
disabled and before current conversation captures. Phase 2 inherits them;
it does not claim fresh cold tests under its later configuration/graph state.
The deleted 161k-node clone cannot be compared, so no large-graph speedup or
latency-distribution claim follows. Core's compact type-index backfill has
source/unit evidence, not a measured large-graph improvement here.

## Actual Hermes result: terminal stale-preference failure

| Stage | Result | Evidence |
|---|---|---|
| A-seed | Input gates passed | Two rows, one delivered batch, one clean extraction job, answer `Noted.` |
| A-correction | Runtime and independent source gates passed | Two additional rows, one clean job, answer `Noted`; exact Claim retirement and Entity summary-edit certificates |
| A-probe | **Failed** | Corrected context and answer were present, but an old Preference was also injected as current |
| B sequence | Not run | Terminal ordering gate stopped progression |

The correction certificates connect this profile's actual, distinct attributed
seed/correction turns. Exact source hashes, role spans, actor bindings, endpoint
versions and retirement directions passed independent review. No uncertified
Supersedes edge was found. Three Preference aliases and one old Concept remained
live; the review recorded that risk before the probe. The reused graph supplied
five different-project memories during seed recall, so this was not a clean-graph
experiment, although the correction certificates bind the intended project.

Probe recall took 0.300168 s at the outer manager and 0.299163 s at the engine.
Five items included the correctly superseded old Claim, updated Entity, new
Claim, a withdrawal Preference and an **unretired old Preference** requiring
long-form prose. The actual answer requested a five-bullet summary and explained
that it replaced prose. That answer does not override the failed context gate;
the answer-specific gate was not reached. No rescore or replacement probe ran.

The source review diagnosed a deterministic eligibility defect: all four old
aliases contained `uid:10000` in their summaries. The quantity parser read its
suffix as scalar `10000`; the owning user message correctly excluded its author
header and therefore contained no such factual amount. Those pairs were excluded
before finite model targets were constructed. The old Claim lacked that numeric
ID in the scanned fields and could be retired. Preferences and atomic Concepts
were already supported types. The report's `excluded_candidates=5` counts an
earlier admission step and is not the diagnostic count for these aliases.

The owned gateway stopped. Probe job `a94553d2-cf72-459c-90b7-59e1cbc68eea`
was cancelled; its telemetry remained unavailable. Original and later terminal
accounting are retained as incomplete, not zero usage. Phase 2 consumed three
Hermes calls, three job reservations and three review reservations. Combined
with the earlier failed seed: four Hermes calls, five owned jobs, four review
reservations. Two phase-2 extraction jobs completed cleanly; the correction
reported one Sol review (8,710 input / 677 output tokens). Probe review usage is
unknown. Consumed reservations remain in the ledger; the unused phase-2 allowance was
forfeited at closure. The earlier unused cold reservation remains separately
recorded.

Core [PR 206](https://github.com/shuruheel/mindgraph-rs/pull/206) addresses this
eligibility defect with a narrow author-reference exemption and adversarial
regressions. It is a successor candidate requiring its own checks and live
qualification; it does not change this result. Cloud readiness
[PR 258](https://github.com/shuruheel/mindgraph-cloud/pull/258) merged as
`9d0500e82b65c5b690dbce2335996ee40dd3c232` after independent reviews and green
checks. Its final documentation-only head `ef6d1a7` has the same runtime source
as the tested `c181279`.

## Preserved failures and changes

1. The initial fixture's automatic embedding failed with a stale credential.
   The key was corrected using the authorized benchmark repository. The old
   scheduled embedding timer had incomplete accounting, including a brief
   valid-key interval. Its historical attempts and cost remain unknown.
2. One reserved vector refresh succeeded, but its harness gate incorrectly
   required `GraphNode.embedding_ref`. That failed record stays failed. A new,
   independently reviewed read-only check of the authoritative stored embedding
   passed: 1536 finite values, nonzero norm, same fixture UID. No second refresh.
3. The first cold instrument missed the 161 ms warming window. It remains
   failed, with its unused second reservation consumed. A prospectively reviewed
   100 ms health timeout / 25 ms polling instrument reserved two new trials;
   both passed above. Four cumulative cold reservations, three executed.
4. The earlier actual-Hermes seed captured cleanly but spawned an unexpected
   Wiki job. The phase failed; the child was cancelled and its provider usage
   remains unknown. No correction/probe ran. Phase 2 prospectively disabled
   automatic Wiki compilation and used new profiles/project codes. The graph
   was reused and retained the failed seed's nodes.

Smoke job receipts are process-local unless persisted. The policy restart made
old jobs return 404. Archived completed/cancelled receipts plus the verified
process replacement establish the recorded lifecycle; 404 alone does not.
Cancellation cannot prove that an upstream provider call never ran.

## Evidence and limits

Raw private artifacts are retained beneath
`/Users/shuruheel/Code/mindgraph/.worktrees/hermes-followup-2026-11-17/evidence/`
and on the lab volume. They include exact source documents, framing hashes,
certificates, retirement endpoints, normalized exclusions, manager traces,
messages, queues, job telemetry, manifests and independent reviews. Shared
or private graph contents are not published in this report.

The [frozen protocol](../../evals/RECREATED-LAB-PROTOCOL.md) defines stage
ordering, terminal failures and immutable scoring. The closed phase-2 protocol allowed at most six
calls/jobs/review reservations; together with the failed prior seed, its ceilings
are seven Hermes calls, eight owned jobs and seven review reservations.
The $2 planning allowance covers only six new transcript reviews, not the
whole test bill. Hosting, Hermes generation, extraction and embeddings are
separate; historical Wiki and timer usage prevents a complete measured bill.

Automatic Wiki child ownership/linkage, scoped observability/cancellation and
provider telemetry remain separate backend lifecycle gaps. Disabling the
feature in this lab does not fix those platform behaviors.

## Selected immutable artifact hashes

| Artifact | SHA256 |
|---|---|
| A-correction source | `3fe196a0d780a0b9df9c7e09dcda3650e0d24e1e801825842c84e7dca3ff881b` |
| A-probe score | `4abd2d211afc1405aae6d7721433dacf82a577118f97da325825402992577f8a` |
| A-probe original accounting | `3cc3e04569ec21e4816f3b4cdabe9ca2b382b017e0c9c0fca8a863ee88431947` |
| A-probe terminal accounting | `41e991cf252c3495f3bb1ad11df3787032030bdc89424d4cd6758f13bc23f7f7` |
| Closed phase-2 ledger | `50d7c0831509a99f066c1fe54d9a4adbf405e736f5fd575da690a3d3f7bb8047` |
| Cold trial 1 | `2053a30cda5522109672cf1a694c067d84744aec6bb11d62f1722941a6be4496` |
| Cold trial 2 | `f0cbc52544b329e91c692f87a9177269f0a35479fb1dde445abe56dd9e0bc90c` |
