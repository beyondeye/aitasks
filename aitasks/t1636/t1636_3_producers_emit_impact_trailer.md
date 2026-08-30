---
priority: high
effort: medium
depends: [t1636_2]
issue_type: enhancement
status: Implementing
labels: [shadow, aitask_monitormini, concern_format]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1636
created_at: 2026-08-30 14:53
updated_at: 2026-08-30 17:54
---

## Context

Part of t1636 (shadow concern impact-vector model). Extends all four concern
producers to emit the impact trailer, grounds the disposition rubric in the
vector, and gives the PLAN-side producers a disposition trailer for the first
time (today they emit none, so every plan concern lands undifferentiated in the
picker's "Needs addressing"). Depends on t1636_1 (vocabulary) and t1636_2
(parser support — never instruct producers to emit what the parser cannot
read). Parent plan: `aiplans/p1636_shadow_concern_impact_vector_model.md`.

The producers are PROMPT FILES read at runtime. Every load-bearing rule uses
the TWO-PLACEMENT discipline (a bolded pre-emit directive at the head of the
emit step AND an entry in the rules list) — a single placement is a rule the
agent may skip. The round-header and rejection-suppression rules are the
existing model.

## Key Files to Modify

- `.claude/skills/aitask-shadow/plan-challenge.md`, `impl-challenge.md`,
  `plan-assumptions.md`, `plan-diagnose-errors.md` — the four producers
  (the `KNOWN_PRODUCERS` set in tests/test_concern_parser.py):
  - emit the impact trailer: `Improves: <dim>(<mag>), ….` — mandatory
    `Worsens:` sentence (even as `Worsens: nothing.`) — `Effort: <mag>.` —
    plus the existing Disposition/Verified sentences; trailer terminal in the
    body, dimensions from the closed vocabulary only;
  - state that DIMENSIONS are load-bearing and MAGNITUDES advisory (risk
    mitigation `state_magnitudes_advisory_in_producers` — see step 1);
  - state the priority-mapping rule: marker priority MUST equal
    `derive_priority(improves)` (max known improve magnitude; `low` when
    empty) so marker and vector cannot contradict;
  - plan-side producers additionally adopt the disposition trailer, grounded
    in the vector.
- `.claude/skills/aitask-shadow/impl-review-angles.md` — "Disposition rubric"
  section: ground blocking/follow-up/informational in the vector (blocking =
  improve side touches an obligation dimension per the task's AC/plan goal;
  follow-up = net-positive but non-obligated; informational = no proposed
  delta / already settled). The existing impact-vs-obligations rubric text
  stays authoritative; the vector grounding is a re-expression, not a
  replacement.
- `tests/test_concern_parser.py` — new `TestProducerImpactVectorRule` and
  `TestProducerMagnitudeFramingRule` mirroring `TestProducerRoundHeaderRule`
  (line 1364): both placements checked, plus negative controls proving each
  guard can fail. Reuse `KNOWN_PRODUCERS` / `PRODUCER_MARKER` from
  `TestProducerShortRegionRule` (line 1033).
- `tests/test_shadow_disposition_surfaces.py` — add the new enumeration sites
  (SITES list) for any section that now enumerates dispositions.
- `website/content/docs/workflows/shadow-agent.md` (lines ~70 and ~98) — the
  user-facing description of findings and of the concern block gains the
  impact vector.

## Reference Files for Patterns

- `plan-challenge.md` "Also emit the structured concern block" step — the
  existing two-placement examples (round header, rejection suppression,
  short-region rule).
- `impl-challenge.md:393-395` — the example concern lines; extend them with
  impact trailers (keep them inside a ``` fence, never a contiguous
  open→items→close block — t1123).
- `tests/test_concern_parser.py::TestRenderedShadowDocsKeepTheGuarantees`
  (line 1570) — rendered-variant (`fast` profile) coverage comes free once the
  authoring-tree guards exist.

## Implementation Plan

1. FIRST (risk mitigation `state_magnitudes_advisory_in_producers`, from the
   parent plan): add to every producer the requirement that dimensions are the
   load-bearing part and magnitudes advisory, plus the
   `TestProducerMagnitudeFramingRule` guard over `KNOWN_PRODUCERS` with a
   negative control proving the guard can fail.
2. Extend the four producers with the impact-trailer emit rules (two-placement
   each): mandatory Worsens, closed dimensions, effort scalar, priority
   mapping, trailer-terminal placement.
3. Ground the disposition rubric in impl-review-angles.md; give plan-side
   producers the disposition trailer.
4. Add `TestProducerImpactVectorRule` (+ negative control); update
   test_shadow_disposition_surfaces.py SITES; update the website doc.
5. Regenerate any affected goldens in the same commit (skill_verify).

## Verification

- `python -m pytest tests/test_concern_parser.py tests/test_shadow_disposition_surfaces.py`
- `./.aitask-scripts/aitask_skill_verify.sh` before committing.
- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last
  line (`PYTHON SUITE: PASSED|FAILED`).
