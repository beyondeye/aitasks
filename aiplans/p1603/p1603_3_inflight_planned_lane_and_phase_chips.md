---
Task: t1603_3_inflight_planned_lane_and_phase_chips.md
Parent Task: aitasks/t1603_surface_deferred_plan_marker_on_the_board.md
Sibling Tasks: aitasks/t1603/t1603_1_*.md, aitasks/t1603/t1603_2_*.md, aitasks/t1603/t1603_4_*.md, aitasks/t1603/t1603_5_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1603_3 — In-flight view: Planned lane, admission, phase chips

## Context

Makes the in-flight view an operational workflow view rather than a human-gates
queue: admits approved-and-deferred `Ready` tasks, adds a fourth lane for them,
and renders each task's workflow phase and compact gate progress. Consumes
t1603_2's seam. Depends on t1603_2.

## The model — code, tests and docs describe THIS

**Every task occupies exactly one lane and carries exactly one phase.**
`InFlightItem.group` stays a scalar `str` (`aitask_board.py:120`); the refresh
path appends each item to exactly one lane list (`:9093-9101`). No multi-lane
model.

- **Lane = what happens next.** The axis is *not* "actor" — the field is
  literally `next_action` and the titles read "Needs your action" / "Agent can
  continue" / "Blocked". Four values: `planned` (a human picks it) · `human` ·
  `agent` · `blocked`. **Planned is intentionally the fourth value**, placed
  first.
- **Chip = where the task sits in the workflow.** On **every** card, Planned
  included, so its meaning never depends on the lane.

Independence means neither axis determines the other, shown by two pairs of
*different* tasks:

| # | Task | Status | Phase (chip) | Lane |
|---|---|---|---|---|
| A | approve-and-stop | `Ready` + marker | `plan_approved` | **Planned** |
| B | `resume_point == IMPLEMENT` | `Implementing` | `plan_approved` | **Agent can continue** |

| # | Task | Lane | Phase (chip) |
|---|---|---|---|
| C | pending human gate | Needs your action | `awaiting_review` |
| D | `resume_point == POSTIMPL` | Needs your action | `post_impl` |

A Planned card's chip restates its lane. It is rendered anyway: a chip that
disappears on some cards makes its absence ambiguous, and row B proves the same
chip value is not redundant one lane over.

## Pre-phase (risk mitigations)

### `phase_model_is_the_single_authority`

Runs **before** the chip is added. Make `_inflight_item_for`'s lane
classification **consume** t1603_2's phase model instead of deriving a second
verdict from the same `TaskGateState`. Two derivations over one input drift, and
the visible symptom is a card whose lane and chip contradict each other.

Ship a test asserting lane and chip cannot disagree across every ledger state —
`stale_signed`, failed-gate, `ALL_PASS`, `POSTIMPL`, no-ledger.

## Implementation Steps

### 1. Admission

`_inflight_item_for` (`:1873-1875`) returns `None` for anything not
`Implementing`. Admit `Ready` + `_plan_approved_marker` as
`group="planned"`, `next_action="approved plan — pick to implement"`.
**Every existing `Implementing` classification stays exactly as it is.**

### 2. ⚠ Close the routing hole the admission opens

`_ops_hint` (`:3296-3305`) appends `g resume` whenever `item.has_ledger` is
true — and **a Planned task does have a ledger**: the approve-and-stop sequence
records `plan_approved: pass` *before* reverting the status
(`task-workflow/plan-approved-stop.md`), and nothing strips `## Gate Runs`. Its
`resume_point` is therefore `IMPLEMENT`.

So the naive admission puts `g resume` on a `Ready` task, bypassing the planning
checkpoint and its remote drift check — exactly what t1595's
visibility-not-routing constraint forbids
(`aidocs/gates/ledger-driven-reentry.md`).

**Gate the resume op on the lane (`group != "planned"`), not on `has_ledger`.**
Required work, not a nicety.

### 3. Dataclass and lane

- `InFlightItem` gains `phase`, `provenance`, `progress`.
- `InFlightColumn.TITLES` / `.COLORS` gain `planned`; pick a colour distinct
  from the existing `#FFB86C` / `#50FA7B` / `#FF5555`.
- The refresh path's `grouped` dict and iteration order become
  `("planned", "human", "agent", "blocked")`.

### 4. Card

`InFlightTaskCard.compose` renders the phase chip and t1603_2's compact progress
in place of the raw `gate_summary` dump. Keep `next_action`, blockers and the
ops-hint line. Degraded renderings follow t1603_4's shared spec:
`Gate state unavailable: <error>`, and `No gate ledger — <phase> (<provenance>)`
rather than a fabricated `0/0`.

Use `markup=False` with an explicit `Text` for any line carrying free-form gate
names (`project_textual_static_markup_eats_free_form_prose`).

## Post-phase (risk mitigations)

### `narrow_terminal_lane_budget`

Runs **after** the lane renders. Four 44-column lanes plus borders and margins
need roughly 176 columns; a narrower terminal silently gains horizontal
scrolling it did not have. Measure the real budget, then pick and implement one
of: horizontal scrolling made deliberate, lane collapsing, or a responsive fold
of the Planned lane into "Agent can continue" below a threshold. **Record the
measured threshold in this plan** — do not let the behaviour fall out of the
layout.

## Verification

- ops hints unchanged for every `Implementing` task — assert the rendered text,
  not the branch;
- **a Planned card offers `p pick` and must NOT offer `g resume`** — asserted
  against a fixture that genuinely carries a `plan_approved: pass` ledger entry.
  A ledger-free fixture passes vacuously and is the wrong control; the test must
  fail if the guard is written as `has_ledger`-only;
- no lane swallows an item: total across lanes == `len(get_inflight_items())`;
- **one lane per item** — each `group` is a single value; no task id appears in
  two lane lists;
- the two-axes model as fixtures: rows **A/B** and **C/D**. If either pair
  collapses to one lane or one chip, the model is wrong and the test says so;
- lane/chip agreement across every ledger state (the pre-phase test);
- the chosen narrow-terminal behaviour at and below the measured threshold.

`bash tests/run_all_python_tests.sh --test-dir tests` — read only the last line.
Then live-check in a **real terminal**: `aidocs/framework/tui_conventions.md`
records that a headless `App.run_test` pin can diverge from a real pty.

## Risk

### Code-health risk: medium
- Touches the in-flight classifier, the dataclass, the card, the column and the
  refresh path — the widest single child in this family. · severity: medium ·
  → mitigation: none (accepted residual)
- Admitting `Ready` tasks breaches visibility-not-routing by default via
  `_ops_hint`'s `has_ledger` test. · severity: high · → mitigation: inline
  step 2 above, with a ledger-carrying fixture as the test control
- A second phase authority beside the lane classification would let lane and
  chip disagree. · severity: medium · → mitigation: inline pre-phase
  `phase_model_is_the_single_authority`
- A fourth lane changes the horizontal budget. · severity: medium ·
  → mitigation: inline post-phase `narrow_terminal_lane_budget`

### Goal-achievement risk: medium
- Serving two groupings at once may not actually make the phase distribution
  readable; the payoff is judged by a human, not a test. · severity: medium ·
  → mitigation: none (accepted residual; t1603_6 is where it is judged)

## Step 9 (Post-Implementation)

Standard closure: commit, merge per the plan header, archive the task and plan.
