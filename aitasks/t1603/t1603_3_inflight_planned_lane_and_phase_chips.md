---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t1603_2]
issue_type: feature
status: Implementing
labels: [board, ui, gates]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1595
implemented_with: claudecode/opus5
created_at: 2026-08-30 13:28
updated_at: 2026-08-31 18:36
---

## Context

Part of t1603. Consumes t1603_2's workflow-phase seam to make the board's
in-flight view a useful **operational workflow view** rather than a human-gates
queue: it admits approved-and-deferred `Ready` tasks, adds a fourth lane for
them, and shows each task's workflow phase and compact gate progress.

Depends on t1603_2.

## The model — code, tests and docs must all describe THIS

Two independent axes. **Every task occupies exactly one lane and carries exactly
one phase.** `InFlightItem.group` stays a scalar `str` (~line 120) and the
refresh path appends each item to exactly one lane list (~lines 9093-9101).
Nothing here makes a task appear twice; no multi-lane model is proposed.

- **Lane = what happens next.** The axis is *not* "actor" — the dataclass field
  is literally `next_action` and the titles read "Needs your action" / "Agent can
  continue" / "Blocked". Four values on one axis, no exception:
  `planned` (a human picks it) · `human` (a human acts on a gate) ·
  `agent` (an agent resumes) · `blocked` (nothing can happen).
  **Planned is intentionally the fourth value of this axis**, placed first — not
  an actor lane, not a phase lane.
- **Chip = where the task sits in the workflow.** Rendered on **every** in-flight
  card, Planned ones included, so its meaning never depends on the lane.

"Independent" means **neither axis determines the other**, shown by two pairs of
*different* tasks:

*Same phase, different lanes:*

| # | Task | Status | Phase (chip) | Lane |
|---|---|---|---|---|
| A | approve-and-stop | `Ready` + marker | `plan_approved` | **Planned** |
| B | in-flight, `resume_point == IMPLEMENT` | `Implementing` | `plan_approved` | **Agent can continue** |

*Same lane, different phases:*

| # | Task | Lane | Phase (chip) |
|---|---|---|---|
| C | pending human gate | Needs your action | `awaiting_review` |
| D | `resume_point == POSTIMPL` | Needs your action | `post_impl` |

A Planned-lane task's chip reads `plan_approved`, restating its lane. The chip is
still rendered: a chip that disappears on some cards makes its absence ambiguous,
and row B proves the same chip value is not redundant one lane over.

## Key Files to Modify

- `.aitask-scripts/board/aitask_board.py`
  - `InFlightItem` dataclass (~line 116) — add `phase`, `provenance`, `progress`
  - `_inflight_item_for` (~line 1873) — admission + consume the phase model
  - `InFlightTaskCard.compose` (~line 3274) and `_ops_hint` (~line 3296)
  - `InFlightColumn.TITLES` / `.COLORS` (~line 3318)
  - the refresh path's `grouped` dict and lane order (~lines 9093-9101)
- `tests/test_board_inflight_view.py` — extend
- `tests/test_board_inflight_planned_lane.py` — new

## Implementation Plan

### Pre-phase (risk mitigation): phase_model_is_the_single_authority

**Runs before the chip is added.** Make `_inflight_item_for`'s lane
classification **consume** t1603_2's phase model rather than deriving a second
verdict from the same `TaskGateState` in parallel. Two derivations over one
input will drift, and the visible symptom is a card whose lane and chip
contradict each other.

Ship a test asserting lane and chip cannot disagree across every ledger state —
including `stale_signed`, failed-gate, `ALL_PASS`, `POSTIMPL` and no-ledger.

### 1. Admission

`_inflight_item_for` currently returns `None` for anything whose status is not
`Implementing` (~line 1874). Admit `Ready` + `_plan_approved_marker`, returning
`group="planned"` with `next_action` "approved plan — pick to implement".

**Every existing `Implementing` classification stays exactly as it is.**

### 2. ⚠ Close the routing hole this admission opens

`_ops_hint` (~lines 3296-3305) appends `g resume` whenever `item.has_ledger` is
true. **A Planned task does have a ledger**: the approve-and-stop sequence
records `plan_approved: pass` *before* reverting the status
(`.claude/skills/task-workflow/plan-approved-stop.md`), and nothing strips the
`## Gate Runs` section — so its `resume_point` is `IMPLEMENT`.

The naive admission therefore puts a `g resume` affordance on a `Ready` task,
bypassing the planning checkpoint and its remote drift check. That is precisely
what t1595's **visibility-not-routing** constraint forbids
(`aidocs/gates/ledger-driven-reentry.md`).

**Gate the resume op on the lane (`group != "planned"`), not on `has_ledger`
alone.** This is a real defect the naive implementation ships, not a
hypothetical — treat it as required work, not a nicety.

### 3. Lane

Add `planned` to `InFlightColumn.TITLES` / `.COLORS`, and make the refresh
path's grouping and iteration order `("planned", "human", "agent", "blocked")`.
Title: "Planned" (or "Planned — awaiting implementation" if it fits).

### 4. Card

`InFlightTaskCard.compose` renders the phase chip and t1603_2's compact progress
in place of the current raw `gate_summary` dump. Keep the existing
`next_action`, blockers and ops-hint lines. Error and no-ledger renderings
follow t1603_4's shared spec: `Gate state unavailable: <error>`, and
`No gate ledger — <phase> (<provenance>)` rather than a fabricated `0/0`.

### Post-phase (risk mitigation): narrow_terminal_lane_budget

**Runs after the lane renders.** Four 44-column lanes plus borders and margins
need roughly 176 columns; a narrower terminal silently gains horizontal
scrolling it did not have. Measure the real budget, then pick and implement one
of: horizontal scrolling (the status quo, made deliberate), lane collapsing, or
a responsive fold of the Planned lane into "Agent can continue" below a
threshold. **Record the measured threshold in this task's plan** — do not leave
the behaviour to fall out of the layout.

## Verification

- ops hints unchanged for every `Implementing` task — assert the rendered hint
  text, not the branch;
- **a Planned card offers `p pick` and must NOT offer `g resume`** — asserted
  against a fixture that genuinely carries a `plan_approved: pass` ledger entry.
  A fixture with no ledger passes vacuously and is the wrong control; the test
  must fail if the guard is written as `has_ledger`-only;
- no lane silently swallows an item: the total across lanes equals
  `len(get_inflight_items())`;
- **one lane per item** — each item's `group` is a single value and no task id
  appears in more than one lane list;
- the two-axes model as fixtures: rows **A/B** and rows **C/D** above. These are
  the executable form of the claim the website will make; if either pair
  collapses to a single lane or chip, the model is wrong and the test says so;
- lane/chip agreement across every ledger state (the pre-phase test);
- the measured narrow-terminal threshold behaves as chosen (the post-phase).

Run: `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last
line. Live-check the lane in a real terminal; `aidocs/framework/tui_conventions.md`
records that a headless `App.run_test` pin can diverge from a real pty.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-31T15:36:17Z status=pass attempt=1 type=human
