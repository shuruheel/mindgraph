# Capture-only configuration: prospective real-Hermes qualification

2026-11-18 UTC. Phase 4 is failed and closed after A-seed. Its guard admitted
one zero-tool generation request, then refused two model-catalog GETs and counted
them as additional generation attempts. CLI output was Noted, but later gates
were not reached. Its sole capture job was cancelled with unknown provider usage.
Phase 3's explicit tool calls and persistent direct-write node remain preserved.

## Changed candidate and prior evidence

Keep runtime core 1a59daee38519224cf33f6e7a97ab1ba14fec37f, Cloud
c1812793e29cb7de91633a058f60f2d8351c04e2, Hermes
ae1ff71c39d8527227400c8e71acf9c57a8a59c6 and plugin
f5d964ba21c79a39f9e02f056e21bd80e12b1efc. Core CI run44263744167 attempt1
succeeded and 93 focused tests passed; source merged through PR206. The private
image/binary stay exactly as phases 3 and 4. This is not qualification of plugin1.3.0.

Keep the independently qualified supported Hermes configuration:
`platform_toolsets.cli: []`, taken verbatim from evals/capture-only.yaml.
Automatic provider recall and transcript capture remain active. Real-host tests
must show ordinary provider tools exist, configured tools are empty, and actual
CLI Responses input includes recalled context with no callable tools and exactly
one captured user/assistant pair. Local stand-ins use no paid endpoints.

Helpers-v8 retain per-stage config SHA checks and the HTTPX request guard.
The prospective change permits only empty-body GET /v1/models and GET /models
as model_catalog requests. They are durably recorded separately; at most two
catalog requests are allowed per stage. Only one generation POST /v1/responses
with model gpt-6-luna and zero tools is allowed by the acceptance gate. All other
endpoints/methods, malformed bodies, wrong models and tool-bearing payloads remain
refused before dispatch. Valid request bodies are not changed. Metadata/body hashes
exclude credentials and prompt text. Missing/extra/rejected evidence fails.

Tests must cover both HTTPX paths, malformed requests, catalog body refusal,
unchanged valid bodies, and the ACTUAL CLI with this exact guard installed and
local generation/catalog API responses. Recall must reach the model and one
user/assistant pair must be captured. All request PIDs must match the actual
MemoryManager prefetch process, and stage trace prefixes must remain unchanged.
No previous failure is rescored; catalog classification is fixed before freeze.

## Frozen environment and gates

Bind the exact configuration, helpers, source/runtime pins, tests, protocol,
review receipts, fresh profiles, prompts and orchestration to a new manifest.
Independent contract/protocol review and installed-runtime preflight precede
all paid calls. No backend restart, native build or new cold trial is required.
Existing warm backend uses private volumes, required-tenant readiness, Wiki-off,
embedding keep-warm disabled and the same attributed revision uploader allowlist.
Old cold results concern only their older source/configuration/graph state.

Use fresh root /data/hermes-catalog-aware, fresh A/B UUIDs and project codes
disjoint from all prior phases. The graph is REUSED and includes previous
captures and the phase-3 direct-tool node. Inspect context/source interference.
No previous profile, memory, gateway or session may be reused. Only fresh codes
replace codes in phase4's six exact prompt templates. Author remains uid:10000.

Models unchanged: Hermes gpt-6-luna, Responses, reasoning none, max3turns,
90-second run budget/120-second outer timeout; Haiku5.5 extraction, Qwen3.6-plus
epistemic, text-embedding-3-small1536; transcript revision review
openai/gpt-6.1-sol, medium reasoning, strict schema,4096 output tokens, at most
one review request per job. No model-based diagnostics or model switches.

Serial optional prefix: A-seed, A-correction, A-probe, B-seed, B-correction,
B-probe. Reserve one CLI/job/review slot before each invocation. Any failure or
interruption closes the entire phase. No unchanged retry, replacement call,
rescore, grammar change, ledger reset or refund. Source review gates both probes;
independent A-probe approval gates B-seed; independent B-probe review is terminal.

Unchanged gates from phase3: exactly two messages/rows, one delivered batch and
one clean completed extraction job per stage, distinct sessions, no tool calls,
no native-memory facts or pending capture. Seed/correction answer exactly Noted
with optional period. Source evidence includes one intact supported chunk and
complete known provider accounting. Invalid-answer completion still fails.

Each correction needs a valid certificate connecting its own ordered seed and
correction user turns, actor and exact property/replacement. Independent review
checks every certificate, retirement endpoint, uncertified Supersedes edge,
exclusion, normalization and source version; one certificate does not imply all
aliases retired. Unsupported identity, prompt-budget skip, incomplete review or
semantic uncertainty fails. Existing actor/source/storage refusal guards remain.

Probes use frozen scorer v3 and answer_gate, unchanged conservative historical
exception grammar and per-UID source proof. Both actual outer MemoryManager and
engine recall must be <=3 seconds. Correct answers cannot rescue stale current
context. Observe actual manager return without an extra retrieval. Review probe
capture, native inventory, source effects, semantics and accounting separately.
This is a warm two-scenario acceptance check, not efficacy or latency-distribution
research, a startup speedup, or a new full outcome suite.

## Budget and terminal accounting

Bind closed phase4 manifest5ff601e3..., ledger2d3f77e2..., terminal accounting
228482d8..., and all inherited lineage including phase3 direct-tool effects.
Prior consumption is7 Hermes CLI invocations,8 owned jobs,7 review reservations
plus2 historical direct tool invocations. CLI calls are not provider-request
counts. Cancelled seed/correction/probe, direct-tool provider and earlier Wiki/
timer usage remain unknown. Five unused phase4 slots are forfeited, and old
ledgers remain immutable.

New separate ledger permits at most6 CLI invocations,6 jobs,6 review reservations.
Cumulative ceilings are13 CLI invocations,14 owned jobs,13 review reservations,
4 cold reservations (no new cold trials). The $2 new review-only planning allowance
is not a total bill. Other authorized model/extraction/embedding/hosting costs and
historical unknowns remain separate. New unknown usage or extra jobs/generation
requests invalidates the phase; catalog reads have the explicit bound above.

On failure preserve raw score/messages/request trace, stop only the owned gateway,
discover jobs by exact batch tag without resubmission, cancel only owned
outstanding jobs and collect separate terminal accounting. Cancellation does not
retract provider calls or independent graph writes. Never delete old evidence or
reuse failed codes to make a replacement pass. Any subsequent changed candidate
needs a new prospective protocol, independent review and distinct ledger.

No production rollout or package publication. Source test/document delivery is
separate from this exact runtime qualification.
