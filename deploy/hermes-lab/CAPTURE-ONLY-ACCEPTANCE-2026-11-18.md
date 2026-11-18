# Capture-only private Hermes qualification

Phase 4 failed and is closed. Phase 5 also failed and is closed. No broader
acceptance follows from this report. The earlier [author-ID qualification](AUTHOR-ID-ACCEPTANCE-2026-11-18.md)
remains failed and closed.

## Runtime and scope

Private runtime: core `1a59daee38519224cf33f6e7a97ab1ba14fec37f`, Cloud
`c1812793e29cb7de91633a058f60f2d8351c04e2`, Hermes
`ae1ff71c39d8527227400c8e71acf9c57a8a59c6`, plugin
`f5d964ba21c79a39f9e02f056e21bd80e12b1efc`.
This is the private acceptance branch, not published plugin 1.3.0.

Core source merged through PR206 with 93 focused tests and successful exact-source
CI. The dedicated empty-CLI-toolset profile and real-host integration tests merged
through [plugin PR17](https://github.com/shuruheel/mindgraph/pull/17). These source
merges establish neither live correction-recall acceptance nor a production rollout.

## Closed phase 4

Candidate: `5ff601e30903b8bdeeab59fc6dc3ff4e060bf7911cd94927b4e18acdb8c6b0fe`.
Only A-seed ran. One `POST /v1/responses` used gpt-6-luna with zero tools and
returned `Noted.`. The new guard then blocked empty-body `GET /v1/models` and
`GET /models` catalog requests. Its one-request assertion counted those rejected
catalog reads alongside generation and failed before later acceptance gates.
This was an instrumentation classification defect; the result is not rescored.

All three recorded attempts came from gateway PID5474. That owned gateway stopped.
The sole capture job `ea0cb2dd-87f7-45b1-98b9-181b6bb1c944` was cancelled and its
terminal receipt lacks provider telemetry. Its usage remains unknown, not zero.
No correction, probe or B stage ran. The five unused slots are forfeited.

| Preserved evidence | SHA256 |
|---|---|
| Failed result | `d437dc2da58862e748c6d820e21b3014d249d21c21ab3498258c2496ad19bf92` |
| Request trace | `5ca918a182f64f1f3ea2901ed0aa9c4cc59d336390e1fe956ea599d71e17fc7a` |
| Terminal accounting | `228482d82cee186d210fbe2114d8ad8db9b39c46de0bcbf9454ef0042bfe2a05` |
| Closed ledger | `2d3f77e255b5800414352853de064a93996f469b67102e9e41cb0322c551cedb` |

## Closed phase 5

Candidate: `21f60002754e673467b4ce50250d507b8681d4b05359b8406cd7f4e52bd705a0`.

The [new protocol](../../evals/CAPTURE-ONLY-ACCEPTANCE-PROTOCOL.md) permits and
separately records only empty-body GETs on the two catalog paths, at most two per
stage. It retains exactly one zero-tool generation request, the same prompts,
models, conservative scorer and source gates. Every request must come from the
actual recall gateway. Valid request bodies remain unchanged.

All 89 helper tests passed, including both HTTPX paths and an actual Hermes CLI
with the guard installed, local generation/catalog stand-ins, recalled context
in the actual request and one captured user/assistant pair. An initial offline
fixture missed the private runtime's stricter relevance threshold; the corrected
fixture matches five of eight query terms while its secret recalled phrase
remains absent from the prompt. Runtime, live prompts and scorer were unchanged.
The earlier failed offline diagnostics are preserved.

Prior consumption was seven Hermes CLI invocations, eight owned jobs and seven
review reservations, plus two historical direct tool invocations. Missing
seed/correction/probe, direct-tool, Wiki and timer usage remains unknown. The new
separate ledger permitted at most six additional CLI/job/review slots; cumulative
ceilings are 13 CLI invocations, 14 jobs and 13 review reservations. CLI invocations
are not provider-request counts. No new cold trial or measured total bill is claimed.

Two fresh profiles reused the private graph. The protocol required failure to
close the phase, source reviews before probes and the second sequence, installed
preflight and independent result review. No package publication or production deployment
is included.

### Phase-5 result

A-seed and A-correction passed their runtime gates. Independent source review
confirmed three certified retirements (Preference, Constraint and Concept) and
one scoped Entity-summary replacement between the actual attributed user turns.
The Entity's separate props.description still retained its earlier wording;
summary qualification is not reconciliation of every stored property.

A-probe passed the frozen context scorer with five relevant items and marked
retired prose assertions. Outer recall was 0.211545 seconds; engine recall was
0.210565 seconds. Its answer affirmed a five-bullet summary and then described
that format as replacing the earlier prose preference. The frozen answer gate
rejected the word “prose” regardless of historical framing. Independent review
classified this as an answer-instrument false rejection, while preserving the
failed protocol result. No retrospective pass or completed probe source review
is claimed.

The probe job `20574f28-ae23-4494-8e77-5f059cef3c76` was cancelled with unavailable
provider telemetry; its capture was not qualified. No B stage ran. Cumulative
consumption is ten CLI invocations, eleven owned jobs and ten review reservations,
plus two historical direct-tool invocations. Three unused phase-5 slots are
forfeited, and unknown usage stays unknown.

| Phase-5 evidence | SHA256 |
|---|---|
| Failed probe result | `10726f305de2914732b8c00ba2cb9c6e0c762da89e5776581d6150f8dc86e9ab` |
| Passing context score | `c0ab05711afce4710f921cc0253da772389e6fcd4b2ec85deb1a4ce500a2bad7` |
| Actual messages | `5260a1a96947c2be13871ffa78c3a9825a7e12844b7262fa01bd8bc01b18ea9a` |
| Terminal accounting | `296c115a17df90e24b55da543640da062818c915eb0cafa3103ee2f6b3b1842b` |
| Closed ledger | `fb275e4a787c00a88a57c7163a599cf2db2e48ccdc81b70b0002625b8beec660` |
