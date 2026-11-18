# Whole-answer private Hermes qualification

Phase 6 failed at B-probe and is closed. Broader acceptance was not established. The [earlier capture-only runs](CAPTURE-ONLY-ACCEPTANCE-2026-11-18.md)
remain failed and closed. Phase 5 demonstrated a correct individual recalled
context and answer but failed its literal answer gate and did not qualify probe
capture. This successor does not rescore it.

Candidate manifest: `0c60f43f1dcb04996aea276a94491f5a27f2c0aedae6b8b70da7d293b24c5981`.
The [prospective protocol](../../evals/WHOLE-ANSWER-ACCEPTANCE-PROTOCOL.md) freezes
the whole-answer contract before new calls.

## Scope and unchanged runtime

Core `1a59daee38519224cf33f6e7a97ab1ba14fec37f`, Cloud
`c1812793e29cb7de91633a058f60f2d8351c04e2`,
Hermes `ae1ff71c39d8527227400c8e71acf9c57a8a59c6`, plugin
`f5d964ba21c79a39f9e02f056e21bd80e12b1efc`. This is the private acceptance branch,
not published plugin 1.3.0. No package publication or production rollout is included.

Two fresh profiles use a reused private graph. Models, prompts, relevance filter,
context scorer, three-second recall bounds and source/capture gates are unchanged.
The supported empty CLI toolset remains active; catalog GETs remain distinct from
the single zero-tool generation per stage. Old cold measurements concern their
older source/configuration/graph only; there are no new cold trials.

## Changed answer contract

Automatic text validation establishes only that an answer is nonempty and bounded;
it does not establish semantic truth. Every probe requires an independent whole-
answer review against the approved ordered seed/correction user turns. The review
must affirm the current property, account for every historical/rejected-value
clause, and reject conflicting current facts, uncertainty, reversed corrections,
unrelated projects and unsupported additions. The verifier binds the complete
answer, source quotes/framing, actor/profile/uploader and correction certificates.

An exclusive finalizer permanently closes a failed review. Interrupted finalization
cannot allow progression or replacement, and probes retain the exact correction
approval they used. Terminal acceptance requires six runtime passes plus four
finalized independent source reviews, including B-probe, unchanged accounting and
successful pinned CI.

All 127 offline checks passed, including real CLI integration and review-lifecycle
regressions. Independent blind calibration agreed on 28 development fixtures;
the observed phase-5 answer is a development positive. This is not held-out
performance, efficacy evidence or a retroactive pass for phase 5.

## Budget

Prior consumption: ten CLI invocations, eleven owned jobs and ten review reservations,
plus two historical direct-tool invocations. Historical missing provider usage
remains unknown. Six new CLI/job/review slots give cumulative ceilings of 16 CLI
invocations, 17 jobs and 16 review reservations. CLI counts are not provider-request
counts, and the review-only planning allowance is not a measured total bill.

## Result

A-seed, A-correction and A-probe passed their runtime gates and both required
independent source reviews. A-probe recalled five relevant items and answered
with the current five-bullet format, explicitly rejecting the old prose format.
Outer recall took 0.307850 seconds; engine recall took 0.306750 seconds.

B-seed and B-correction passed. Independent source review supported five certified
retirements of obsolete $8,000 assertions and preservation of the budget-free
Entity and correctly framed historical Summary.

B-probe failed the unchanged current-assertion context gate: all five recalled
assertions were obsolete $8,000 facts, correctly marked retired. The $12,500
replacement appeared only in supersession labels. The model answered $12,500
correctly, but that does not rescue missing current-assertion coverage. Outer
recall took 0.704977 seconds and engine recall 0.704037 seconds. Independent
review confirmed a valid context failure, not an answer-instrument false rejection.
The selected-item trace does not alone identify which ranking/filter step omitted
the stored current Claim.

Owned probe job `d26ff66b-19ae-41f7-b2ab-d123d58b4099` was cancelled; provider
telemetry remains unavailable. Probe capture/source effects are unqualified.
All six slots were consumed: cumulative totals are 16 CLI invocations, 17 owned
jobs and 16 review reservations, plus two historical direct-tool invocations.
No retry, replacement, refund or rescore is permitted. Earlier failures remain
closed. A completed A sequence does not establish broader two-scenario acceptance.

| Preserved evidence | SHA256 |
|---|---|
| B/probe/result.json | `35b6e48e762c653cec35dc81eb52c70b5692d54af5831c280ec822b3e2aa1a0a` |
| B/probe/score.json | `c7cce4c5679f259fd1d7b3783884735110c05c8c58f2af945294ae96017061b8` |
| B/probe/messages.json | `1863f15b761dfd5a7a5041f8b31c9d7634c16625b5217c20cf1db499d06efb41` |
| B/probe/trace.json | `7608ca47bfdb273047a14560cf064b66b4d36c491c38bb68ca980cee6a75c6fa` |
| B/probe/model-requests.json | `9d23f35b39f635a788b6d1540e96c26bbccfcbb8b7ccd3619d09dfd6ac75c30e` |
| B/probe/accounting.json | `53c60d98f798583452f2a245ce93a68d50955f0c5c14bab7571be736b96f8fe1` |
| B-probe-terminal-accounting.json | `c7bba55d2cbeeaaa0a315ac30b72fdaff2ff3af2dff17c1efa421a5f94c1c8dd` |
| budget.json | `aca956096388d6234ce58b2e12e1e655cce88a47025bc4e54c805e0ded3f2e1e` |

