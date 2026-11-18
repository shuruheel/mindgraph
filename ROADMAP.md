# Hermes memory integration roadmap

Updated 2026-11-18. Source integration, deployment and live acceptance are separate
milestones. The [latest private qualification](deploy/hermes-lab/TRANSPORT-REPRODUCTION-2026-11-18.md)
is failed and closed. Plugin version remains 1.3.0; newer source changes are unreleased.

## Delivered source and validation

- Capture durability, turn attribution, timestamp/framing preservation and real
  Hermes hook/CLI coverage are integrated.
- Current-successor selection and MCP 0.29 tool/instruction contracts are merged
  in [plugin #18](https://github.com/shuruheel/mindgraph/pull/18), with 586 unit
  tests, 35 real-host tests and successful CI. Live successor recall remains unqualified.
- A persistent private Fly lab is available. The current harness passed 151 checks;
  live tests preserve failed attempts, source evidence and bounded provider accounting.

## Priorities before another live qualification

1. **Prevent invalid retirement of communication history.** Backend
   [#207](https://github.com/shuruheel/mindgraph-rs/pull/207) removes an unsafe prompt
   waiver and adds conservative eligibility checks. Complete source checks and
   review before considering a new private runtime candidate. This does not repair
   historical certificates or qualify a deployed backend.
2. **Resolve mixed representation coverage.** A Concept can combine a valid format
   definition with an obsolete user-preference summary. An Entity can retain an old
   description after a supported summary edit. Define which fields assert current
   state, keep definitions/history intact, and test extraction and retrieval together.
   Do not solve this by indiscriminately retiring identities or rewriting source evidence.
3. **Requalify complete correction sequences.** Use a new immutable candidate and
   reviewed protocol after the preceding gaps are addressed. Require six runtime
   stages and four independent source/whole-answer reviews. Keep all failed runs and
   cumulative costs; a correct answer cannot rescue missing context or invalid writes.
4. **Define recovery from incomplete revision processing.** One request failed on a
   response-body reset. The job correctly remained partial, but partial extraction
   writes persist. Specify bounded retry/resume semantics, idempotency and per-attempt
   accounting before implementing or testing recovery. Offline reset controls alone
   do not establish transport remediation.

## Later acceptance and release gates

- Broaden actual-Hermes coverage beyond the two correction scenarios to interrupted
  work, cross-session decisions, unrelated recall, deletion and profile isolation.
- Revisit cold readiness and representative graph sizes on the then-current source;
  older small-graph cold measurements do not establish current performance.
- Publish a package only after its exact source, required checks and intended live
  acceptance scope are qualified. Source merge is not package publication or production rollout.
