# Phase 11 private requalification — 2026-11-16 UTC

**Phase 11 failed and is closed.** Its only suite, `phase11-development-1`
(run `3a95d4`), scored **5/6**; `corrected_fact` failed again. All input gates
passed. Under the [frozen protocol](../../evals/LIVE-ACCEPTANCE.md), no
confirmation suite or actual-Hermes pair ran, and nothing is rerun or rescored.
No further scorer change was made within the phase. Core PR #167 at `629e4d3`
remains **not** requalified. The phase-9 result for core `60a62d2` stands, and
phase 10 stays closed at 5/6 ([record](ACCEPTANCE-2026-11-16-phase10.md)).

## What changed: scorer v3

Phase 11 followed the owner's ruling to accept the `3ce76b` history wording.
Scorer `historical-budget-rejection-v3` (`evals/run.py`) keeps every v2 form and
the v2 noun-label rule, and adds exactly two complete summary forms:

- **Appositive:** `<v2 first clause naming OLD>, a figure|value|amount
  [later|subsequently] corrected|superseded|replaced|retracted [by the user|by a
  correction|by the user's correction]`.
- **Before the correction:** `[The] [approved] budget for [the] CODE pilot was OLD
  before the|a|the user's correction`.

The calibration fixtures grew from 48 to 62 cases (SHA-256
`5baa62a0a7431a6f47336d0ecbbe12b50851cfe9887b9221b7e93eacb200b633`).
- **New history case:** the exact `3ce76b` assertion now counts as history.
- **New failing cases:**
  - a bare $8,000;
  - "(later revised)";
  - "corrected?";
  - hedged, negated, present-tense, trailing and questioned appositives;
  - a missing replacement answer;
  - a separately recalled current $8,000 Claim.

Results on the plugin candidate:
- Local suite: 557 passed (33 skipped); ruff clean.
- Hosted `test` and `version-guard` passed.
- Hosted `contract-drift` failed because released mindgraph-mcp 0.27.1 differs
  from the checked-in 0.27.0 snapshot. That is an external drift monitor, not
  affected by this candidate.

An independent reviewer, given only the code and fixtures, reported READY:
- **Stale figures still fail:** a stale figure recalled as current fails, as its
  own item, in a label, in a present-tense summary, or after a history clause.
- **Breadth:** the change is "no broader than stated". The reviewer ran 47
  adversarial probes and found no over-acceptance.

## Candidate

| Component | Identity |
|---|---|
| Plugin | `af1990eeeea9a543d5a8a280c3209bddc2353da9` (v3 scorer, plus main's Hermes #13 governance message, merged so hosted CI could run) |
| Hermes | `ae1ff71c39d8527227400c8e71acf9c57a8a59c6` |
| Backend | the unchanged phase-10 image `hermes-integration-629e4d3@sha256:3c8ffa0c…25e9f5`; binary `0b0e270b…5141` re-verified on the machine |
| Backend manifest | `4aac0f4c608fc3dd42c3af5df62fe615f597bce3450734d854e3a211ce5b3498` |
| Candidate identity | `97470fb5ac21e78df7a5bbf68fd2e1d57fa87323e0b76d1a9d485b65d8aff1e4` |
| Protocol SHA-256 | `aaa3c5c92998e0960b1d6f7be21befaee518717a5ce178f1c23de170dc2c77f3` |

The lab image was rebuilt with `PLUGIN_REF=af1990e`. On the lab, 557 unit and 33
real-Hermes host tests and 20 budget-helper tests passed. A preflight on the
warm backend returned results from both the text and vector legs. The
independent final preflight review was READY.

## Development run `3a95d4`

| Scenario | Result | Recall |
|---|---|---:|
| preference_change | pass | 1.680 s |
| corrected_fact | **FAIL** | 1.863 s |
| interrupted_work | pass | 1.458 s |
| cross_session_decision | pass | 1.226 s |
| unrelated_project | pass | 1.467 s |
| deletion | pass | 1.559 s |

All 14 rows were accepted, no batches were undelivered, and all 6 jobs completed.
Recall p50 was 1.513 s and the maximum 1.863 s.

The failing item was a recalled Claim:
`Zephyr3A95D4 pilot approved budget (superseded) — The approved budget for the Zephyr3A95D4 pilot was initially stated as $8,000, later corrected by the user.`

The independent failure review (SHA-256
`0c015afe25c705cc06a19069f600ddb13af80c2427149f8ab4d15336cf1acb15`) found the
item to be supported history that is not current. Its wording falls outside v3,
because the appositive lacks its noun ("a figure"). The review found no
reconciliation defect in the scored item:
- The only $8,000-as-current Claim was certified retired and was not recalled.
- The mixed-history nodes were correctly left uncertified.

The review also recorded these non-scoring findings:
- A provenance defect on a passing scenario: the stale prose Constraint carries
  an extraction edge from the chunk that negates it.
- Duplicate ExtractedFrom edges.
- Four of the five recall slots went to $8,000-history variants.
- The review search hit its limit, so the candidates it omitted are unknown.

## Usage and ledger

Saved job telemetry shows:
- **Revision review** (`transcript_revision`, `openai/gpt-6.1-sol`): 3 requests,
  35,781 input and 2,728 output tokens.
- **Extraction:**
  - `anthropic/claude-haiku-5.5`: 24 requests, 147,367 input and 16,867 output
    tokens.
  - `qwen/qwen3.6-plus`: 6 requests, 65,514 input and 4,805 output tokens.

No actual-Hermes model calls ran.

The ledger has 28 entries: 19 suites, 114 jobs, 266 rows and **126 reserved
reviews**. The phase-11 ceilings were 21/126/294/142. The development entry is
`failed_acceptance` with its failure review. Final ledger SHA-256:
`a3362c1b38c0178372cf5f662f110e5ca265af6cf9dafb964face38159625ce8`.

## Evidence

| Artifact | SHA-256 |
|---|---|
| Report | `49ee6153b23a959d6c84644bfdfb0e263610645d95a76633f8e42501597ddf4f` |
| Revision evidence | `d4a44bbcb1e53131a04cc8dd1a599733e0fba4f4bd27ed0f9f0754dbf9c070bb` |
| Run manifest | `dc302d4d408bfbfbf63f29f3a14b981229a137d954d0a0db7da28a0ccdea2eb5` |

Locations:
- **Raw run:** `/data/runs/20261116T204108Z-phase11-development-1-vh892gc5`.
- **Validation, helpers and ledger copy:**
  `/data/acceptance-artifacts/phase11-af1990e/`. The first failure-recorder
  upload had a syntax error and changed nothing. The `_v2` script recorded the
  review.
- **Local copies:** the acceptance worktree's `evidence/`.

## State and open items

- The private repair machine `84ee145a23e748` is **started** on the phase-10
  image. The lab machine runs plugin `af1990e`.
- Across `3ce76b` and `3a95d4`, the remaining corrected-fact failures come from
  the extractor writing open-ended history paraphrases. The bounded-grammar
  scorer keeps missing them. Each run also spends recall slots on mixed-history
  nodes.
- A further phase needs a new decision: either a different instrument, such as
  per-UID source-reviewed history without a wording grammar, or an extraction
  change that stops writing mixed-history nodes. Either would be preregistered
  as a new phase.
