---
Task: t1210_5_trail_move_to_column_commands.md
Parent Task: aitasks/t1210_brainstorm_durable_implementation_trail_skill_and_board_repo.md
Sibling Tasks: aitasks/t1210/t1210_6_implementation_trail_docs.md, aitasks/t1210/t1210_7_manual_verification_implementation_trails.md
Archived Sibling Plans: aiplans/archived/p1210/p1210_1_trail_schema_library_and_validator.md, aiplans/archived/p1210/p1210_2_trail_gatherer_and_drift_helper.md, aiplans/archived/p1210/p1210_3_aitask_trail_skill.md, aiplans/archived/p1210/p1210_4_board_bytrail_view.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1210_5 — By-Trail move-to-column commands (`m` / `M`)

## Context

T5 of the Implementation Trails decomposition (parent t1210, RFC §9.4/§10 in
`aidocs/implementation_trail_design.md`). The By-Trail view (t1210_4) currently
renders wave lanes read-only. RFC §10 makes the **board column** — not an API —
the bridge between a trail and the t1162 manager work report: the user moves
tasks or whole waves into a column from By-Trail, and the Work Report reads that
column unchanged. This task adds the two commands that make that bridge usable.

**Verified against the landed code, not the task's original plan** (which was
written pre-t1243):

| Task-file premise | Landed reality |
|---|---|
| `move_task_col` + `normalize_indices` | Gone. Use `move_tasks_to_column` (`aitask_board.py:2305`) — K writes, input order preserved, all-or-nothing, appends past the destination max. Never call `respace_column`. |
| "build a column-picker modal" | Already exists. t1243_7 shipped `_move_destination_columns` → `ColumnSelectScreen` → `_apply_move_to_column`, plus `_reject_stale` / `_review_then` / `MoveTaskSelectScreen`. |
| t1268 "may land second" | Already landed. `_rerender_trail` (`:9292`) is its local re-render path. |
| "boardcol is displayed" on a trail card | It is **not** — `TrailTaskCard.compose` renders follow-up glyph, title, classification badge, status badge, drift. Nothing reads `board_col`. |

The RFC's §8.1 "a move must not flip the trail to stale" holds and is now
*verified*: the digest is `input_digest` over INPUT records only
(`task_file`: exists/status/depends/gates; `plan_file`: exists/content_hash).
`boardcol` appears only on the display-only `MEMBER:` line, `boardidx` is
structurally unrepresentable, and `GATHERER_DRIFT_CODES`
(`trail_gather.py:201`) has no board-related code. A column move therefore
cannot produce drift.

## Design decisions

1. **`m` extends the existing chain; it is not a new binding.** The task file
   is explicit: "Do not build a second column picker… so `m` means the same
   thing in every view." `Binding("m", "move_to_column", "Move to Col")` and its
   footer label are already truthful in By-Trail, so no duplicate-key pair
   (unlike t1268's `r`/`s`, which needed *different* labels).

2. **`M` is By-Trail-specific** — new `action_trail_move_wave`, declared
   adjacent to `m` per the uppercase-adjacent rule in
   `aidocs/framework/tui_conventions.md`. `M` is unbound today.

3. **Wave membership comes from `TrailColumn.lane.entries`, not a DOM sweep.**
   `query(TrailColumn)` is one widget per wave; `query(TaskCard)` is the
   whole-board walk t1243_7 measured and removed. `lane.entries` is also the
   authoritative `position` order and carries the entry refs needed for the
   which-item skip report.

4. **`M` always reviews; `m` never does.** `M` is a bulk action over cards a
   search filter may have hidden — `_review_then` shows exactly what will move,
   in wave order, and `MoveTaskSelectScreen` confirms in displayed order, which
   `move_tasks_to_column` consumes verbatim. `m` acts on one visible focused
   card, matching the existing no-marks path. **The wave list must not pass
   through `_board_order()`** — that re-sorts by column/boardidx and would
   destroy wave order.

5. **No re-render after a By-Trail move, deliberately.** `move_tasks_to_column`
   mutates `task.board_col`/`board_idx` on the manager's live `Task` objects
   *and* writes the files, and no By-Trail surface reads either field — so the
   lanes cannot change. A later view switch calls `refresh_board`, which reads
   those same in-memory objects, so the move is already visible there
   (satisfying step 4 of the task's plan without a second reload route).
   `_apply_move_to_column`'s `refresh_columns(...)` would be actively wrong here:
   By-Trail mounts `TrailColumn`s, not `KanbanColumn`s, and `src_cols` names
   columns this view does not render.

6. **Ghosts and children are excluded structurally.** Ghosts: `TrailGhostCard`
   carries a synthetic stub with no file (RFC §9.1 read-only). Children:
   `move_tasks_to_column` resolves against `task_datas` (parents only) and a
   child has no column of its own — the same refusal the normal-view `m`
   already gives.

7. **The wave list is deduplicated by task before it reaches the review
   dialog.** `TaskSelectScreenBase._row_key`'s contract is "hashable **and
   unique**" — it is the `SelectionList` value, and `_selected()` re-emits one
   entry per matching row, so a repeated filename yields a row the user cannot
   independently uncheck and a duplicate in the confirmed list.
   `trail_schema._semantic_checks` enforces uniqueness on `wave_id`,
   `entry_id`, `evidence_id` and `observation_id`, and strictly increasing
   `position` — but **nothing on `entry["task"]`**, so a schema-valid wave may
   list one task twice, and `build_trail_lanes` resolves both to the same live
   `Task` and renders both cards. `move_tasks_to_column`'s `_resolve_parents`
   dedups too, so the *write* was never at risk; the review dialog is. This is
   new surface: `m`'s marked path is a set, its focused path is one card, and
   its placeholder path reads `get_column_tasks` — only the wave list can
   repeat a task.

8. **Every move action carries its own ghost guard — the `check_action` ghost
   pre-gate is not sufficient.** It hides the *binding*; the command palette
   calls `action_*` directly (`move_to_column` is already in `_COMMANDS`), and
   `action_move_to_column` re-checks its own view gate for exactly this reason.
   `TrailGhostCard` passes `is_child=False` and `_GhostTaskStub.filename` is a
   synthetic `trail-ghost-<slug>.md`, so without a guard that name reaches
   `_reject_stale`, which reports *"Selection is stale — no longer on the
   board… Press r to refresh"* about a valid read-only trail member — a wrong
   diagnosis pointing at a refresh that cannot help. `_GhostTaskStub`'s
   docstring calls `check_action` "the primary safety"; that is true for
   *hiding*, not for *dispatch*. The guard goes in unconditionally (not under a
   `bytrail` branch): `is_ghost` is False on every other card, so an
   unconditional check is free and cannot be missed if ghosts ever render
   elsewhere.

## Implementation

### 1. `.aitask-scripts/board/aitask_board.py` — bindings

Add next to the existing `m` binding (~`:8636`):

```python
Binding("m", "move_to_column", "Move to Col"),
# By-Trail wave move (t1210_5). Uppercase sibling declared adjacent to its
# lowercase primary per tui_conventions.md. NOT a duplicate-key pair: `m`
# keeps one meaning in every view, so only the wave command needs a key.
Binding("M", "trail_move_wave", "Move Wave"),
```

Add to `KanbanCommandProvider._COMMANDS` (~`:8182`), which the palette-parity
test covers:

```python
("Move Wave to Column", "action_trail_move_wave",
 "Move the focused wave's tasks to a column, in wave order"),
```

### 2. `check_action` gating (~`:8779`–`:8945`)

> **Deviation (implementation).** The plan put `"move_to_column"` and
> `"trail_move_wave"` in the **ghost pre-gate** tuple. That was wrong and two
> existing tests caught it: the pre-gate calls `_focused_card()` for every
> action in the tuple *unconditionally*, which (a) made `move_to_column` read
> focus twice — its own branch reads it too — failing
> `test_the_gate_issues_AT_MOST_ONE_dom_query`, and (b) ran a focus read before
> the marked-set early return, failing
> `test_a_marked_set_short_circuits_before_any_dom_query`. Both pin t1243_7's
> measured hot-path fix (`check_action` runs once per binding on every
> `refresh_bindings()`), so they are real contracts, not fixture noise.
>
> **Landed instead:** neither action joins the pre-gate; each does its own
> `is_ghost` check inside its own branch, riding the `_focused_card()` it
> already fetches. Same hiding behaviour, one focus read, and none at all
> outside By-Trail. The action-level ghost guards below are unaffected — they
> were always the real safety.
- In the `move_to_column` branch, narrow the derived-view hide list to
  `("inflight", "bytopic")` and insert a By-Trail branch **before** the
  `if self.marked: return True` early return:

```python
elif action == "move_to_column":
    if self.base_filter == "bytrail":
        # Resolved entirely on focus: `toggle_mark` is hidden here and
        # `_set_base_filter` clears the set on entry, so a mark cannot
        # exist. Gating before the marks check states that invariant
        # instead of depending on it holding forever.
        focused = self._focused_card()
        return focused is not None and not focused.is_child
    if self.base_filter in ("inflight", "bytopic"):
        return False
    ...unchanged...
```

- New branch for the wave command:

```python
elif action == "trail_move_wave":
    # Live only in By-Trail, on a live (non-ghost) card. Deliberately NOT
    # gated on `focused.is_child`, unlike `m`: `M` acts on the WAVE, so a
    # focused child still names a wave whose parents are movable. The
    # empty-wave case is reported by the action, not hidden here — a DOM
    # walk in check_action would undo t1243_7's measured hot-path fix.
    if self.base_filter != "bytrail":
        return False
    return self._focused_card() is not None
```

### 3. Extract the destination chooser — **one named method, both callers**

`action_move_to_column` currently holds the destination flow as a local
closure `to_destination`. A closure cannot be handed to `_review_then` from a
*different* action, so lift it verbatim to a method on `KanbanApp`, above
`action_move_to_column`:

```python
def _choose_move_destination(self, filenames) -> None:
    """Offer the destination columns for `filenames`, then apply the move.

    A METHOD, not the local closure it grew from: `action_trail_move_wave`
    (t1210_5) passes it to `_review_then` as the confirm callback, and a
    closure is not reachable from there. Both move commands therefore run
    one implementation of the destination chain.
    """
    # Built AFTER the review: the redundant-column filter depends on the
    # confirmed target set, not on the pre-review one.
    dests = self._move_destination_columns(filenames)
    if not dests:
        self.notify("Nowhere to move to — every other column is collapsed, "
                    "and the selection already sits where it is.",
                    severity="warning")
        return
    self.push_screen(
        ColumnSelectScreen(self.manager, "Move to", columns=dests),
        lambda col_id: self._apply_move_to_column(filenames, col_id),
    )
```

`action_move_to_column`'s three existing `to_destination` references become
`self._choose_move_destination` (two as a `_review_then` callback, one called
directly on the focused-card path); the local `def to_destination` is deleted.
**`_choose_move_destination` is the only name for this flow** — there is no
`_trail_move_destination`.

### 4. `action_move_to_column` (~`:10644`) — By-Trail path

Replace the blanket view gate and add the focused-card-only branch:

```python
if self.base_filter in ("inflight", "bytopic"):
    return
...
if self.base_filter == "bytrail":
    # Focused card only: no marks exist here, and a wave lane has no
    # column placeholder to fall back to. Ghost/child refusals below
    # still apply, so this shares the same `to_destination` chain.
    if focused is None:
        return
```

Add the ghost guard immediately after `focused = self._focused_card()`, i.e.
**before** the existing child check and before any target derivation:

```python
focused = self._focused_card()
# Ghost guard — BEFORE target derivation, and unconditional. check_action
# hides `m` on a ghost, but that is only the BINDING gate: the palette
# calls action_* directly (same reason the view gate is re-checked above).
# Without this, _GhostTaskStub's synthetic `trail-ghost-<ref>.md` reaches
# _reject_stale, which blames a stale selection and tells the user to press
# r — about a member that is simply read-only, and that a refresh will
# never make movable.
if focused is not None and getattr(focused, "is_ghost", False):
    self.notify("Archived, missing and cross-repo trail members are "
                "read-only — there is no local task file to move.",
                severity="warning")
    return
if focused is not None and focused.is_child and not self.marked:
    ...unchanged...
```

Then branch — in By-Trail, skip the marked-set and column-placeholder paths
entirely and go straight to `self._choose_move_destination([focused_name])`
after `_reject_stale`.

### 5. New `action_trail_move_wave`

```python
def action_trail_move_wave(self) -> None:
    """`M`: move the focused wave's tasks to a column, in position order."""
    if self._modal_is_active():
        return
    # A binding gate is not an action guard — the palette calls action_*
    # directly (same reason action_trail_summary_expand re-checks).
    if self.base_filter != "bytrail":
        return
    focused = self._focused_card()
    if focused is None:
        return
    # Same ghost guard as `m`, and for the same reason: check_action hides
    # `M` on a ghost, but the palette dispatches straight here. Refuse with
    # a reason rather than silently — RFC §9.1 gives ghosts no move action,
    # so this states that instead of looking broken.
    if getattr(focused, "is_ghost", False):
        self.notify("Read-only trail member — move the wave from a live "
                    "card in it.", severity="warning")
        return
    lane = next((c for c in self.query(TrailColumn)
                 if c.col_id == focused.column_id), None)
    if lane is None:
        return
    names, ghosts, children, dupes, seen = [], [], [], [], set()
    for view in lane.wave_entries():          # position order
        ref = str(view.entry.get("task") or "?")
        if view.task is None:
            ghosts.append(ref)
        elif "_" in (task_own_id(view.task) or ""):
            children.append(ref)
        elif view.task.filename in seen:
            # Two entries, one task. `entry_id` is unique and `position`
            # strictly increasing, but trail_schema enforces NOTHING on
            # `entry.task` — the same ref may legally appear twice in a
            # wave, and both render. Dedup on FIRST occurrence so the kept
            # slot is the earliest position.
            dupes.append(ref)
        else:
            seen.add(view.task.filename)
            names.append(view.task.filename)
    # Which-item report, never a bare count (the t1243_6 refusal idiom).
    skipped = ([f"{len(ghosts)} ghost: " + ", ".join(ghosts[:3])] if ghosts else []) \
        + ([f"{len(children)} child: " + ", ".join(children[:3])] if children else [])
    if not names:
        self.notify("Nothing movable in this wave — "
                    + "; ".join(skipped) if skipped else
                    "Nothing movable in this wave", severity="warning")
        return
    if skipped:
        self.notify("Skipping " + "; ".join(skipped))
    if dupes:
        # Not a skip — the task still moves, once. Reported so the review
        # dialog listing fewer rows than the wave shows is explained.
        self.notify(f"{len(dupes)} task(s) appear twice in this wave "
                    f"({', '.join(dupes[:3])}) — moving each once.")
    # The SAME method action_move_to_column uses (step 3) — one
    # destination chain, not a parallel one.
    self._review_then(names, self._choose_move_destination)
```

`TrailColumn` gains a one-line `wave_entries()` accessor returning
`self.lane.entries`, so the action does not reach through two attributes.

### 6. `_apply_move_to_column` (~`:10715`) — view-aware repaint

After the `result.refused` check and `self.marked.clear()`:

```python
if self.base_filter == "bytrail":
    # By-Trail renders TrailColumns, not KanbanColumns, and no trail
    # surface reads board_col/board_idx — the lanes cannot change, and
    # `src_cols` names columns this view does not render. The manager's
    # Task objects were mutated in place, so a later view switch shows
    # the move without a reload.
    self.notify(f"Moved {len(result.moved)} task(s) to "
                f"{self._column_title(col_id)}")
    return
self.refresh_columns(...)   # unchanged
```

## Tests

**`tests/test_board_move_command.py`** — first, a harness change that is load
bearing: `_mock_app` builds a `MagicMock` and binds a **named list** of real
methods onto it (`:132`). Add `_choose_move_destination` and
`action_trail_move_wave` to that list. This is not bookkeeping — a `MagicMock`
auto-creates any attribute it is asked for, so a callback method that does not
exist on `KanbanApp` would silently resolve to a no-op mock here and every test
would pass while a real board raised `AttributeError` *after* the user confirmed
the review dialog. Binding the real attribute is what makes the harness able to
fail on a missing or renamed method.

Two existing tests pin the old contract and must be updated, since t1210_5
deliberately changes it:

- `MoveGatingTests.test_hidden_in_every_derived_view` → `("inflight", "bytopic")`,
  renamed to say which views; add a By-Trail companion asserting `m` is
  `True` on a live parent card, `False` on a ghost, and `False` on a child.
- `MoveActionGuardTests.test_the_view_gate_is_re_checked_inside_the_action` →
  same narrowing, plus a By-Trail case asserting the action *does* push a
  screen.
- New `TrailGhostActionGuardTests` — **the palette/direct-dispatch path, not
  the gate.** Call `action_move_to_column()` and `action_trail_move_wave()`
  directly with a focused `TrailGhostCard` while `check_action` is never
  consulted, and assert: `push_screen` not called, `move_tasks_to_column` not
  called, and the notify text is the read-only refusal — explicitly **not**
  the `_reject_stale` "no longer on the board / press r" string. Asserting the
  *absence* of the stale wording is what makes this test fail if the guard is
  removed; a bare "did not push a screen" assertion passes either way, since
  the unguarded path also pushes nothing.
- New `TrailWaveMoveTests` on the existing `_mock_app` harness (extended with
  a `TrailColumn` double and `_focused_card` returning a trail card):
  - wave order is preserved end-to-end — assert the exact `filenames` list
    handed to `_review_then`/`move_tasks_to_column`, not just its length;
  - ghosts and children are skipped **and named** in the notify text;
  - an all-ghost wave notifies and writes nothing;
  - **duplicate member fixture** — a wave whose entries carry the same task
    ref twice (distinct `entry_id`s, increasing `position`s, so the document
    is schema-valid; assert that with `trail_schema.load_trail` so the fixture
    cannot silently drift into being invalid and pass vacuously). Assert the
    list handed to `_review_then` contains that filename **exactly once**, at
    the position of its **first** entry, and that the surrounding wave order is
    otherwise unchanged;
  - **`M` invoked from child focus succeeds** — focus a child trail card, call
    `action_trail_move_wave()`, and assert the enclosing wave's *parent* tasks
    reach the review/destination chain in position order. This is the action-
    level half of the deliberate gate divergence: without it the tests would
    only prove the footer advertises `M` there, and a later child guard added
    to the action would leave the key advertised but inert;
  - `trail_move_wave` gating: hidden outside bytrail, hidden on a ghost,
    shown on a focused child.

**`tests/test_board_bytrail_view.py`** — live Pilot coverage using the existing
`_enter_synthetic_bytrail` harness:

- `m` / `M` appear in the By-Trail footer with truthful labels, and disappear
  when a ghost takes focus (`test_focused_ghost_footer_regression` is the
  pattern);
- `M` then switch to the normal view → the wave's tasks are in the target
  column in wave order (the task file's Pilot check);
**`tests/test_trail_gather.py`** — the negative control landed **here** rather
than in the board module (deviation, for the better): `DigestStabilityTests`
already owns a synthetic repo plus `snapshot()` / `make_trail()` / `drift()`
helpers, and already carries `test_boardidx_and_updated_at_do_not_drift`.
`boardcol` was the uncovered half — and the one that needed proving, since
unlike `boardidx` it *is* emitted, on the display-only `MEMBER:` line. Added
`test_boardcol_does_not_drift`: digest unchanged, verdict still `CURRENT`, plus
a **positive control** asserting the `MEMBER:` line *did* change, so the test
cannot pass merely because the write never landed.

Run: `bash tests/run_all_python_tests.sh --test-dir tests` (read the **last**
line for the verdict; use `set -o pipefail` if piping).

## Docs

No website docs here — `t1210_6` (`depends: [t1210_5]`) owns the workflow page
and "board docs for the new view + keybindings".

**Deviation (implementation):** the planned RFC correction was **not made, and
is not needed.** The plan claimed the wireframe at
`aidocs/implementation_trail_design.md:672` put `[m] move task [M] move wave`
on the *card hint line*. Re-reading the mock in place, that row sits below the
summary panel and spans the full frame — it **is** the footer, which is exactly
where these keys land. The wireframe was already correct; only its illustrative
labels differ from the real strings ("move task" vs "Move to Col"), and
polishing those belongs to t1210_6's RFC sweep rather than to a gratuitous edit
here.

## Post-Review Changes

### Change Request 1 (2026-08-31 09:55)

- **Requested by user:** The duplicate-wave test's docstring asserted the
  repeated-task shape is schema-valid, but the test builds `SimpleNamespace`
  stand-ins and never calls `trail_schema.load_trail` — despite the approved
  plan explicitly requiring that assertion. A future schema rule could outlaw
  duplicate task refs while the test kept passing and kept claiming the case is
  reachable. Add a validated fixture, or record the deviation.

- **Verified:** Confirmed. The claim was load-bearing (it is the whole
  justification for the dedup) and nothing executed it — a self-declared marker
  gating its own premise.

- **Changes made:** Added the assertion rather than recording a deviation, and
  put it where the schema's contract belongs:
  `tests/test_trail_schema.py::SemanticNegativeControls::
  test_a_wave_may_legally_repeat_a_task_ref` — a **positive** control among the
  negatives. It takes the shipped `cross_topic_multiple_trails.json` fixture,
  appends a twin entry (fresh `entry_id`, increasing `position`, **same**
  `entry.task`) and asserts `issues_for(doc) == []` through the real validator.
  Using a real fixture beats a hand-built minimal doc: it cannot drift out of
  sync with the schema's required shape.

  Falsified before accepting it: corrupting the twin's `classification` yields
  `$.waves[0].entries[2].classification:enum`, proving the validator actually
  inspects the appended entry, so the `VALID` verdict is a real answer rather
  than the twin being ignored.

  The behaviour test in `test_board_move_command.py` no longer asserts
  schema-validity from stand-in objects — its docstring now names the
  executable premise test instead, so the two are linked and the claim lives
  where it can fail.

- **Files affected:** `tests/test_trail_schema.py`,
  `tests/test_board_move_command.py`.

## Coordination

- **t1268** has landed; this rebases onto its `check_action` `bytrail` branches
  and reuses its view semantics rather than adding a second reload route.
- **t1377_5** has landed (`e` = column management, hidden in `bytrail`). No key
  conflict with `m`/`M`; its gating stays untouched.
- The t1162 contract is preserved by construction: no work-report gatherer or
  skill file is touched.

## Risk

### Code-health risk: low

- Two existing tests in `tests/test_board_move_command.py` assert the *old*
  By-Trail exclusion and must be edited rather than deleted; editing an
  assertion to match new behavior can mask an unintended regression elsewhere
  in the same gate · severity: low · → mitigation: inline post-phase
  `pin_non_bytrail_gates_unchanged`
- `check_action` is a measured hot path (once per binding per
  `refresh_bindings()`); a new branch that queries the DOM would regress it
  · severity: low · → mitigation: covered by the design (both new gates are
  attribute reads; the existing `test_focused_card_is_o1` benchmark stands)
- Widening `m` into By-Trail brings `TrailGhostCard` within reach of the move
  chain for the first time; the `check_action` ghost pre-gate hides the key but
  does not stop palette dispatch, and the unguarded path misdiagnoses a
  read-only member as a stale selection · severity: medium · → mitigation:
  inline post-phase `ghost_action_guards`
- The two move commands share a destination chain that today is a local
  closure; giving the second caller its own copy — or referring to it by a
  second name — would split one flow in two, and the `MagicMock` harness cannot
  detect a callback that does not exist · severity: medium · → mitigation:
  inline post-phase `single_named_destination_chain`

- The wave list is the first move input that can legally repeat a task, and
  `MoveTaskSelectScreen`'s unique-key requirement is stated only in a
  docstring — nothing enforces it at the call site · severity: medium ·
  → mitigation: inline post-phase `wave_task_dedup`

### Goal-achievement risk: low

- The task file's plan is written against APIs that no longer exist, so a
  literal reading would not compile; this plan is written against the landed
  t1243/t1268 code instead · severity: low · → mitigation: resolved during
  planning (verified table above)
- RFC §8.1's "a move must not flip the trail to stale" was asserted by the
  task, not proven · severity: low · → mitigation: inline post-phase
  `drift_negative_control` (already folded into the test list above)

### Planned mitigations
- timing: post-phase | name: wave_task_dedup | type: bug | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: a schema-valid wave may repeat a task ref, violating the review dialog's unique-key contract | desc: dedup movable filenames on first occurrence before `_review_then`, report the repeats, and pin it with a duplicate-member fixture that is asserted schema-valid so it cannot pass vacuously
- timing: post-phase | name: single_named_destination_chain | type: refactor | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: two move commands needing one destination flow, and a mock harness that cannot fail on a missing callback | desc: lift the `to_destination` closure to the single method `_choose_move_destination` used by both actions, and bind it plus `action_trail_move_wave` into `_mock_app`'s real-method list so an undefined or renamed callback fails the suite instead of auto-mocking
- timing: post-phase | name: ghost_action_guards | type: bug | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: ghost cards reachable by palette dispatch once `m` is widened into By-Trail | desc: explicit is_ghost guard with truthful feedback at the top of both move actions, before target derivation, pinned by a direct-dispatch test that asserts the stale-selection wording is NOT emitted
- timing: post-phase | name: pin_non_bytrail_gates_unchanged | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: editing the two derived-view assertions could mask a regression | desc: keep the inflight/bytopic halves of both edited tests asserted explicitly, so narrowing the tuple cannot silently unhide `m` in the other two derived views
- timing: post-phase | name: drift_negative_control | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: unproven "a column move never flips a trail stale" | desc: assert the gatherer's DIGEST line and CURRENT verdict are unchanged across a move, rather than relying on the digest-exclusion argument

### Pre-phase (risk mitigations)

None.

### Post-phase (risk mitigations)

- **`wave_task_dedup`** — the `seen`/`dupes` pass in
  `action_trail_move_wave` (Implementation step 5) plus the duplicate-member
  fixture under Tests.
- **`single_named_destination_chain`** — Implementation step 3 (the
  `_choose_move_destination` extraction, both callers rewired, the closure
  deleted) plus the `_mock_app` method-list addition under Tests.
- **`ghost_action_guards`** — the unconditional `is_ghost` refusal at the top
  of `action_move_to_column` and `action_trail_move_wave` (Implementation
  steps 4 and 5), plus `TrailGhostActionGuardTests` driving both actions
  directly with `check_action` bypassed.
- **`pin_non_bytrail_gates_unchanged`** — in both edited tests, keep an
  explicit `inflight`/`bytopic` subTest asserting `False`, alongside the new
  By-Trail positive case.
- **`drift_negative_control`** — the before/after `trail_gather.py` digest +
  verdict assertion listed under Tests.

## Step 9 (Post-Implementation)

Cleanup, archival and merge follow the shared task-workflow Step 9. The
`risk_evaluated` gate is active for this task.

## Final Implementation Notes

- **Actual work done:** `m` now works in the By-Trail view and `M` moves a whole
  wave, both landing through the existing t1243_7 chain rather than a second
  one. In `.aitask-scripts/board/aitask_board.py`: the `M` binding (declared
  adjacent to `m`) plus a `_COMMANDS` palette entry; a By-Trail branch in
  `check_action("move_to_column")` and a new `trail_move_wave` gate; the
  `to_destination` closure lifted to the method `_choose_move_destination` and
  all four call sites rewired; unconditional `is_ghost` guards at the top of
  both move actions; `action_trail_move_wave` (position order, ghost/child skip
  with which-item reports, first-occurrence dedup, always-review);
  `TrailColumn.wave_entries()`; and a By-Trail branch in
  `_apply_move_to_column`. Tests across four modules — see below.

- **Deviations from plan:**
  1. **The ghost pre-gate was the wrong home** (caught by two existing tests,
     not by review). The plan added both move actions to `check_action`'s ghost
     pre-gate tuple. That tuple calls `_focused_card()` *unconditionally* for
     every action in it, which (a) made `move_to_column` read focus twice — its
     own branch reads it too — failing `test_the_gate_issues_AT_MOST_ONE_dom_query`,
     and (b) put a focus read ahead of the marked-set early return, failing
     `test_a_marked_set_short_circuits_before_any_dom_query`. Both pin t1243_7's
     measured hot-path fix, so they were preserved as real contracts rather than
     updated. **Landed instead:** neither action joins the pre-gate; each does
     its own `is_ghost` check inside its own branch, on the `_focused_card()` it
     already fetches. Same hiding behaviour, one focus read, none outside
     By-Trail.
  2. **The planned RFC edit was dropped as unnecessary.** The plan claimed
     `aidocs/implementation_trail_design.md:672` put `[m]`/`[M]` on the card
     hint line (which t1268 reduced to `[enter details]`). Read in place, that
     row spans the full frame below the summary — it **is** the footer, exactly
     where these keys land. The wireframe was already correct; only its
     illustrative labels differ from the real strings, and that belongs to
     t1210_6's RFC sweep.
  3. **The drift negative control landed in `tests/test_trail_gather.py`**, not
     the board module. `DigestStabilityTests` already owns a synthetic repo plus
     `snapshot()` / `make_trail()` / `drift()`, and already carried
     `test_boardidx_and_updated_at_do_not_drift`. `boardcol` was the uncovered
     half — and the one worth proving, since unlike `boardidx` it *is* emitted,
     on the display-only `MEMBER:` line.
  4. **Post-review (CR 1):** the duplicate-wave premise moved from a docstring
     claim to an executable test in `tests/test_trail_schema.py`. See
     Post-Review Changes.

- **Issues encountered:**
  - The two hot-path failures above. Diagnosis: `check_action` runs once per
    binding on every `refresh_bindings()`, so anything added to the shared
    pre-gate costs a focus read on *every* view, not just the one being taught
    a new trick. Resolved by scoping each check to its own branch.
  - `MoveTaskSelectScreen`'s row key must be unique, but a schema-valid wave may
    repeat a task ref (`entry_id` is unique, `entry.task` is unconstrained).
    Resolved with first-occurrence dedup plus a reported repeat count; the write
    was never at risk (`_resolve_parents` dedups too) — the review dialog was.

- **Key decisions:**
  - **One `m`, not a duplicate-key pair.** t1268 needed `r`/`s` pairs because
    By-Trail wanted *different footer labels*; "Move to Col" is already truthful
    there, so widening the existing gate beats a second binding.
  - **No re-render after a By-Trail move.** No trail surface reads
    `board_col`/`board_idx`, so the lanes cannot change;
    `move_tasks_to_column` mutates the manager's `Task` objects in place, so a
    later view switch shows the move with no reload. `refresh_columns` would
    have been actively wrong (By-Trail mounts `TrailColumn`s, and `src_cols`
    names columns this view does not render).
  - **`M` stays visible on a focused child, `m` does not.** `M` acts on the
    enclosing wave, so a focused child still names movable parents. Pinned at
    the action level, not just the gate, so a later child guard cannot leave the
    key advertised but inert.
  - **Ghost refusals live in the actions, not only the gate.** The palette
    dispatches `action_*` directly; without the guard `_GhostTaskStub`'s
    synthetic filename reached `_reject_stale` and produced a wrong diagnosis
    ("no longer on the board — press r") about a member that is merely
    read-only. The tests assert the *absence* of that wording, because the
    unguarded path also pushes no screen and a "did not push" assertion would
    pass either way.

- **Upstream defects identified:** None

- **Notes for sibling tasks:**
  - **`_choose_move_destination` is the single destination chain.** Any future
    view that gains a move command should call it (or pass it to
    `_review_then`), never re-open the closure it replaced.
  - **`_mock_app` in `tests/test_board_move_command.py` binds real methods by
    name.** A callback missing from that list resolves to an auto-created
    MagicMock and the suite passes while production raises `AttributeError`.
    Add any new action/helper you drive to that tuple.
  - **Do not add anything to `check_action`'s ghost pre-gate without checking
    the DOM-query budget** — `MoveGatingTests` pins it, and the pre-gate reads
    focus on every view.
  - **The passive t1162 bridge is now usable end-to-end:** a wave moved with `M`
    lands in the target column in wave order, and the Work Report reads that
    column with no code coupling. t1210_6 documents the workflow and the
    keybindings; the RFC wireframe at `:672` already shows `[m]`/`[M]` in the
    footer, only with illustrative labels.
