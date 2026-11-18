# One disclosed reproduction after a transport failure

2026-11-18 UTC. Phase 7, candidate
`1004f92bddc10ef7ae6ae90e2d885de18f4307a54f46c3d956f1f93204bb3f99`,
failed and is closed. A seed passed. A correction was captured and delivered but
its mandatory revision review failed reading the response body: `Connection reset
by peer (os error 104)`. The job completed_with_errors, with partial graph writes.
Its one failed revision request has unknown token usage and cost. No probe ran.
The four unused stage allowances are forfeited; no old result is rescored.

This protocol explicitly authorizes ONE new exploratory reproduction of unchanged
product behavior, under the user's standing request to continue acceptance work.
It is not a causal fix for the transport failure. Observational helper changes
improve evidence only. Any eventual success must be reported alongside all prior
failed attempts, and establishes neither reliability nor efficacy nor a success rate.
No further automatic reproduction follows a failure of this phase.

## Offline investigation and immutable inputs

The isolated offline diagnostic copies the exact core provider adapter and LLM
types. A local TCP server resets an HTTP200 response during its body. Both API
paths produce the recorded reset error, with one request and no returned response
or usage. Complete malformed JSON and successful responses are separate controls.
The fixture uses an error shim and does not execute the graph or revision writer.
Source inspection shows the mandatory review records the failed attempt and returns
before parsing/applying its verdict; earlier extraction writes are not rolled back.
The real plugin input barrier must reject terminal partial extraction offline.
Existing backend logs lack a retained matching event/request ID, so the responsible
provider/proxy/network component remains unknown. Preserve the initial fixture
build failure (missing main source) and successful six-control build log.

Product pins stay unchanged: plugin8bb05d61d3bfe33881514ad9f19eac63737eaef3,
Hermesae1ff71c39d8527227400c8e71acf9c57a8a59c6,
core1a59daee38519224cf33f6e7a97ab1ba14fec37f,
Cloudc1812793e29cb7de91633a058f60f2d8351c04e2. No backend restart/build/deploy,
model switch, semantic prompt change, scorer tuning or new cold trial. The separate
offline diagnostic image is build-only and is not deployed.

Use /data/hermes-transport-reproduction and helpers-v11. Prepare two new profile
UUIDs and project codes. Change only codes in the six exact prior prompt templates;
retain uid:10000, capture-only configuration and models. The graph is reused,
including phase7 partial writes and earlier direct-tool effects. This is not a
fresh-world study. Inspect all source evidence for interference.

Freeze protocol, scripts, installed helper map, profiles, source pins/tracked hashes,
CI, tests and independent reviews. Reuse successful exact-source plugin/core CI and
real-host/unit checks. Run all helper checks sequentially on the 1 GB lab. Independent
contract, protocol/orchestration and installed-preflight reviews must pass before calls.

## Passive evidence changes

The observer copies each response supplied to the recall selection/rendering method,
with session, query and live/cache source. It returns the original result unchanged,
issues no extra retrieval and changes no selection, timeout or retry policy. Failed
serialization is an observation error; probe acceptance requires this evidence.
Observation overhead remains included in the existing measured outer deadline.
The record is a selection input, not proof of a new network request in a cache path.

Accounting now distinguishes terminal request receipts from token-usage coverage.
A failed request or response without usage leaves tokens unknown/partial; absent
cost telemetry never becomes a zero bill. Existing clean-job and request-budget
gates remain mandatory. These reporting changes do not repair a provider reset.

## Execution, independent review and stop rules

All phase7 acceptance requirements remain unchanged: context scorer v3; complete
whole-answer contract current-and-history-v1; conservative per-UID historical
exceptions; exact original attributed nonbot user turns with framing hashes and
actor/profile/uploader bindings; every correction certificate and exclusion; and
one-shot independent review finalization. Bind unchanged answer_review.py,
historical.py, gates.py, answer_cases.py and review_finalization.py hashes. The
28-case development calibration is reused, not a held-out efficacy result.

Models unchanged: gpt-6-luna Responses reasoning none, max3turns/90s/outer120s;
Haiku5.5 extraction, Qwen3.6-plus epistemic, embedding3small1536; revision review
openai/gpt-6.1-sol medium strict schema4096tokens, at most ONE request/job.
Exactly one zero-tool generation per stage and at most two separately recorded
empty-body catalog GETs; matching gateway PID/home; no other model requests.

Serial optional prefix A-seed,A-correction,A-probe,B-seed,B-correction,B-probe.
Reserve each CLI/job/review slot before execution. Finalize each independent
correction source review before its probe, and A-probe before B-seed. Require
two messages/rows, one delivered batch and one clean completed extraction job per
stage; distinct sessions, no tools/native-memory facts, no pending capture and
known request counts. Seed/correction answers Noted with optional period. Probes
require successful retrieval and both outer/engine recall <=3s; a correct answer
cannot rescue missing current assertions or incomplete capture. Review all source,
certificate, retirement/exclusion and probe capture effects independently.

ANY failure, interruption, unexpected request/job or new unknown request count
closes this phase. No stage retry/replacement, rescoring, ledger reset, refund or
substitute verdict. Stop only owned gateways; discover jobs by batch tag; cancel
only outstanding owned jobs; preserve separate terminal receipts. Cancellation
does not undo graph writes or refund calls. No automatic third attempt is allowed.

Terminal acceptance requires all six runtime passes and four finalized independent
source/whole-answer reviews, exact unchanged evidence, successful pinned CI and
independent final-result review. The claim is completion of these two warm functional
sequences on this source and reused graph, alongside the preceding failures.

## Budget and lineage

Bind phase7 manifest, ledger
cfb8ad240b6e1c154945d4edafdb871c1a996457cba1a9b3d2d190aa289a909b,
and terminal accounting
61bea1a4121980dd5451610e3268c509238b13750a659093c72041b3743b8c20.
Carry18CLI/19ownedjobs/18reviewreservations, plus2historical direct tools. Four
completed prior revision responses are known; phase7 adds one failed request with
unknown tokens/cost. Preserve all earlier cancelled/Wiki/timer/direct-tool unknowns.

At most6 newCLI,6newjobs,6newreviewreservations. Cumulative ceilings24CLI/25jobs/
24reviewreservations;4coldreservations inherited, zero newcold. A new $2 review-only
planning allowance is not total spend. Other authorized model/extraction/embedding/
hosting costs and historical unknowns remain separate. No production rollout or
package publication. Source merge remains separate from live qualification.
