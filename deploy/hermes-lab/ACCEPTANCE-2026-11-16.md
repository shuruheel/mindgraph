# Broader private acceptance — 2026-11-16 UTC

**Phase 9 passed the frozen broader private functional acceptance protocol.**
Independent protocol and actual-Hermes contract reviews passed with no blocking
findings within this scope.
Qualification is limited to the warmed private functional scenarios in the
[frozen protocol](../../evals/LIVE-ACCEPTANCE.md), with the actual-Hermes
capture/new-session recall gate described below. This is not production
qualification or a general extraction-quality result.

## Qualified candidate

| Component | Immutable identity |
|---|---|
| Plugin | `716f9d808239558c46108dfd242116ffcd4fbd2e` |
| Hermes | `ae1ff71c39d8527227400c8e71acf9c57a8a59c6` |
| MindGraph core | `60a62d2f48a710f8f73be8c71ecb68e40a24bd28` |
| Cloud wrapper | `d486836c8c9817a2475a5da8d3bad4e844d513b2` |
| Mnestic base | `272c7b7196de9acd8d4aa66ec3e6e2f10f0057ea` |
| Private Mnestic formatting-only patch SHA-256 | `3783395372d04bd233502c569c35c4829e21b277539b4603eb00e05b0b41dbd2` |
| Backend image digest | `sha256:3d0337df3e125c0e88cd9c02708277b97bf25395caa3dcd9fce39078273527a7` |
| Running backend binary SHA-256 | `d73d14a8a034b9bb95c71bc2a629ba142cf94a24701203c4a922d85b6b557575` |
| Candidate identity | `693b00880417d92904fff9fa547b611fa77d7f5260e4b3cc8db19aa0072b11ea` |
| Protocol SHA-256 | `066d8c579f81b90fdaab8a6d91ac851ec74a851e4ba50d4cffed02925fc6bc0f` |
| Frozen scorer fixtures SHA-256 | `f7a0ec2ddacc08912b2eab1c576e6e40bdc7f25f9f5b42c8e5051a1c2800cc50` |

Later documentation commits do not change the runtime candidate above. The
backend revision prototype is opt-in and deployed only to the private repair
app. Hosted CI used the clean Mnestic tag; the private build retained the
reviewed three-file formatting patch. Both provenances are preserved.

## Three fresh suites

| Run | Score | Delivered rows | Clean completed jobs | Maximum recall |
|---|---:|---:|---:|---:|
| Development `639a20` | 6/6 | 14 | 6 | 1.311 s |
| Confirmation 1 `2e4b83` | 6/6 | 14 | 6 | 1.395 s |
| Confirmation 2 `a15c18` | 6/6 | 14 | 6 | 1.558 s |

These scripted capture/recall suites used the same candidate and passed independent review of complete
source assertions, framing hashes, actor/provenance bindings, endpoint versions,
retirement certificates, exact Entity summary edits and retained history.
Together they contain 13 certified retirements, three certified summary edits,
eight explicit correction-history exclusions and no uncertified collected
retirements. No historical-scoring exemption was needed. No attribution
normalization audit occurred, so that branch has no positive live coverage here.

Confirmation 1 had a session-open timeout. The plugin retained all four parts
and delivered the same batch through its built-in retry; final evidence contains
the intact transcript, a clean job and no undelivered rows. There was no manual
rerun. Successful remember/delete receipts identify the same UID in each suite;
unrelated-query and post-deletion probes returned no recalled items.

## Actual Hermes conversation pair

Run `actual-hermes-acceptance-rqnw12ms` used OpenAI Responses `gpt-6-luna`,
reasoning disabled, three-turn/90-second run limits and a 120-second outer
deadline. The model name is an alias, not an immutable provider snapshot.

The seed supplied the service window and mascot for fresh code `OrionB73D60`.
Hermes replied `Noted.` without tools. Both transcript rows were delivered and
the extraction job completed cleanly before the probe; the capture gate took
25.6 seconds. A distinct session then asked for the facts without supplying
their values. Automatic memory injection included both, and Hermes answered:

> Service window: Tuesday 09:40 UTC. Mascot: copper badger.

Both sessions had exactly one user and one assistant message and no tool calls.
The observed probe engine recall took 0.685 seconds; the entire observed
MemoryManager prefetch took approximately 1.217 seconds, within the three-second
deadline (outer duration from observer wall-clock timestamps; engine timer monotonic).
These are memory timings, not total model response latency. The harness checked
native `MEMORY.md`/`USER.md` for test-fact contamination; a subsequent read-only
inventory found no such files outside plugins in the exact run profile.

This is fresh-session recall in a reused private graph. The seed recalled nodes
from the previous failed pair's different codename, and the shared current-task
header remained available. It is not a clean-graph or general isolation test.
The saved probe transcript capture was sealed without a submission receipt;
only the seed's completed extraction was required and established by this gate.

**Real-host correction reconciliation remains unqualified.** Actual Hermes
supplied author-attributed user framing with `plain_user=false`; backend
revision review explicitly reported `skipped_unsupported_source_or_identity`.
The pair proves capture and automatic recall, while the correction suites
exercise the supported plain-user framing. A profile UUID does not authenticate
a speaker. Supporting real-host corrections needs an explicit identity contract
and a separate live correction test.

The first pair's seed remains a failed execution: the parent-only observer
missed Hermes's gateway process, although the conversation and capture worked.
A reviewed observer fix propagated into the actual gateway, retained original
return/exception/deadline behavior, and passed five unpaid observer tests, six
budget tests and a gateway startup handshake. The single permitted replacement
pair then passed. The failed seed remains counted; it was not rescored. No third
pair or further model calls followed the successful pair.

## Checks and evidence

The exact plugin candidate passed 537 unit tests locally and remotely, 33
real-Hermes host tests, lint/version checks and all hosted workflows. The core
passed 45 revision tests, the saved failure replay, retirement ownership and
four attribution tests, plus [full hosted CI](https://github.com/shuruheel/mindgraph-rs/actions/runs/43773412530).
The backend image was built from the pinned source and its running binary hash
verified. A Fly builder cleanup deadline happened after successful image export;
the successful build log and deployment verification are retained.

Raw graph evidence and runtime configuration stay private. On the lab volume,
suite roots are under `/data/runs/`:

- `20261115T232815Z-phase9-development-1-w7n7hh0m`
- `20261115T233858Z-phase9-confirmation-1-pw51a5qq`
- `20261115T235126Z-phase9-confirmation-2-ovwnatpq`
- `actual-hermes-acceptance-_xs52kj1` (failed original seed)
- `actual-hermes-acceptance-rqnw12ms` (successful replacement)

Frozen inputs and observer correction evidence are under
`/data/acceptance-artifacts/phase9-716f9d8/`. Local copies are retained in the
isolated acceptance worktree's `evidence/` directory. Each suite has its raw
report, manifest, provider usage, revision evidence and independent source review.

| Artifact | SHA-256 |
|---|---|
| Development report | `a29ff1477b8b11f7746b6df545fcb70cb2f5445deac7c950eea47cf0979f7316` |
| Confirmation 1 report | `f39450ca659697e3387e6c123be4e5802c930976265908bdc6c43260baa1a2f5` |
| Confirmation 2 report | `c0466b8c60f84ba9b633de4324be67a4f22b6311a78d16f295a0b5899af7d5b1` |
| Replacement pair manifest | `14db54d648392f0b10d9c5b348c57e59781d3eb8d085a736f4d6eb77fe5b705c` |
| Raw replacement prefetch trace | `cfd326e3aa68bf857b0ab2e98811abd854cd00f154413b6e85284241c80edeaa` |
| Final reservation ledger | `33f54d140b6c212912b4b2a0ca1e576b69a64c70d687b5fd051f52d988f6ad0e` |

All earlier failed runs and reservations remain unchanged. The final ledger has
26 entries and 114 reserved reviews, below the 115-review ceiling. Three actual
Hermes invocations were used, including the failed seed. The $25 review-stage
planning allowance carried an estimate of $24.835756; neither number is a
measured bill or hard spending cap, and both exclude extraction, embeddings,
Hermes calls and hosting. Saved provider telemetry is the usage evidence.

## Remaining work

1. Define trustworthy Hermes author/profile binding before enabling source-backed
   correction for real author-attributed turns; preserve refusal until qualified.
2. Address cold startup/search latency: the private preflight's first text query
   took 70.441 seconds. Warm functional success does not qualify cold recall.
3. Investigate the earlier cross-project Concept dedup provenance case and
   qualify attribution normalization and discovery beyond bounded candidates.
4. Integrate the core prototype with current main on a new candidate and qualify
   it before any production rollout. [Core PR #167](https://github.com/shuruheel/mindgraph-rs/pull/167)
   has a later-main merge conflict; [plugin PR #11](https://github.com/shuruheel/mindgraph/pull/11)
   remains draft. No new release or production prototype deployment is included.

The [November 14 progress record](ACCEPTANCE-2026-11-14.md) and
[initial smoke record](VALIDATION.md) remain historical evidence.
