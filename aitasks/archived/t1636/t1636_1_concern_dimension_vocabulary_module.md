---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [shadow, aitask_monitormini, concern_format]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1636
implemented_with: claudecode/opus5
created_at: 2026-08-30 14:53
updated_at: 2026-08-30 16:19
completed_at: 2026-08-30 16:19
---

## Context

Part of t1636 (shadow concern impact-vector model). Every concern the shadow
emits will declare a signed impact vector over ONE closed quality-dimension
vocabulary (`Improves: robustness(high). Worsens: simplicity(low). Effort: low.`).
This child creates the single source of truth for that vocabulary — the module
every other child builds on. The parent plan
(`aiplans/p1636_shadow_concern_impact_vector_model.md`) records the settled
design decisions; do not re-litigate them here.

Settled decisions consumed by this child:
- 7 dimensions, `maintainability` and `simplicity` kept SEPARATE (extracting a
  helper improves maintainability while worsening simplicity — merging would
  cancel that trade out): `goal`, `correctness`, `robustness`, `performance`,
  `verification`, `maintainability`, `simplicity`.
- Magnitudes `high|medium|low`, advisory; dimensions are the load-bearing part.
- `derive_priority(improves)` = max magnitude over improve entries with a KNOWN
  magnitude; empty/absent improve side or no known magnitudes → `low`. This is
  the single canonical marker-priority mapping (parent plan decision 2).

## Key Files to Modify

- NEW: `.aitask-scripts/monitor/concern_dimensions.py` — the vocabulary module.
  Lives in `monitor/` (not `lib/`) because its only consumers are
  `concern_parser.py` (contractually pure — sibling import only, no sys.path
  insertion; see the try/except import pattern at `concern_parser.py:104`) and
  the picker. No shell consumer needs it.
- `.claude/skills/aitask-shadow/concern-format.md` — new spec section defining
  the trailer grammar, mandatory-Worsens rule, effort scalar, and the
  disposition GROUNDING rubric (blocking = improve side touches an obligation
  dimension per the task AC/plan goal; follow-up = net-positive but
  non-obligated; informational = no proposed delta / already settled). Place it
  beside the existing "Derived fields: disposition and verdict" section.
  IMPORTANT (t1123 hazard): never embed a contiguous open→items→close example —
  the doc is read at runtime into the shadow pane; follow the doc's existing
  inline-sentinel style.
- NEW drift-guard test (e.g. `tests/test_concern_dimensions.py`): the doc
  section and the module enumerate the SAME vocabulary — canonical site plus
  drift guard, never two copies.

## Reference Files for Patterns

- `.aitask-scripts/lib/followup_kinds.py` — the model: dict as canonical order
  (`FOLLOWUP_KINDS` at line 33), derived `frozenset`, per-value tuple, `*_for()`
  accessors, module docstring explaining why the vocabulary is closed/framework-
  semantic.
- `tests/test_shadow_disposition_surfaces.py` — the doc↔code enumeration guard
  pattern (normalize whitespace, anchor to headings, negative controls).

## Implementation Plan

1. Write `concern_dimensions.py`: per dimension — canonical name, one-line
   rubric, short display label, declaration order. Magnitude vocabulary +
   semantics ("advisory; unknown/absent normalizes to '' (unspecified), never
   'low'"). `derive_priority(improves)` as specified above.
2. SHORT LABELS ARE ≤ 5 TERMINAL CELLS (e.g. `goal`, `corr`, `robus`, `perf`,
   `verif`, `maint`, `simpl`). This is a packing constraint, not taste: the
   narrow picker core `▲label? ▼label? E:xx` must fit 21 cells at 24 columns —
   `2·(W+2) + 2 + 4 ≤ 21 → W ≤ 5` with 4-cell effort tokens (`E:lo/E:md/E:hi`).
   The module MUST assert the bound over its own table (import-test time, not
   render time).
3. Identify which dimensions are "obligation dimensions" (used by the
   disposition grounding): `goal` and `correctness` categorically; document
   that robustness/performance become obligation-touching only when the task's
   AC or plan obligates them (the grounding is per-task, the module records
   the categorical core).
4. Write the concern-format.md spec section (grammar, mandatory Worsens —
   `Worsens: nothing.` is priced-as-nothing and is DIFFERENT from an absent
   sentence — effort scalar, grounding rubric, derive_priority mapping).
5. Write the drift-guard test with a negative control (a synthetic doc text
   missing a dimension must fail the predicate).

## Verification

- `python -m pytest tests/test_concern_dimensions.py` (or unittest fallback).
- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last
  line (`PYTHON SUITE: PASSED|FAILED`).
- `./.aitask-scripts/aitask_skill_verify.sh` before committing the
  concern-format.md change.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-30T13:02:20Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-30T13:17:42Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-30T13:19:21Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:57ba84470b00e04d

> **✅ gate:risk_evaluated** run=2026-08-30T13:19:21Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1636_1/risk_evaluated_2026-08-30T13:19:21Z-risk_evaluated-a1.log`
