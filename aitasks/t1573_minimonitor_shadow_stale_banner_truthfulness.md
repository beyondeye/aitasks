---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [minimonitor, shadow, tui, monitor]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-08-18 15:26
updated_at: 2026-08-18 17:21
---

## Problem

Minimonitor's continuous shadow-staleness banner (`#mini-shadow-stale`, in
`.aitask-scripts/monitor/minimonitor_app.py`) asserts that shadow feedback is
stale in situations where there is no feedback at all, and keeps asserting it
after the followed agent has moved to a workflow phase in which the old
feedback is moot.

Three observed symptoms, all reported from live use:

1. The banner appears **before any concern was ever created** by the shadow.
2. Moving on from the **planning** phase leaves the banner standing.
3. Moving from **implementation review** to **post-review** leaves it standing,
   where it should be gone.

**Live evidence** (window `agent-pick-1566`, captured during exploration):
the minimonitor rendered

```
 ⚠ shadow feedback is stale — agent
 moved on (analyzed 15m25s ago)
```

while the bound shadow pane `%287` had emitted **zero** concern markers over its
whole scrollback — it had only been asked to explain the followed agent's plan.
The banner consumed 2 of the pane's ~38 usable columns' worth of rows to say
something untrue.

The banner itself is wanted. **This task is about making it truthful, not about
removing it**, and it is explicitly *not* about the staleness *signal*: the
signal as consumed by the concern dialog / picker behaves correctly.

## Root cause

### A. Read-recency is ungated on whether feedback exists

`compute_block_age_staleness` (`monitor/monitor_core.py`) is already gated:
with no block on the pane it returns `applicable=False`, and
`contains_block_evidence` (`monitor/concern_parser.py`) documents this exact
failure mode in its own docstring —

> "There is no block" and "there is a block whose age I cannot establish" are
> different states: collapsing them makes an explain-only shadow — one never
> asked for a review — report "freshness unknown" forever, about feedback that
> does not exist.

But `combine_staleness` returns `read` unchanged when the block age is
inapplicable, and **read-recency has no equivalent gate**. Read recency answers
"has the shadow re-read since the agent last changed?", which is well-defined
whether or not the shadow ever produced anything — so for an explain-only
shadow it goes `True` and the banner renders "shadow feedback is stale" about
feedback that was never produced. The `contains_block_evidence` gate protects
one of the two inputs and the banner consumes their join.

### B. The standing warning is never retired

`_record_combined_staleness` preserves a standing `True` and records a `None`
over a `False` — correct as a fail-safe rule. But the only paths that fully
clear the banner are an explicit `False` verdict and the shadow pane
disappearing (`_maybe_offer_concerns`, the `if not shadow_pane` branch). For a
one-shot shadow, read-recency is permanently `True` once the followed agent
types anything after the shadow's last read, so the warning has no realistic
exit.

### C. No workflow-phase awareness

Minimonitor already computes a `PhaseSignal` on every tick (`_phase_for_snap`,
`.aitask-scripts/lib/workflow_phase.py`, `PHASES = PLAN / IMPLEMENT / POSTIMPL /
UNKNOWN`) and stamps it onto the shadow pane via `_restamp_shadow_phase`. The
banner never reads it. Concerns raised about a *plan* stop mattering once the
agent is implementing; concerns raised during implementation review stop
mattering at post-review. Nothing invalidates the banner on either transition.

## Scope

**In scope** — the minimonitor continuous banner only:

- `_refresh_shadow_stale_banner` (per-tick write site)
- the picker-path write inside `action_pick_concerns` that also calls
  `_record_combined_staleness`
- a phase-transition retirement path, sitting alongside the existing
  no-shadow clear in `_maybe_offer_concerns`

**Out of scope — must not change behavior:**

- `compute_shadow_staleness` / `combine_staleness` / `compute_block_age_staleness`
  semantics as consumed by the other callers
- the **auto-recheck review loop** (`monitor/review_loop.py`, t1159_2). It fires
  on `awaiting_input AND stale` and reads `_shadow_feedback_stale` — the
  **read-recency** verdict — not the combined banner verdict. Confirm this
  separation holds after the change; the loop must keep seeing the same input it
  sees today, including the `_loop_stale_false_pending` latch.
- the full monitor (`monitor/monitor_app.py`). It has **no** continuous banner
  and already computes staleness only on paths that hold a concern block (the
  toast path and the picker path), which is the precedent this task follows.
  Its picker warning stays as-is.

## Constraints

- **The advisory-phase anti-gating rule holds.** `aidocs/framework/shadow_agent.md`
  ("Phase detection (advisory)") requires a wrong or `UNKNOWN` phase to cost the
  user at most one extra keystroke. Suppressing an advisory banner is a display
  default and fits that rule, but retirement must fire only on a transition
  between two **known, different** phases — never on a transition into or out of
  `UNKNOWN`, and never such that a mis-detected phase can hide a warning that a
  real block still justifies.
- **Do not weaken `_record_combined_staleness`'s preserve rule.** Phase
  retirement is a new, explicit clear (like the no-shadow clear), not a
  loosening of the fail-safe join. Keep the rule in exactly one place.
- **`display` toggling is load-bearing.** Per `_set_shadow_stale_banner`'s
  docstring (t1499), an empty `Static` with `height: auto` still occupies a row;
  clearing the text must turn the widget off. The same docstring warns that
  asserting on the `_shadow_stale_banner_text` seam is exactly what let this
  surface ship dead — **verify on the composited frame**, not on the seam.

## Acceptance criteria

1. A shadow that has never emitted a concern block produces **no** banner, in
   any read-recency state (`True` / `False` / `None`) — reproducing the
   `agent-pick-1566` case above.
2. A shadow with a real concern block still goes stale exactly as it does today
   (read-recency `True`, and the block-age-only wording), with unchanged banner
   text for those cases.
3. A standing warning is retired when the followed agent's phase changes between
   two known phases (`PLAN` → `IMPLEMENT`, `IMPLEMENT` → `POSTIMPL`), and is
   **not** retired on any transition involving `UNKNOWN`.
4. The `#mini-shadow-stale` widget occupies **zero rows** whenever it carries no
   warning — asserted on the rendered frame, not on `_shadow_stale_banner_text`.
5. `review_loop.py`'s firing input is provably unchanged: the loop still consumes
   the read-recency verdict, and the banner gating does not alter what it sees.
6. `monitor_app.py`'s picker/toast staleness wording and behavior are unchanged.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-18T14:21:18Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-18T15:04:40Z status=pass attempt=1 type=human
