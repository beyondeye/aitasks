---
Task: t1603_3_inflight_planned_lane_and_phase_chips.md
Parent Task: aitasks/t1603_surface_deferred_plan_marker_on_the_board.md
Sibling Tasks: aitasks/t1603/t1603_4_expanded_gate_surface_in_task_detail.md, aitasks/t1603/t1603_5_website_docs_board_planned_lane_and_phases.md, aitasks/t1603/t1603_6_manual_verification_surface_deferred_plan_marker_on_the_boar.md
Archived Sibling Plans: aiplans/archived/p1603/p1603_1_board_card_badge_and_detail_row.md, aiplans/archived/p1603/p1603_2_workflow_phase_model_and_degradation.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-31 18:34
---

# t1603_3 — In-flight view: Planned lane, admission, phase chips

## Context

The board's In-Flight view is a human-gates queue: it hard-filters
`status == Implementing`, groups by required next actor, and dumps the raw gate
summary onto each card. It cannot answer "which tasks finished planning?" — the
question the parallel-planning workflow (plan several tasks, defer their
implementations, pick them up later) exists to ask.

This child makes it an operational workflow view: it admits approved-and-deferred
`Ready` tasks, adds a fourth lane for them, and renders each task's workflow
phase plus compact gate progress in place of the raw dump. It consumes t1603_2's
landed phase seam and adds **no new derivation**.

## The model — code, tests and docs describe THIS

**Every task occupies exactly one lane and carries exactly one phase.**
`InFlightItem.group` stays a scalar `str` (`aitask_board.py:118`); the refresh
path appends each item to exactly one lane list (`:9492-9496`). No multi-lane
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

---

## Verification pass (2026-08-31) — what changed since this plan was approved

All line numbers below are **current**. Two commits landed after this plan was
written (`d46fc1c10` t1603_2, then `781daf858` t1642 and `f1dc4f23e` t1210_5),
and they moved every anchor plus part of the premise.

1. **Anchors drifted.** `InFlightItem` `:118` (was 120) · `_inflight_item_for`
   `:2116` (was 1873) · `get_inflight_items` `:2182` · `InFlightTaskCard.compose`
   `:3530` · `_ops_hint` `:3553` (was 3296) · `_priority_border_color` `:3565` ·
   `InFlightColumn` `:3571` (TITLES `:3574`, COLORS `:3579`, `on_mount` `:3606`)
   · refresh path `:9492-9496` (was 9093) · `HorizontalScroll(id="board_container")`
   `:9051`.

2. **t1642 already removed half the pre-phase's premise.**
   `TaskManager._human_pending_gates` / `_has_failed_gate` (`:2099`, `:2111`) now
   delegate to the same `_pending_human_gates` / `_failed_active_gates` that
   `derive_workflow_phase` uses, frozen by `SharedGatePredicateContractTest`
   (tests/test_board_gate_digest_budget.py:306) and `TwoAxisAgreementTests`
   (tests/test_board_workflow_phase.py:741). What is still **not** single-authority
   is the *ladder ordering*: `_inflight_item_for` reads `state.resume_point`,
   `state.archive_decision` and `state.stale_signed` to pick a lane. The pre-phase
   narrows to exactly that, and gains the AST scan those two guards model.

3. **⚠ The routing hole is three sinks, not one.** `_ops_hint` is only the
   *advertisement*. The keys are live independently: `g` → `action_view_git`
   (`:10119`) → `action_gate_resume` (`:12130`) for any focused
   `InFlightTaskCard`; `s` (`:12023`) and `f` (`:10082`) →
   `_record_focused_human_gate` (`:12174`) → `aitask_gate.sh append`. A
   Ready+marker task carries a ledger whose `review_approved` is *pending*, so the
   naive admission would also let a user **sign off review on a task that has not
   been implemented**. Gating the hint text alone leaves both keys armed.

   **3b. …and the guard must not key on the LANE.** The obvious gate
   (`item.group == "planned"`) fails open on a real case: an unresolved
   dependency claims the lane first, so a `Ready` + marker task with a blocking
   dep renders in **Blocked**, `group != "planned"`, and all three routes come
   back — the exact bypass the guard exists to prevent, on a card that looks
   correctly blocked. The lane is a *display* fact and the two states are not
   the same set. Both the lane and the three guards must read **one underlying
   boolean**: `Ready` **and** carrying the deferred-plan marker.

4. **The admission needs a cheap pre-filter.** `_inflight_item_for` returns
   `None` on status *before* calling `gate_state_for` (`:1990`), which reads and
   parses the task file from disk. Calling `derive_workflow_phase` first would
   force a ledger read + a plan-path stat for **every task on the board**, every
   refresh.

5. **The degraded literals must be one function.** t1603_4's plan (`:70-72`)
   re-states `Gate state unavailable: <error>` and
   `No gate ledger — <phase> (<provenance>)`. They ship here, as a shared helper
   t1603_4 calls — not as prose duplicated into two plans. Also:
   `provenance == "marker"` is reachable **with** a ledger present, so it must not
   render "No gate ledger".

6. **`gate_summary` stays computed.** `tests/test_board_gate_digest_budget.py:244`
   asserts on `item.gate_summary`. Only its *rendering* moves off the card.

7. **A ready-made negative control exists.** `test_ready_with_ledger_is_excluded`
   (tests/test_board_inflight_view.py:109) — `Ready` + ledger, no marker — must
   stay green: it is what proves the admission keys on the marker, not the ledger.

8. **Docs go stale for one task.** `website/content/docs/tuis/board/reference.md:213`
   and `how-to.md:204-205` enumerate three lanes. That is t1603_5's scope; not
   touched here.

---

## Pre-phase (risk mitigations)

### `phase_model_is_the_single_authority`

Runs **before** the chip is added, and before the admission. Replace
`_inflight_item_for`'s lane ladder with a mapping off t1603_2's phase, so the
lane cannot be a second verdict over the same `TaskGateState`.

Add beside `derive_workflow_phase` (after `:385`):

```python
#: The In-Flight lane axis ("what happens next"), in render order. `planned`
#: is the fourth VALUE of this axis, not a second axis (t1603_3).
INFLIGHT_LANES = ("planned", "human", "agent", "blocked")

#: The ONE mapping from t1603_2's phase axis onto the lane axis. Total over
#: WORKFLOW_PHASES by test, so a sixth phase cannot land without a lane.
LANE_FOR_PHASE = {
    "plan_approved": "agent",
    "implementing": "agent",
    "awaiting_review": "human",
    "needs_attended_agent": "human",
    "post_impl": "human",
}


def _inflight_lane(phase: str, progress, *, approved_unstarted: bool,
                   blocked: bool) -> str:
    """The lane for one in-flight item — PRIMITIVES ONLY (t1603_3).

    Takes the phase name and its fraction, never a `TaskGateState`: the
    signature is what makes a second derivation impossible rather than merely
    discouraged, and `PhaseIsTheOnlyLaneAuthorityTest` scans this body for any
    gate-state read.

    The archivable rung reads the phase model's OWN fraction — `ALL_PASS` is
    exactly `progress[0] == progress[1]` (`derive_workflow_phase`'s docstring
    says so), so "ready to archive" is read off the phase rather than
    re-derived from `archive_decision`.

    `blocked` outranks `approved_unstarted`: a dependency-blocked task is one
    where nothing can happen next, which is what this axis reports. That is
    exactly why the routing guards in step 2 read `approved_unstarted`
    DIRECTLY and never `group == "planned"` — the lane is a display fact and
    the two sets differ on precisely this case.
    """
    if blocked:
        return "blocked"
    if approved_unstarted:
        return "planned"
    if progress and progress[0] == progress[1]:
        return "human"
    return LANE_FOR_PHASE[phase]
```

`approved_unstarted` is computed **once**, in `_inflight_item_for`, and stored on
the item:

```python
# The ONE authority for "plan approved, implementation never started" (t1603_3).
# The lane, the ops hint and the three action guards all read THIS — never
# `group == "planned"`, which a blocking dependency silently takes away.
approved_unstarted = status == "Ready" and bool(_plan_approved_marker(task.metadata))
```

**Two shipped classifications change. Both are deliberate, and both get a named
test:**

- **Δ1** phase `needs_attended_agent` with `resume_point == IMPLEMENT` moves
  `agent` → `human`. A pending `procedure` gate is owed by a person launching an
  attended agent; the old ladder filed it under "Agent can continue" only because
  it never looked past `resume_point`.
- **Δ2** `resume_point == POSTIMPL` **with another human gate still pending**
  re-words from `reviewed — post-implementation` to `pending human gate`. The
  lane is `human` either way; the new wording names the thing actually owed.

Everything else is byte-identical, including the `ALL_PASS` lane and wording for
a task whose `review_approved` was *skipped* (`test_skipped_human_gate_is_not_pending`).

Ship `LaneChipAgreementTests` (below) asserting the `(lane, chip)` pair across
every ledger state — `stale_signed`, failed-gate, `ALL_PASS`, `POSTIMPL`,
`IMPLEMENT`, procedure-pending, error and no-ledger — **before** the chip is
added, then re-run it after.

---

## Implementation Steps

### 1. Admission

`_inflight_item_for` (`:2116`) keeps a cheap pre-filter (finding 4), then lets the
phase model decide admission — `derive_workflow_phase` already returns `None` for
exactly the tasks the view must exclude:

```python
def _inflight_item_for(self, task: Task) -> InFlightItem | None:
    status = task.metadata.get("status")
    # Pre-filter FIRST: `gate_state_for` parses the task file, and this method
    # runs for every task on the board on every refresh. The phase model's own
    # `None` is the admission rule; this only avoids paying for it on tasks it
    # would reject on `status` alone.
    if status not in ("Implementing", "Ready"):
        return None
    if status == "Ready" and not _plan_approved_marker(task.metadata):
        return None
    task_id, title = TaskCard._parse_filename(task.filename)
    if not task_id:
        return None
    result = self.gate_state_for(task)
    phase = derive_workflow_phase(
        task, result, self.gate_registry(),
        plan_exists=_resolve_plan_path_for_task(task, self) is not None)
    if phase is None:          # Ready without a marker, Editing, Postponed, Done
        return None
    blockers = ...             # unchanged
    approved_unstarted = status == "Ready" and bool(_plan_approved_marker(task.metadata))
    group = _inflight_lane(phase.phase, phase.progress,
                           approved_unstarted=approved_unstarted,
                           blocked=bool(blockers))
    ...
```

`Ready` + marker therefore lands as `group="planned"`,
`next_action="approved plan — pick to implement"`. **Every existing
`Implementing` admission is unchanged** — the pre-filter admits a superset and
the phase model rejects the same set the old `status` test did.

The `next_action` ladder becomes phase-keyed, preserving every shipped string:

| condition (in order) | `next_action` |
|---|---|
| `blockers` | `blocked by dependencies` |
| `provenance == "error"` | `gate state unavailable` |
| `provenance in ("unknown", "derived")` | `No gate information yet — pick/resume` |
| `approved_unstarted` | `approved plan — pick to implement` *(new)* |
| `stale_signed` | `awaiting re-sign: <gates>` |
| `progress` complete | `all gates pass — archive/re-enter` |
| `phase == "post_impl"` | `reviewed — post-implementation` |
| `phase == "needs_attended_agent"` | `needs an attended agent: <current_gate>` *(new)* |
| `failed` | `failed gate — inspect/sign off or fail` |
| `human_gates` | `pending human gate` |
| `phase == "plan_approved"` | `plan approved — resume implementation` |
| else | `resume or continue planning` |

### 2. ⚠ Close the routing hole the admission opens — all three sinks

A Planned task **has a ledger**: `plan-approved-stop.md` records
`plan_approved: pass` *before* reverting the status, and nothing strips
`## Gate Runs`, so its `resume_point` is `IMPLEMENT` and its `review_approved`
is pending. Advertising or accepting a resume/sign-off there bypasses the
planning checkpoint and its remote drift check — exactly what t1595's
visibility-not-routing constraint forbids (`aidocs/gates/ledger-driven-reentry.md`).

Gate on **`item.approved_unstarted`** — never on `has_ledger` (every planned task
has one) and never on `group == "planned"` (finding 3b: a blocking dependency
takes that lane away and re-opens all three routes). All three sites:

- `_ops_hint` (`:3553`) — `if item.has_ledger and not item.approved_unstarted:`
  for `g resume`, and skip the `s`/`f` pair entirely when `approved_unstarted`.
- `action_gate_resume` (`:12130`) — after the `isinstance(focused, InFlightTaskCard)`
  check, refuse and return:
  `self.notify("t<id> has an approved plan but has not started — press p to pick it (resume would bypass the planning checkpoint).", severity="warning")`.
- `_record_focused_human_gate` (`:12174`) — same refusal, **before** the
  `human_gates` read: *"t<id> has not started — no gate can be signed on an
  approved-but-unimplemented task."*

Required work, not a nicety. A guard in the hint alone is a binding gate, not an
action guard: `g`/`s`/`f` remain reachable through their key bindings, a remap,
or the command palette.

### 3. Dataclass, lane and rendering constants

- `InFlightItem` (`:118`) gains `phase: str = ""`, `provenance: str = ""`,
  `progress: tuple[int, int] | None = None`, and `approved_unstarted: bool = False`
  — the last one defaulting to `False` so every existing construction site and
  test fixture keeps the safe (guards armed only where they must be) value.
- `InFlightColumn.TITLES` (`:3574`) gains `"planned": "Planned"`; `.COLORS`
  (`:3579`) gains `"planned": "#BD93F9"` — distinct from the shipped
  `#FFB86C` / `#50FA7B` / `#FF5555`. `_priority_border_color` (`:3565`) returns
  `"magenta"` for the planned lane, matching the existing named-colour idiom.
- The refresh path (`:9492-9496`) builds its dict and iterates **from
  `INFLIGHT_LANES`**, not from a second literal tuple:
  `grouped = {lane: [] for lane in INFLIGHT_LANES}` / `for group in INFLIGHT_LANES:`.
- New CSS rule beside `.inflight-action` (`:8356`): `.inflight-phase { color: $text-muted; }`.

### 4. Card

One shared renderer, beside the lane helpers, so t1603_4's expanded surface
cannot word the degraded states differently (finding 5):

```python
#: Human-readable phase labels — the chip's only vocabulary (t1603_3).
PHASE_LABELS = {
    "plan_approved": "plan approved",
    "implementing": "implementing",
    "awaiting_review": "awaiting review",
    "needs_attended_agent": "needs attended agent",
    "post_impl": "post-implementation",
}


def phase_chip_text(phase: str, provenance: str, progress, *,
                    error: str = "") -> str:
    """The ONE rendering of a workflow phase as compact text (t1603_3).

    Shared with t1603_4's expanded surface: a second literal for the degraded
    states is what would let the card and the detail screen describe the same
    ledger differently.

    `marker` never says "No gate ledger" — a Ready+marker task IS reachable
    with a ledger present (the marker just outranks it), so the phrase would be
    false. `None` progress prints no fraction rather than a fabricated `0/0`.
    """
    if provenance == "error":
        return f"Gate state unavailable: {error}" if error else "Gate state unavailable"
    label = PHASE_LABELS[phase]
    if provenance == "marker":
        return f"{label} (from marker)"
    if provenance in ("unknown", "derived"):
        return f"No gate ledger — {label} ({provenance})"
    if progress:
        return f"{label} · {progress[0]}/{progress[1]}"
    return label
```

`InFlightTaskCard.compose` (`:3530`) yields the chip **unconditionally**, in
place of the `if self.item.gate_summary:` line, with
`classes="task-info inflight-phase"` and **`markup=False`** — the error text and
gate names are free-form prose and Rich would eat a bracket
(`project_textual_static_markup_eats_free_form_prose`). `next_action`, blockers
and the ops line are unchanged and keep their order.

The current gate is surfaced through `next_action`
(`needs an attended agent: docs_updated`), **not** the chip, so the chip stays
inside a narrow card's budget: the longest ledger form is
`needs attended agent · 3/4` (26 cols) against a 44-column lane.

`item.gate_summary` is still computed and still asserted by
`test_board_gate_digest_budget.py:244`; only the card stops rendering it. The
full list arrives on the detail screen in t1603_4 (`effort: low`, depends on
this) — a one-task transitional gap, accepted.

---

## Post-phase (risk mitigations)

### `narrow_terminal_lane_budget`

Runs **after** the lane renders. `InFlightColumn.on_mount` (`:3606`) sets
`width: 44`, `min_width: 34`, `margin: (0, 1)`, inside
`HorizontalScroll(id="board_container")` (`:9051`) — so three lanes already
scroll below ~138 columns today; the fourth extends an existing scroll rather
than introducing one.

**Chosen behaviour: the status quo, made deliberate.** No fold, no collapse, no
narrowing (which would cost every card 10 columns and blow the chip's budget).

1. **Measure**, don't guess: sweep `App.run_test(size=(W, 40))` in the In-Flight
   view and compare `container.scrollable_content_region.width` against the
   container's own region to find the exact W at which scrolling begins, at both
   `width` and `min_width`. **Record the measured numbers in this plan** in this
   section.
2. **Pin it:** at a width below the threshold all four `InFlightColumn`s still
   exist, in `INFLIGHT_LANES` order, with their four titles, and none is dropped
   or clipped — the view scrolls.
3. Live-check in a **real terminal** at a narrow width: a headless
   `App.run_test` pin can diverge from a real pty
   (`aidocs/framework/tui_conventions.md`).

---

## Verification

New file `tests/test_board_inflight_planned_lane.py` (fixtures follow
`tests/test_board_inflight_view.py`'s `InFlightActiveSetTests`: real task files
with a valid `active_gates` tuple and a staged `metadata/gates.yaml`, so
"active" vs "filtered" vs "absent" stay distinct):

- **Admission.** `Ready` + marker + ledger → admitted, `group == "planned"`,
  `next_action == "approved plan — pick to implement"`. Negative control: the
  identical fixture **without** the marker is excluded (and
  `test_ready_with_ledger_is_excluded` stays green).
- **The routing hole — three assertions against a fixture that genuinely carries
  a `plan_approved: pass` ledger entry** (a ledger-free fixture passes vacuously
  and is the wrong control):
  - rendered ops contain `[p pick]` and **not** `[g resume]`, `[s sign-off]`,
    `[f fail]`;
  - `action_gate_resume` on a focused planned card pushes **no** screen and
    notifies;
  - `_record_focused_human_gate("pass")` on it appends **nothing** (patch the
    `subprocess.run` used by `_append_human_gate` and assert it was never called).
  - **Positive control:** the same fixture with `status: Implementing` shows
    `[g resume]` and reaches both actions — so the guard cannot be written as
    `has_ledger`-only, nor as "always off".
  - **The lane-keyed-guard control (finding 3b).** The same Ready + marker +
    `plan_approved: pass` fixture, plus an **unresolved dependency**. Two halves,
    both required:
    - the card is still *correctly* shown as blocked — `group == "blocked"`,
      `next_action == "blocked by dependencies"` — so the test cannot be
      satisfied by moving the lane;
    - and all three routes still **refuse**: no `[g resume]` / `[s sign-off]` /
      `[f fail]` in the rendered ops, `action_gate_resume` pushes no screen, and
      `_record_focused_human_gate` runs no subprocess.

    This is the discriminating case: written as `group == "planned"`, every
    guard passes the plain-planned rows above and fails here.
- **Ops hints unchanged for every `Implementing` fixture** — render-level, over
  a table of the shipped cases, asserting the hint *text*, not the branch.
- **The two-axes model as fixtures:** rows **A/B** (one phase, two lanes) and
  **C/D** (one lane, two phases). If either pair collapses, the model is wrong
  and the test says so.
- **`LaneChipAgreementTests`** — a table of `(fixture) → (lane, chip text)`
  literals over no-ledger, error, `stale_signed`, failed-gate, pending-human,
  `ALL_PASS`, `POSTIMPL`, `IMPLEMENT`, procedure-pending and Ready+marker.
- **Δ1 and Δ2** each pinned by their own named test, as deliberate corrections.
- **`PhaseIsTheOnlyLaneAuthorityTest`** — AST scan modelled on
  `SharedGatePredicateContractTest`: `_inflight_lane`'s body reads none of
  `{resume_point, archive_decision, stale_signed, archive_pending, active_gates,
  current, filtered_gates}`, and its caller set is exactly `{_inflight_item_for}`
  (vacuity guard — a renamed or dead helper must fail, not pass).
- **Totality:** every `WORKFLOW_PHASES` value is a `LANE_FOR_PHASE` key, and every
  `LANE_FOR_PHASE` value is in `INFLIGHT_LANES`.
- **Conservation:** the total across lanes equals `len(get_inflight_items())`;
  each item's `group` is a single `str`; no task id appears in two lane lists.
- **Narrow terminal:** the post-phase's threshold pin.

Existing sibling guards that must stay green (run them explicitly):
`tests/test_board_inflight_view.py`, `tests/test_board_workflow_phase.py`,
`tests/test_board_gate_digest_budget.py`, `tests/test_board_followup_glyph.py`.

```bash
bash tests/run_all_python_tests.sh --test-dir tests   # read ONLY the last line
```

Then live-check in a real terminal: `ait board`, `i`, confirm the four lanes,
the chip on every card including Planned, and that `g`/`s`/`f` refuse on a
Planned card.

## Risk

### Code-health risk: medium
- The widest child in the family: the classifier, the dataclass, the card, the
  column, the refresh path **and two action handlers**. · severity: medium ·
  → mitigation: none (accepted residual)
- Admitting `Ready` tasks arms **three** live sinks — `g` resume and the `s`/`f`
  gate appends — not just the ops-hint text, so a naive admission lets a user
  sign off review on a task that was never implemented. · severity: high ·
  → mitigation: none — closed inline by required step 2, which gates all three
  sites on `approved_unstarted`, with a ledger-carrying fixture as the control
  and an `Implementing` positive control
- The obvious form of that guard (`group == "planned"`) **fails open** on a
  dependency-blocked Ready+marker task, which takes the Blocked lane and gets
  every route back while looking correctly blocked. · severity: high ·
  → mitigation: none — closed inline by step 2 reading one underlying boolean
  that the lane also consumes, plus the dependency-blocked discriminating
  fixture in `## Verification` (a lane-keyed guard fails it)
- A second phase authority beside the lane would let lane and chip disagree.
  Reduced from the original assessment: t1642 already collapsed the two shared
  predicates, leaving only the ladder ordering. · severity: medium ·
  → mitigation: inline pre-phase phase_model_is_the_single_authority
- That refactor deliberately changes two shipped classifications (Δ1, Δ2), so a
  behaviour the user relies on could move without being noticed. · severity:
  medium · → mitigation: inline pre-phase phase_model_is_the_single_authority
- A fourth lane changes the horizontal budget. · severity: medium ·
  → mitigation: inline post-phase narrow_terminal_lane_budget
- The card drops the raw `gate_summary` line one task before t1603_4 lands the
  expanded surface that replaces it. · severity: low · → mitigation: none
  (accepted residual; t1603_4 is `effort: low` and depends on this task)

### Goal-achievement risk: medium
- Serving two groupings at once may not actually make the phase distribution
  readable; the payoff is judged by a human, not a test. · severity: medium ·
  → mitigation: none (accepted residual; t1603_6 is where it is judged)
- `website/…/board/reference.md:213` and `how-to.md:204-205` describe three lanes
  until t1603_5 lands. · severity: low · → mitigation: none (accepted residual;
  owned by t1603_5, which depends on this task)

### Planned mitigations
- timing: pre-phase | name: phase_model_is_the_single_authority | type: refactor | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a second lane derivation over the same TaskGateState, and the two deliberate deltas it introduces | desc: Replace the lane ladder with `_inflight_lane(phase, progress, …)` over primitives plus a total `LANE_FOR_PHASE` map, freeze it with an AST scan and a lane/chip agreement table across every ledger state, and pin Δ1/Δ2 as named corrections.
- timing: post-phase | name: narrow_terminal_lane_budget | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a fourth lane changes the horizontal budget | desc: Measure the exact width at which the four-lane In-Flight view starts scrolling (headless sweep + a real-pty check), record it in this plan, and pin that below it all four lanes still exist in order with none dropped or clipped.

## Step 9 (Post-Implementation)

Standard closure: commit, merge per the plan header (current-branch mode — base
and output are both `main`), archive the task and plan.
