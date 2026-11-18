# Phase 10 private requalification — 2026-11-16 UTC

**Phase 10 failed and is closed.** Its only suite, `phase10-development-1`
(run `3ce76b`), scored **5/6**: `corrected_fact` failed. All input gates passed.
Under the [frozen protocol](../../evals/LIVE-ACCEPTANCE.md), no confirmation
suite or actual-Hermes pair ran, and nothing is rerun or rescored. Core PR #167
at `629e4d3` is therefore **not** requalified. The phase-9 result for core
`60a62d2` ([record](ACCEPTANCE-2026-11-16.md)) stands unchanged.

## Candidate

| Component | Immutable identity |
|---|---|
| Plugin | `716f9d808239558c46108dfd242116ffcd4fbd2e` (unchanged) |
| Hermes | `ae1ff71c39d8527227400c8e71acf9c57a8a59c6` (unchanged) |
| MindGraph core | `629e4d3c92e4cbcfebcf09dea9c1f89a0d850d09` (phase-9 core + `fe300fb` + main through `86080cc`) |
| Cloud wrapper | `facc6f8e68046df4040457aa75c4837f8ac8cf9d` |
| Mnestic | `c3571877fff959e7dc0556022c2d1298638e9e2f`, clean archive, no patch |
| Backend image digest | `sha256:3c8ffa0c20d3a5f468af8ad8cf75a3d9ac48a37dc33a3d98f31ca20fac25e9f5` |
| Running backend binary SHA-256 | `0b0e270bf22393ebbb8aea8c826946561f348b4e3bfd0caaf2447f93d6ff5141` (build `20261116-184007`) |
| Backend manifest SHA-256 | `3be078477d2696326adc0e50694111c08bf2e03db91bee8cca349a319290c9de` |
| Candidate identity | `cb6b93dc8567452fdf5fd76a32dc56303bd660f812d6630ca18f0833289f9999` |
| Protocol SHA-256 | `b36d886420f9618b431f6d14862a2f88f86e857923166a64c711cffd3db72718` |

Only the private machine's image changed. Its environment, guest, volume and
absence of public services were identical to phase 9. The new optional settings
(attributed-author bindings, context source default, search reindex, usage log,
agent sweep archive) were verified unset in the running process.

## Gates before the paid run

- Hosted CI [run 43899054036](https://github.com/shuruheel/mindgraph-rs/actions/runs/43899054036)
  on the exact head passed (macOS test skipped by the workflow).
- The Fly remote build compiled clean archives of the three pinned commits. Its
  focused tests passed from the same source: 46 revision and history tests (4
  ignored), the saved phase-5 replay, retirement ownership, and 4 attribution
  tests. After the image export, flyctl reported a builder-release deadline, as it
  did in phase 9. The deployed binary hash matches the build.
- On the lab: the doctor check passed, 537 plugin unit tests passed (33 skipped),
  33 real-Hermes host tests passed, and the 20 phase-10 budget helper tests passed.
- Private preflight returned results on the text and vector legs. A cold first
  text query took **70.1 s**, as in phase 9 (70.4 s). The hybrid query took 0.50 s
  and the context query 0.17 s.
- Independent protocol, contract and final-preflight reviews were all READY with
  no blocking findings. The contract review confirmed four things against
  `60a62d2`:
  - Sole supersession ownership is unchanged.
  - Ordinary edges still cannot carry revision evidence.
  - The review budgets and fences are unchanged.
  - Unset author bindings admit nothing.

## Development run `3ce76b`

| Scenario | Result | Items | Recall |
|---|---|---:|---:|
| preference_change | pass | 5 | 1.474 s |
| corrected_fact | **FAIL** | 5 | 1.363 s |
| interrupted_work | pass | 5 | 1.666 s |
| cross_session_decision | pass | 5 | 1.241 s |
| unrelated_project | pass | 0 | 1.671 s |
| deletion | pass | 0 | 1.411 s |

All 14 rows were accepted, nothing was left undelivered, and all six jobs
completed. Recall p50 was 1.442 s and the maximum 1.671 s.

The failing recalled item was an epistemic-pass Claim, displayed as:
`Zephyr3CE76B pilot approved budget (superseded) [CONFLICT: unresolved] — The approved budget for the Zephyr3CE76B pilot was initially stated as $8,000, a figure later corrected by the user.`

The independent failure review classified it as **supported history outside the
frozen `historical-budget-rejection-v2` grammar**. The grammar does not accept
the clause `, a figure later corrected by the user`. The review found no
reconciliation defect in the scored item:

- The only node asserting $8,000 as current was correctly certified as retired
  and was not recalled.
- The review correctly declined to certify the three mixed-history nodes.

It attributes the failure to ordinary extraction wording variance, the same
class as phase-7 `a4a07a` and phase-8 `6e15fe`. The telemetry gives no sign that
main's wrong-target filter or cross-pass ids touched it. One sample cannot rule
out a shift in wording from main's prompt changes.

The review's non-blocking findings:
- The recalled $12,500 Constraint's single provenance anchor points at the
  $8,000 turn. This did not affect certification.
- An unrecalled project Entity keeps a stale "long-form prose" summary. It was
  never a review target.
- The historical $8,000 figure is typed as a Preference and as a hard
  Constraint, although both display as history.
- The source edge behind the `[CONFLICT: unresolved]` marker was not in the
  collected evidence.

The other five scenarios were source-correct, with four certified retirements in
total.

## Usage and ledger

Saved job telemetry shows:
- **Revision review** (stage `transcript_revision`, `openai/gpt-6.1-sol`): 3
  requests, 33,462 input and 1,965 output tokens.
- **Extraction:** `anthropic/claude-haiku-5.5` 24 requests (147,518/16,729
  tokens); `qwen/qwen3.6-plus` 6 requests (65,547/5,272 tokens).

These figures do not include embeddings, preflight queries or hosting. No
actual-Hermes model calls ran.

The ledger now has 27 entries: 18 suites, 108 jobs, 252 rows and **120 reserved
reviews**, under the phase-10 ceilings of 20/120/280/136. The development entry
is `failed_acceptance`, with its failure review recorded. Final ledger SHA-256:
`d5f34e95533fca218a5257efed906d3270c27b0f7a14faf12a2f1bc50ecb571f`.

## Evidence

| Artifact | SHA-256 |
|---|---|
| Report | `f258f47a00175284ea4cdba1f7fc5e2000c58ddc5d0852786a4e9105f7e4df66` |
| Revision evidence | `6ae2f8e90ae4f8ba40cdc460a58ec3ddcdb3410cb20ac9fa7366194385d7e703` |
| Run manifest | `c8633b08f093dd88afafe24108a09a6f8c30ba42cd2e94f8b023044ee8fac2b0` |
| Failure review | `9b879b4e6daa989aff6085464897d7bf6f3444f0ce638a20dfc86dbc88f6135b` |

Paths on the lab volume:
- Raw run: `/data/runs/20261116T192553Z-phase10-development-1-yti5xv75`
- Validation, helpers and final ledger copy: `/data/acceptance-artifacts/phase10-629e4d3/`
- Local copies: the acceptance worktree's `evidence/`

## Private backend state

The private repair machine `84ee145a23e748` is **started** and now runs the
phase-10 image above, not the phase-9 image. To roll it back, POST
`evidence/private-config-phase9.json` (phase-9 image
`hermes-history-60a62d2@sha256:3d0337df…7a7`, same environment) to that
machine through the Machines API. Then reinstall the phase-9 backend manifest as
`/data/backend-acceptance.json` from
`/data/acceptance-artifacts/phase10-629e4d3/prior-backend-manifest.json`.

## What this leaves open

- Requalifying #167 needs a new, explicitly preregistered phase. A changed
  scorer or extraction would be a new instrument or candidate, not a rescore of
  `3ce76b`.
- Every issue from phase 9 remains: real-host author binding, cold search
  latency, and the attribution/dedup questions.
