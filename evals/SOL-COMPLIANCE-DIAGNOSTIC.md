# GPT-6.1 Sol development diagnostic

All four ingestion suites and the four preceding diagnostic phases remain
failed. Preserve their raw evidence and all 29 review reservations. The latest
Luna positive response was structurally valid but semantically incorrect; no
proposed graph mutation was applied. A validator pass is not a coverage pass.

Make exactly two new read-only calls: the same saved ea1780 positive correction,
then the same hypothetical-budget negative, with `openai/gpt-6.1-sol`. Keep the
discriminated schema, review instructions, finite choices, unchanged oracle,
decoder and semantic validator from the preceding phase. Only the model and
its known temperature capability change. Source includes the adapter's omission
of unsupported temperature for this model. Export actual adapter HTTP requests
at a local listener, recording the new fence nonce. The negative fixture also
creates fresh ExtractedFrom edge UUIDs; record those provenance-only changes
while keeping all source facts, node IDs and selection IDs unchanged. Freeze source, validator,
request/evidence/oracle, runner and reservation hashes in manifest.json.

Use OpenRouter Chat Completions, provider-default temperature, strict JSON
schema, require_parameters=true, throughput routing, reasoning disabled and
4096 output tokens. Do not opt into Fast/Ultrafast service tiers. One attempt
per fixture, no retries, repair, prompt tuning or graph writes. Preserve normal
and error responses, model/provider identity, usage, cost and latency. Reject a
response with abnormal finish or reported input above the diagnostic's 75000
token planning envelope; retain any charged usage even for an invalid run.
Both new responses need independent source-backed review. Positive coverage
must include all five old assertions and the Entity summary, excluding every
assistant acknowledgment endpoint. The negative must decline both targets.
Either failure closes this phase; passing only permits a separately frozen
new ingestion phase, not broader acceptance or a general model-quality claim.

Reserve two calls upfront with no refunds: cumulative review ceiling 45 to 47,
31 consumed with 16 qualification reservations untouched. Suite/job/row ceilings
remain 6/36/84. Explicitly raise the review-stage planning allowance $4 to $5.
This phase uses a 75000-input-token estimate for each fixed request (wire body
under 64000 bytes; previous positive use was under 17000 tokens), not the old
300000-token generic estimate. At the higher ordinary route's $2.75/M cache-write
input and $11/M output rates, two calls with 4096 outputs estimate $0.502612.
This is a planning estimate, not a tokenizer guarantee, hard provider spend cap
or total bill; extraction, embeddings and actual-agent calls remain excluded.

The [OpenRouter model page](https://openrouter.ai/openai/gpt-6.1-sol), checked
2026-11-14, dates release to 2026-09-29 and lists standard $2/$10 per million
input/output tokens. Saved endpoint metadata records parameters, route prices,
cache-write premiums and long-context tiers. The fixed model change is a
capacity diagnostic after small-model failures, not a comparative benchmark.
