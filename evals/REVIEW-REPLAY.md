# One-call review diagnostic after ea1780

The four live development results remain failed: d2b302 (4/6), 05a4d6,
5d4704 and ea1780 (each failed input gates with no recall probes). Phase 2 is
closed. No confirmation or actual-agent invocation has been consumed.

This is one read-only replay of ea1780's saved review evidence, not another
capture/ingestion suite or acceptance score. Use core 26de2931dab3eebb48234a51d279854893c38118's
unchanged RULES and Rust validator. Change the review model from
`openai/gpt-5.4-nano` to `openai/gpt-6-luna` through OpenRouter Chat Completions.
Keep temperature 0, JSON-object output, 4,096 output tokens, reasoning disabled
and provider sort `throughput`. Preserve raw request/response, returned model
and provider identity, finish reason and usage. Do not retry, repair the response,
change the prompt after inspection, or write any proposed revision to the graph.

The original per-process random fence nonce was not retained. The reconstructed
request uses one fresh, recorded nonce with the same framing and evidence; it is
not claimed to be a byte-identical original wire request. No oracle information
is added to the model prompt.

Frozen request SHA256:
`ba7fa5c6e3d65dc24e81282cc0d410be6561bf51075cd7192b371a4ee2534b24`.
Frozen oracle SHA256:
`61245000606aba9649861bdef85d7bff95cda99c3f0a296e9fc9e72a8dde66f7`.
Private artifacts: `/tmp/hermes-revision-workspace/luna-diagnostic/` locally,
with the request, oracle and reservation archived on the lab's persistent volume
before the call. Preserve a hashed test-only harness patch that calls the
unchanged Rust validator on the original and replay responses.

Success requires all of the following, frozen before inspecting the response:

- Normal `stop` finish reason, no truncation, and unchanged Rust validation.
- Source-supported retirement of all five old Preference/Claim targets:
  `4ca9a004-b917-4a02-8066-d1ee91e35253`, `9b13bffd-ed09-4e1b-af10-260785caecd8`,
  `a189a802-053c-49fb-b465-29d1cc8314ec`, `c5da67b7-292e-46d3-a264-3574ba3b9f89`,
  and `fce28356-7008-47a3-9cc8-0a370bb56f80`.
- A valid exact-span summary correction for Entity
  `62d53112-1506-4e28-adaa-a42ac74e3b89`, preserving identity and unrelated text.
  Its `current_chunk=true` flag does not make its old prose summary current.
- No revision endpoint for assistant-only acknowledgments
  `b981a04e-33cc-4437-83cf-8692fa7117c2`, `ec06840f-cd77-41ca-81df-1d836e9b9503`,
  or `62c3db15-ce70-4628-a163-a5d466b8efb5`.
- Independent source-backed coverage review, not merely a validator pass.

Add exactly one diagnostic review reservation, raising the cumulative review
ceiling from 34 to 35; suite/row/job ceilings remain 6/84/36. Retain all prior
reservations with no refunds. Failure terminates this diagnostic. Success may
support a separately preregistered phase 3; it does not authorize an automatic
suite retry or establish broader acceptance or general model superiority.

OpenRouter's 2026-11-14 [Luna listing](https://openrouter.ai/openai/gpt-6-luna)
reports a 2026-09-22 release, $0.10/$0.50 per million input/output tokens, and
$0.20/$1.00 for its higher-priced listed Fast route. The existing conservative
300,000 input plus 4,096 output-token allowance estimates at most $0.064096 for
this diagnostic at that higher rate. Keep the $3 review-stage planning allowance;
it excludes extraction, embeddings and Hermes calls and is not a measured bill.
