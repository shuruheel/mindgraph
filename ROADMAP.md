# Hermes memory integration roadmap

Updated 2026-11-18. Source integration, deployment and live acceptance are separate
milestones. The [latest private qualification](deploy/hermes-lab/FIELD-CORRECTION-ACCEPTANCE-2026-11-18.md)
is failed and closed. Plugin version remains 1.3.0; newer source changes are unreleased.

## Delivered source and validation

- Capture durability, turn attribution, timestamp/framing preservation and real
  Hermes hook/CLI coverage are integrated.
- Current-successor selection and MCP 0.29 tool/instruction contracts are merged
  in [plugin #18](https://github.com/shuruheel/mindgraph/pull/18), with 586 unit
  tests, 35 real-host tests and successful CI. One fresh-session preference probe
  now passed answer/context gates; its new-capture source gate failed.
- A persistent private Fly lab is available. The field-correction harness passed 168 checks;
  live tests preserve failed attempts, source evidence and bounded provider accounting.

## Priorities before another live qualification

1. **Fix ordinary transcript assertion admission and provenance.** The latest probe
   created an explicit user preference anchored to a question that never stated
   its value. Label overlap must not manufacture supporting evidence. Validate
   exact source turns, actor/modality and assertion support before persistence;
   preserve valid assistant history. Validate event timestamps separately: the
   same probe invented an unsupported next-day Observation time. Declines must be
   visible, and unanchored records must not conceal unsupported current assertions.
2. **Extend live coverage of the delivered field safeguards.** Backend
   [#208](https://github.com/shuruheel/mindgraph-rs/pull/208), including #207, is
   merged, checked and installed in the private lab. One correction review passed
   with history preserved and an Entity summary edited. The original
   failures included a Concept with a valid format definition and stale current
   preference, plus an Entity with a corrected summary and stale description.
   Offline source/storage tests pass, but multi-field edits and mixed Concept
   repair were not exercised by this live extraction. Broaden that coverage with
   independently reviewed inputs; do not retroactively expand this run's claim.
3. **Requalify complete correction sequences.** Use a new immutable candidate and
   reviewed protocol after the preceding gaps are addressed. Require six runtime
   stages and four independent source/whole-answer reviews. Keep all failed runs and
   cumulative costs; a correct answer cannot rescue missing context or invalid writes.
4. **Support successive corrections through explicit ownership transfer.** The first
   field writer refuses overlapping later corrections rather than overwriting an
   active certificate. Define ordered A-to-B-to-C corrections, duplicate delivery,
   concurrency and source retraction before broadening this contract. Deleting an
   earlier source must not erase a later supported value or restore stale text.
   Qualify this with separate offline lifecycle tests and a prospective live protocol.
5. **Define recovery from incomplete revision processing.** One request failed on a
   response-body reset. The job correctly remained partial, but partial extraction
   writes persist. Specify bounded retry/resume semantics, idempotency and per-attempt
   accounting before implementing or testing recovery. Offline reset controls alone
   do not establish transport remediation.
6. **Render precise assertion provenance.** A node can have several supporting
   documents, and the first rendered title may not support its updated assertion.
   Select the actual supporting source or clearly describe an association; do not
   present a grouped or identity-only source as a precise citation for every field.

## Later acceptance and release gates

- Broaden actual-Hermes coverage beyond the two correction scenarios to interrupted
  work, cross-session decisions, unrelated recall, deletion and profile isolation.
- Revisit cold readiness and representative graph sizes on the then-current source;
  older small-graph cold measurements do not establish current performance.
- Measure field-certificate maintenance scans on representative graph sizes before
  making scale or latency claims about the new lifecycle safeguards.
- Publish a package only after its exact source, required checks and intended live
  acceptance scope are qualified. Source merge is not package publication or production rollout.
