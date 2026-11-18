# Current-assertion private Hermes qualification

Candidate `1004f92bddc10ef7ae6ae90e2d885de18f4307a54f46c3d956f1f93204bb3f99`
is **failed and closed**. The [prospective protocol](../../evals/CURRENT-ASSERTION-ACCEPTANCE-PROTOCOL.md)
preserves the failed [phase-6 result](WHOLE-ANSWER-ACCEPTANCE-2026-11-18.md).

## Source and gates

Private plugin `8bb05d61d3bfe33881514ad9f19eac63737eaef3`, Hermes
`ae1ff71c39d8527227400c8e71acf9c57a8a59c6`, core
`1a59daee38519224cf33f6e7a97ab1ba14fec37f`, Cloud
`c1812793e29cb7de91633a058f60f2d8351c04e2`. This includes unreleased changes
beyond published plugin 1.3.0; no package publication or production rollout.

The new selection admits actual current successor nodes before related history,
under the same item/character limits. It does not construct facts from status labels.
The integration also updates MCP 0.29 explicit context/instruction contracts.
The automatic capture-only profile, models, prompts, context scorer and independent
whole-answer/source contract remain unchanged. Two fresh profiles reuse the graph.

Validation before freeze: 586 local tests passed, 35 real-Hermes host tests passed,
135 helper tests passed, and all exact-source hosted checks passed. Contract and
protocol/orchestration reviews were independent. Installed tracked-file hashes are
verified before each stage and at terminal acceptance.

Pre-freeze failures remain recorded: missing offline fixture profiles; an obsolete
host-test instruction heading; concurrent offline CLI timeout/incomplete host
receipt; and a local profile transfer's extra newline. The final checks ran
sequentially. The transfer repair changed no JSON/profile content and occurred
before any manifest, ledger or live call existed.

## Result

A-seed passed. A-correction's conversation and transcript delivery completed, but
mandatory backend revision processing failed while reading its provider response:
`Failed to read JSON: Connection reset by peer (os error 104)`.

Job `d41def12-2c48-4100-84d3-31bbe651e149`, document
`b08bd071-0e13-4e2a-9b46-a4f765dc7013`, ended `completed_with_errors`, with
`processing_status: partial` and one failed chunk. All five extraction layers
reported no failed passes; the separate revision stage failed. Eight nodes and
39 edges were created before failure. No rollback or correction correctness is claimed.

Both conversations had one tool-free generation and exactly two messages. Four
cumulative rows reached two delivered batches; native memory was empty. The owned
gateway stopped. No probe or B stage ran. The successor-selection fix therefore
has neither a passing nor a failing live probe in this run. Independent review
confirmed the closed failure and these limits. Correct answers cannot rescue
incomplete capture processing.

The available backend log window no longer contained a matching failure event or
provider request ID. The evidence does not identify which provider, proxy or
network component caused the reset. An offline reproduction subsequently verified
that the exact adapter reports this body-reset error without silently retrying;
it does not establish that the transport fault was fixed.

## Limits and accounting

The protocol planned two warm functional scenarios; execution stopped during
A-correction before either sequence completed. This is not efficacy research or
a latency distribution.
No new cold trial or large-graph speedup is claimed. Prior failed phases remain closed.
This phase consumed two CLI calls, two owned jobs and two review reservations.
Cumulative consumption is 18 CLI / 19 jobs / 18 review reservations, plus two
historical direct tools. Four unused stage allowances are forfeited. The failed
revision request had zero returned responses and no reported usage; its zero
telemetry token fields mean unknown usage/cost, not zero charge. Terminal receipt
coverage (`incomplete: false`) does not mean complete billing telemetry. Historical
unknowns remain unknown; reservations are not provider requests or a total bill.

Evidence SHA256:

- Manifest: `1004f92bddc10ef7ae6ae90e2d885de18f4307a54f46c3d956f1f93204bb3f99`
- Closed ledger: `cfb8ad240b6e1c154945d4edafdb871c1a996457cba1a9b3d2d190aa289a909b`
- Correction result: `2b751a9c191922589ff5e2c354bee4d60f595b6d5f1f86e35e8cc597ba548cde`
- Capture gate: `cabd217e7524064100656d1957382c13d601ad055ba1a013454558eda6ac3fb8`
- Correction and separate terminal accounting: `61bea1a4121980dd5451610e3268c509238b13750a659093c72041b3743b8c20`
