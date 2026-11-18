# Private field-correction qualification — failed source gate

The run is **failed and closed**. A fresh Hermes session recalled the corrected
preference and answered correctly, but ingestion of that probe created incorrect
source anchors and unsupported temporal metadata. A correct answer does not
establish safe memory capture. No B stage ran and no package was published.

## Candidate and completed prerequisites

Frozen candidate:
`309f5b426ff1124ed11add6ddc0b1e163afbd05c1773e9fb7b87475fbcb08ecd`.
The [prospective protocol](../../evals/FIELD-CORRECTION-PROTOCOL.md) is unchanged.

- Core `0abb6551d5a070cc0e889f9f4b67080c20282ad3` was merged in
  [#208](https://github.com/shuruheel/mindgraph-rs/pull/208), including #207's
  communication-history safeguard. Merge: `e1ed7ea603fa228310d838e02eb0934c5b1ed6c7`.
- Hermes `ae1ff71c39d8527227400c8e71acf9c57a8a59c6`, plugin
  `8bb05d61d3bfe33881514ad9f19eac63737eaef3`, Cloud
  `c1812793e29cb7de91633a058f60f2d8351c04e2`.
- Exact integrated source passed 421 core and 1,070 server library tests, with
  one and five ignored respectively, plus Clippy. Hosted CI run `44352470816`,
  attempt 1, passed before private deployment.
- The optimized runtime image digest is
  `e243ca1966639c5e8b73aca15517406cfbcb68cd02b953a19446a34dec7e2bef`;
  installed binary SHA256 is
  `b82e4d997bb7c925e2d4e5bb558c09d716acef08b59db6c4dfba2844e5210ed8`.
- The helper suite passed 168 checks on the pinned Hermes host. Design,
  orchestration and installed-candidate reviews passed. Identifier joining was
  explicitly disabled; existing models, scoring and three-second recall gates
  were retained.

The graph was reused, including previous failed/partial writes. Profiles and
project codes were new. These are functional observations, not fresh-world
efficacy or general reliability evidence.

## Results

| Stage | Runtime gates | Independent source/answer review |
| --- | --- | --- |
| A seed | Passed | Included in correction review |
| A correction | Passed | Passed |
| A probe | Passed | Failed source gate; answer and context passed |
| B seed/correction/probe | Not run | Not run |

The correction produced five supported retirements and one field certificate.
The Entity's summary changed; its label and description remained supported and
unchanged. The historical acknowledgment remained intact. The retired Concept
itself asserted the old preference, so retirement was appropriate in this case.
This run did **not** exercise multi-field editing or repair of a Concept that
combines an obsolete preference with an independent definition; those paths have
offline coverage only.

The probe answered that reports should be a five-bullet summary, not long-form
prose. Its context contained actual current assertions and explicitly superseded
history: five relevant items, zero irrelevant items and 1,696 characters. Outer
recall was approximately 268 ms and engine recall 267 ms, both below three seconds.
The probe left all six approved correction certificates unchanged.

## Why the source gate failed

New Preference `80dff6e6-2ff0-4002-bb12-111af7a07a77` records an explicit
five-bullet preference, but its only collected source edge anchors bytes 0–112 of
the user's question asking how reports should be formatted. That question does
not state the format. Within the probe document, the format appears only in the
assistant's answer at bytes 169–266. A new Observation and an assistant-history
Preference also received incorrect question anchors.

The Observation additionally records `2026-11-19T17:44:40Z`, one day after the
capture, without either turn supplying that future event time. This is a second
source defect, not the sole reason for failure.

Source titles also require follow-up: the corrected Entity renders a seed-document
title even though raw retrieval includes both seed and correction documents. A
retired Claim renders a grouped title from another project while retaining its
correct local chunk. These are lossy node-level selections, not precise citations
for each assertion. They do not invalidate the supported correction or the
correct final answer; the blocking defect is the newly written source attribution.

The source review covered the collected representations, certificates and model
review decisions. Upstream candidate filtering reported 37 exclusions without
individual records; this was not an exhaustive audit of every search rejection
or the whole reused graph.

## Closure and accounting

The failed verdict was finalized once. A-probe's runtime pass remains preserved,
while the ledger marks the source review failed. The owned gateway was stopped;
all three jobs were already completed, so no cancellation occurred. Graph writes
were not rolled back. The unused allowance for the three B stages was forfeited; the three consumed
A-stage reservations remain recorded.

Cumulative consumption is 23 CLI generations, 24 owned jobs and 23 revision-review
reservations, plus two historical direct-tool calls. Six completed revision
responses are known, including this correction's one response; seed and probe
made no revision requests. Historical failed-request usage, embedding tokens and
total cost remain unestablished. The review planning allowance is not a total bill.

Private evidence hashes:

| Artifact | SHA256 |
| --- | --- |
| Closed ledger | `4445fe13a47a4a2dfb2d4238fcc79431c03ae1a8f65e502eb872d7b1fb22b753` |
| Probe source | `f7ff00c8c8a80b22c1d1658d31da0d99b9df4c692c3265f4df57c8395d515966` |
| Failed review | `3c35b85a95291d4a1a792a8848a8279c6230f254a4aac77b4e9c54132efe1092` |
| One-shot finalization | `faf4c7a02439d6f42f26a6132fb3241264c6fb3d1d465e5392ab814a403da2c2` |
| Terminal accounting | `fbd6a491df5ed790d9b392c1ab0e6111e0383eac333b9eedd2480588a97cb09b` |
| Cleanup | `84aa4aae7f177f6367fed1eb8e8da4378418763f3d972ef4f40d05f1cf46c9b6` |

The downloaded helper-test log differs from the locally frozen log by one trailing
blank line; both record the same 168-pass result. They are not byte-identical.

## Next gate

Fix ordinary transcript extraction so a label match cannot manufacture assertion
support or explicit-user attribution; validate temporal metadata separately.
Retain valid assistant history and report source uncertainty honestly. Then use a
materially new reviewed candidate and prospective budget. This closed run cannot
be retried, rescored or completed by launching its remaining stages.
