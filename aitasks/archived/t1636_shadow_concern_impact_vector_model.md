---
priority: high
effort: high
depends: []
issue_type: enhancement
status: Done
labels: [shadow, aitask_monitormini, concern_format]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
created_at: 2026-08-30 11:21
updated_at: 2026-09-01 09:54
completed_at: 2026-09-01 09:54
---

## Problem

The shadow agent's review procedures (plan-challenge, impl-challenge, plan-assumptions,
plan-diagnose-errors) classify every concern on a single, undefined `high/medium/low`
scale. This has become the binding constraint on the whole review loop, and it gets
worse as the shadow runs on stronger models:

- **Severity is undefined.** No rubric anywhere states what high/med/low measures
  (impact? likelihood? effort? which quality attribute?). `plan-challenge.md` and
  `impl-challenge.md` just say "severity (high / medium / low)". The user seeing
  `high` cannot tell *on which dimension* it is high.
- **The disposition rubric is impl-only.** `impl-review-angles.md` defines
  `blocking/follow-up/informational` well (anchored to the task's obligations —
  AC, plan goal, existing behavior), but the three plan-review producers emit no
  disposition trailer at all, so every plan concern lands in the picker's
  "Needs addressing" bucket undifferentiated.
- **The concern's type axis is deliberately erased.** The discovering angle
  (edge cases, plan deviation, reuse, conventions…) is "discovery context only"
  and never carried into the emitted concern.
- **Non-convergence is structural.** The auto-recheck loop
  (`review_loop.py::compose_recheck_prompt`) injects "re-run the review
  sub-procedure end to end" each round — every round is a fresh unbounded search
  over an ill-defined concern space, not a delta check against round N-1. Only
  user-rejected concerns are suppressed. Stronger agents find more concerns each
  round; reviews have been observed not to converge after 10 rounds.
- **Overengineering has no counterweight.** A concern today is a pure demand with
  externalized costs: nothing asks what incorporating the fix would *worsen*
  (complexity, scope drift away from the user's original intent), so accumulating
  concerns silently over-engineers the solution.
- **The decision surface exists; the information doesn't.** The concern picker
  already has per-concern states `forward / rejected / spinoff` (spinoff creates a
  `followup_kind: review_finding` draft task). What the user lacks is the
  information to decide forward-vs-spinoff-vs-reject.

## Agreed direction (from exploration brainstorm)

**A concern is a proposed delta in a shared quality-dimension space.** Each concern
declares a signed impact vector over ONE closed dimension vocabulary — the improve
side and the worsen side draw from the *same* dimensions:

```
… body … Improves: robustness(high), verification(medium). Worsens: simplicity(low). Effort: low. Disposition: follow-up. Verified: PLAUSIBLE.
```

Key design points settled during exploration:

1. **Closed dimension vocabulary** (~6–7 dims, single source of truth module like
   `lib/followup_kinds.py`, one-line rubric each). Draft: `goal` (task AC / user
   intent delivered), `correctness` (right behavior on reachable inputs),
   `robustness` (failure/concurrency/hostile input — stability + security),
   `performance`, `verification` (testability, proof it works), `maintainability`
   (readability, duplication, conventions), `simplicity` (amount of mechanism —
   the classic worsen-side). Open call: merge maintainability+simplicity into one
   "code health" dim, or keep the split so "adds mechanism" stays distinct from
   "hard to change safely".
2. **Only non-zero entries are listed** (most concerns have 1–2 per side), but the
   Worsens side is **mandatory** (even as `Worsens: nothing.`) — forcing the
   reviewer to price its own suggestion is the anti-overengineering mechanism. A
   concern improving only non-obligated dims at a simplicity cost self-identifies
   as a bad trade.
3. **Effort is a separate one-time-cost scalar** (`Effort: low|medium|high`), not a
   vector dimension: quality deltas are permanent properties of the codebase,
   effort is transient — mixing them corrupts both.
4. **Existing fields recast, not discarded:**
   - `priority` becomes derived/summary (max magnitude on the improve side,
     obligation dims weighted) — or is eventually dropped from the marker;
   - `disposition` grounds in the vector (blocking = improve side touches an
     obligation dim per the task's AC/plan goal; follow-up = net-positive but
     non-obligated; informational = no proposed delta / already settled);
   - `Verified:` verdict stays orthogonal (confidence, not consequence).
5. **Plan reviews get the same trailer**, unifying plan-side and impl-side
   classification (today the plan side carries only the bare priority).
6. **Backward-compatible mechanics:** the trailer parses as a terminal sentence
   run in `monitor/concern_parser.py` (`_TRAILER_SENTENCE` alternation + new
   `Concern` fields) — the `- [priority | region]` line format is unchanged and
   old blocks parse exactly as before.
7. **Picker consumes the vectors:** compact rendering per row (e.g.
   `▲robust ▼simpl E:low`), grouping/sorting by trade profile, and explicit
   decision guidance — forward = obligation dims or pure-win + low effort;
   spinoff = net-positive but non-obligated or effort ≥ medium;
   reject = worsens ≥ improves.

## Scope of this task

Design-first, then implement:

- Write the dimension vocabulary + magnitude semantics + a severity/disposition
  grounding rubric as a single source of truth (module + doc section in
  `concern-format.md`), settling the open maintainability/simplicity call.
- Extend the four producer procedures (plan + impl) to emit the impact trailer,
  with the same two-placement rule discipline the existing trailer rules use
  (guarded by `tests/test_concern_parser.py` producer-rule tests).
- Extend `concern_parser.py` (new derived fields, display_body stripping,
  needs_addressing semantics unchanged or vector-grounded) with tests.
- Extend the picker UI (monitor_shared/minimonitor) to render trade profiles and
  the decision guidance.
- Consider (may split to follow-up): making auto-recheck rounds delta-scoped
  (verify prior concerns' status + only report NEW concerns whose improve side
  touches obligation dims) so the loop converges by construction.

## Non-goals / risks noted at exploration

- Annotation burden per concern (accepted: only non-zero entries, 1–2 per side).
- LLM magnitude calibration is noisy — named dimensions still beat an unnamed
  scalar; magnitudes are advisory, dimensions are the load-bearing part.
- Vocabulary must stay closed (framework-semantic, like `followup_kinds.py`) or
  the parser/UI break.

## Key files (from exploration)

- `.claude/skills/aitask-shadow/concern-format.md` — format source of truth
- `.claude/skills/aitask-shadow/plan-challenge.md`, `impl-challenge.md`,
  `plan-assumptions.md`, `plan-diagnose-errors.md` — producers
- `.claude/skills/aitask-shadow/impl-review-angles.md` — disposition rubric home
- `.aitask-scripts/monitor/concern_parser.py` — parser (trailer extension point)
- `.aitask-scripts/monitor/monitor_shared.py`, `minimonitor_app.py` — picker
- `.aitask-scripts/monitor/review_loop.py` — auto-recheck (convergence angle)
- `tests/test_concern_parser.py` — producer-rule guards
