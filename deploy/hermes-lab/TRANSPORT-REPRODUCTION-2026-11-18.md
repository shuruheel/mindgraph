# Private Hermes reproduction after a transport failure

**Failed and closed.** Candidate
`a22308f438d7e9974aa25491fb49a3fa4b8f419938470cba2cc9e3f31eacf933`
completed A-seed and A-correction runtime gates, then failed the mandatory
independent correction-source review. No A-probe or B stage ran.

This was the single disclosed exploratory reproduction authorized by the
[prospective protocol](../../evals/TRANSPORT-REPRODUCTION-PROTOCOL.md).
The preceding [transport-failed run](CURRENT-ASSERTION-ACCEPTANCE-2026-11-18.md)
remains failed. Unchanged product behavior was reproduced with fresh profiles
on the reused private graph; this was not a repair of the transport fault or a
measurement of reliability, efficacy or success rate.

## Candidate and checks

Plugin `8bb05d61d3bfe33881514ad9f19eac63737eaef3`, Hermes
`ae1ff71c39d8527227400c8e71acf9c57a8a59c6`, core
`1a59daee38519224cf33f6e7a97ab1ba14fec37f`, Cloud
`c1812793e29cb7de91633a058f60f2d8351c04e2`. Backend instance, configuration,
models, prompt templates and acceptance criteria were unchanged. The plugin's
source changes were merged in [PR #18](https://github.com/shuruheel/mindgraph/pull/18);
this neither published a package nor qualified its live behavior.

The new observer passively recorded the actual responses supplied to recall
selection, including live/cache provenance. It issued no extra retrieval and
preserved original results; its overhead remained in the measured deadline.
Accounting separated request receipts from token-usage and billing knowledge.
All 151 helper checks passed, including actual Hermes CLI stand-ins and the
partial-extraction barrier. The first invocation passed 150 checks and skipped
the CLI because its opt-in flag was absent; that diagnostic was preserved.
Unchanged source retained its 586 unit and 35 real-host passes and successful CI.

A separate build-only diagnostic copied the exact core provider adapter and LLM
types into an isolated harness. Six local TCP controls covered interrupted bodies,
complete malformed JSON and success on both supported API paths. Body resets
produced the same connection-reset error without a hidden retry. This used an
error shim and did not execute the graph writer. Its first build lacked the main
fixture file; both that failure and the successful build were retained. No
provider call or runtime deployment was part of this diagnostic.

Independent contract, protocol, orchestration and installed-candidate reviews
passed before live execution. The frozen manifest bound 74 source inputs,
140 evidence artifacts and 34 helper files.

## Runtime success and source failure

| Stage | Runtime result | Job | Document |
| --- | --- | --- | --- |
| A-seed | Passed | `fd598cd9-948a-403d-9c70-cb44ee4ac490` | `014a4d8d-3097-45d3-a826-51feac612b01` |
| A-correction | Passed | `aad2110d-1c77-4dd3-8e2d-0b146e9d9e9e` | `580bb17d-79ff-4eda-9dde-b452068ddb95` |

Each distinct session had the intended user statement and `Noted.`, one tool-free
generation, and no native-memory facts. The seed also made one permitted catalog
GET. Four rows reached two delivered batches and two clean one-chunk jobs. The
correction made one completed Sol revision-review request.

Five certificates had mechanically valid actor, source-framing, live ChunkOf,
endpoint-version and provenance bindings. Three current-preference/claim
retirements and one exact Entity-summary edit were supported. The remaining
certificate, `ca6102a7-a210-4c54-8c6c-42e43bb2329d`, wrongly retired Claim
`5011dfb1-b3c8-4491-950a-75e1d8050654`, whose summary states:

> Assistant acknowledged the user's preference for long-form prose status reports
> on Project Zephyr0007D7 with the single word 'Noted.'

That historical acknowledgment remains true after the user changes the preferred
format. The certificate cited the seed user turn at bytes 0–163; the actual
acknowledgment is in the separate assistant turn at bytes 165–182. Exact byte
matching does not establish support for the whole assertion or a valid retirement.
Independent review rejected it, and one-shot finalization closed the ledger. The
runtime pass remains recorded separately. The owned gateway stopped; both jobs
were already terminal, so no cancellation or rollback was performed.

The review also found a retained Concept (`613125b9-3365-4b7b-9fff-56d8bc9ee1fa`)
whose summary still affirms the old prose preference alongside a format definition.
This needs representation and coverage work; retiring the valid definition would
not be a safe remedy. Only a decision-reason hash was retained, not its plaintext
rationale. The Entity summary edit also left its original description property
unchanged. Neither observation was measured by a recall probe.

## Follow-up and limits

The backend fix is tracked in [PR #207](https://github.com/shuruheel/mindgraph-rs/pull/207):
remove the review prompt's provenance waiver and conservatively exclude recognized
communication-event assertions, including structured fields and Entity summary
fragments. That source work is separate from this closed run. Existing certificates
are unchanged. The live backend still uses the source pin above.

Broader acceptance has not succeeded. The current-assertion retrieval fix has not
reached its live probe in either of the latest two attempts. No further automatic
reproduction is permitted by this protocol; another qualification needs a new
reviewed candidate and prospective scope after the product gaps are addressed.

## Accounting and evidence

Two new CLI calls, two jobs and two review reservations were consumed. Cumulative
consumption is **20 CLI / 21 owned jobs / 20 review reservations**, plus two historical
direct tools. Four unused stage allowances are forfeited. Five completed revision
responses are now known across the recorded phases; phase7's failed request and
earlier cancelled/direct-tool/Wiki/timer usage retain their unknown tokens/cost.
Reported extraction usage covers these two jobs' recorded attempts. Embedding token
usage and total billing remain unestablished. There were no new cold trials.

Evidence SHA256:

- Manifest: `a22308f438d7e9974aa25491fb49a3fa4b8f419938470cba2cc9e3f31eacf933`
- Closed ledger: `75ff6600a7a904f34b28c288bcda3dc7ba229f63fc877fad7212d8f9531ecb39`
- Correction source: `d7e41b1b3bafd6cf79a7696a989239456b1ccd672287827c976b0b21d82822d9`
- Correction runtime result: `564e7d957fe0745181f969aea939c22101cdc088f6f722de904940826d2e411f`
- Independent failed verdict: `919f3bf2a386b8a5473f13ab22990a7f960b33bc476276ae2003ba504b2f8970`
- Failed review finalization: `8e68cbd363d7fd7950a6ad05bddcc5e3993da1e605c1fae468297c19138cfaf8`
- Separate terminal accounting: `af50eedbd0bf366f0b49aba959c103a190a3535ea7c09bedf1b93ef01eb84146`
- Owned gateway cleanup: `9661ecc19dcc740002e27bfb45efaa981308c8d7104789c520c533e502dcf6a1`
