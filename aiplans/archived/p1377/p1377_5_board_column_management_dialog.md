---
Task: t1377_5_board_column_management_dialog.md
Parent Task: aitasks/t1377_minimonitor_pick_column_action_and_board_column_management.md
Sibling Tasks: aitasks/t1377/t1377_1_*.md, aitasks/t1377/t1377_2_*.md, aitasks/t1377/t1377_3_*.md, aitasks/t1377/t1377_4_*.md, aitasks/t1377/t1377_6_*.md
Archived Sibling Plans: aiplans/archived/p1377/p1377_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-06 15:52
---

# p1377_5 — board ad-hoc column-management dialog

## Goal

One discoverable dialog behind one key covering reorder / add / edit / delete /
merge, wiring up t1377_4's merge engine. Satisfies parent AC4, AC5, AC7.

The gap this closes is **discoverability plus merge**: add / edit / delete already
exist but **no key is bound to any of them** — they are reachable only via the
Ctrl+P palette or the header ✎ button. And `TaskManager.merge_columns` has
**zero call sites** (verified) — this dialog is its first consumer.

---

## Plan re-verification (2026-08-06)

Every anchor was re-checked against `main` @ `b55f9f967`. **Four sequencing
claims in the original plan were wrong** and are corrected below; the design is
otherwise sound and gets one substantive correction (the `check_action` gate).

| Original claim | Verified reality |
|---|---|
| t1243_7 "expected to have landed" the `_COMMANDS` de-dup | **Landed** (`8b0e63a3e`). `_COMMANDS` at `aitask_board.py:6246`, `_resolved()` at `:6267`, guard `CommandPaletteParityTests` in `tests/test_board_move_command.py:180`. **Consume it.** |
| t1418 (footer) is `Implementing` | **Landed** (`f8a4d7614`). `lib/multirow_footer.py`; it **un-hid `m`** and deleted t1243_7's "footer is already full" comment. |
| t1210_5 "sits ahead in the queue — rebase onto its gating" | **Still `Ready`.** This child lands **first**; it must gate `bytrail` itself and leave the note for t1210_5. |
| Workstream C order "undecided" | **Resolved.** `grep -rn 'collapsed_groups\|boardgroup' board/ lib/` → **0 hits**; t1243_8…15 all `Ready`. t1243_10 has already accepted ownership of the group integration (its §"if `merge_columns` is already in board/aitask_board.py … **this task owns the integration**"). Build against the current model; **do not** pre-build group handling. |

Also confirmed: t1369 landed (`a3f0494a3`), t1268 landed. `e` is **free** at
board level — the only `Binding("e", …)` is inside `TaskDetailScreen`
(`:5225`, scope `board.detail`). `M` and `G` are entirely unbound.

**Scope decision (user, 2026-08-06): column *rename* stays unreachable.**
`ColumnEditScreen.save()` dismisses `("edit", self.col_id, title, color)` — the
id is never re-slugged, so `update_column`'s rename branch is never taken. Ids
are auto-slugged, so re-slugging on a title edit would rewrite every member
task's `boardcol` as a side effect of a cosmetic change, and ids are also
referenced by the work-report protocol. Nothing in AC4/AC5 or t1377_7's
manual-verification checklist asks for rename. **t1377_4 left a comment at
`aitask_board.py:1953` claiming the path is "Dead in the UI until t1377_5 makes
the rename reachable" — correct that comment** to say the path stays dormant by
decision, so the next reader does not treat it as an unfinished handoff. Its
collapsed-state migration fix stays in place and correct.

---

### Pre-phase (risk mitigations)

Runs **before** Step 1 — it characterizes the code the extraction in Step 2
re-parents, so a regression fails loudly instead of silently.

**`[characterize_column_edit_path]`** — in the new
`tests/test_board_column_dialog.py`, pin the **current** behaviour of the column
modals through their existing entry points, with **no production change yet**:

- `open_column_edit(col_id)` (the header ✎ button, `:10053`) → `ColumnEditScreen`
  in `edit` mode → on save, `TaskManager.update_column` is called with the id
  **twice** (`col_id, col_id, title, color`) and the board refreshes **once**.
- `action_add_column` → `add_column(slug, title, color)` with the slug generated
  from the title.
- `action_delete_column` → `ColumnSelectScreen` → `DeleteColumnConfirmScreen`
  carrying the correct `task_count` → `delete_column`.

No such coverage exists today (no test drives `ColumnEditScreen` or
`DeleteColumnConfirmScreen` through `Pilot`), so this is the baseline the
`_apply_column_edit` extraction must not move.

## Step 1 — `_COMMANDS`: consume, do not re-derive

`_COMMANDS` (`:6246`) is a tuple of `(display, action_attr, help)`; both
`discover()` and `search()` go through `_resolved()` (`:6267`). Add two entries:

```python
("Manage Columns", "action_column_manage", "Reorder, add, edit, delete or merge columns"),
("Merge Columns",  "action_merge_columns", "Merge one or more columns into another"),
```

- `CommandPaletteParityTests`' three generic tests derive from `_COMMANDS`, so
  they cover the new entries **automatically** — do not write a second guard.
  `test_every_command_action_resolves_on_the_real_app_class` (`:232`) means both
  `action_*` names **must** exist on `KanbanApp` or the suite fails.
- Extend the guard only by adding the declaration assertions, mirroring
  `test_the_new_commands_are_declared` (`:238`).

`action_merge_columns` is a palette shortcut straight into the merge sub-flow;
`action_column_manage` opens the full dialog.

## Step 2 — `ColumnManageScreen`, bound to `e`

### The binding

```python
Binding("e", "column_manage", "Columns", show=True),
```

**Footer-visible.** t1418's `MultiRowFooter` reflows onto as many rows as width
needs, and `aidocs/framework/tui_conventions.md:409` now states verbatim that
*"there is no room in the footer" is no longer a reason to hide a binding*.
t1243_7's `m` was un-hidden by t1418 for exactly this reason.

### `check_action` gating — **corrected**

The original plan said to mirror `w` (`work_report`, `:6825`). **That is wrong.**
`w` additionally requires `self._get_focused_col_id() is not None` because it
reports on *the focused column*. This dialog operates on the **whole column
list** — requiring a focused column would make `e` dead on an empty or
filter-emptied board, which is exactly when a user wants to add a column.

Mirror instead the column-operation gate at `:6899`
(`move_col_right` / `move_col_left` / `toggle_column_collapsed`):

```python
elif action in ("column_manage", "merge_columns"):
    # Column management is board-scoped, not card-scoped: In-Flight /
    # By-Topic / By-Trail render derived lanes, not columns. Deliberately
    # NOT `w`'s gate — that one also demands a focused column because it
    # reports on one; this dialog edits the column LIST, so gating on focus
    # would kill it on an empty board, the case that most needs "Add".
    if self.base_filter in ("inflight", "bytopic", "bytrail"):
        return False
```

- **Do not** add either action to the ghost-card pre-gate (`:6759-6763`) — that
  list is card-scoped actions only.
- This keeps the gate at **zero** DOM queries and zero `_focused_card()` calls.
  `check_action` runs once per binding on every `refresh_bindings()`; t1243_7
  measured that path at 59.08 ms before it was fixed to 0.05 ms, and
  `test_board_move_command.py:714-737` pins the cost. Mirror that cost guard.

### Contents — reuse, never re-picker (AC7)

| Operation | Reuse |
|---|---|
| list + reorder | `ColumnManageItem(PickerItem)` rows over `manager.column_order`; `shift+up`/`shift+down` rewrite `column_order` wholesale then `save_metadata()` (generalises the one-step `_shift_column` at `:9980`) |
| add / edit | `ColumnEditScreen(manager, col_id=…, mode=…)` (`:6015`), pushed nested via `self.app.push_screen(…, callback)` |
| delete | `DeleteColumnConfirmScreen(col_conf, task_count)` (`:6089`) |
| merge sources | `WorkReportColumnSelectScreen(columns, initial)` (`:4879`) — a `SelectionList` multi-select over `(col_id, title)` pairs returning `list[str]` |
| merge destination | `ColumnSelectScreen(manager, "Merge into", columns=…)` (`:6213`) |

**Reuse `_work_report_columns()` (`:8607`) for the source list** — it already
returns ordered `(col_id, title)` pairs and hand-prepends
`("unordered", "Unsorted / Inbox")` **only when `unordered` holds tasks**, which
is precisely the plan's "list `unordered` as a source only when it holds tasks"
rule. Do not re-implement it. (Rename it or add a neutral alias if
`_work_report_*` reads oddly at the new call site; keep one implementation.)

### Refactor before adding (planning_conventions)

`_handle_column_edit_result` (`:10003`) mutates the manager, notifies, **and**
calls `refresh_board()`. The dialog must not recompose the board underneath
itself on every edit. Extract the mutate+notify half:

```python
def _apply_column_edit(self, result) -> bool:
    """Apply a ColumnEditScreen result. Returns True if anything changed."""
```

`_handle_column_edit_result` becomes `if self._apply_column_edit(result): self.refresh_board()`.
The dialog calls `_apply_column_edit`, sets its own `self._changed = True`, and
rebuilds only its own list. `ColumnManageScreen.dismiss(changed: bool)`; the
app's callback calls `refresh_board()` once, on close.

This keeps the header ✎ button path (`open_column_edit`, `:10053`) on exactly
the same code.

### Partial-merge reporting — branch on the sentinel, not just `complete`

Verified `MergeResult` (`:1066`): `merged`, `failed: tuple[(key, reason)]`,
`sources_removed`, `refused`; `complete = not (failed or refused)`. Sentinels are
module constants — **import them, do not re-spell the strings**:
`MERGE_METADATA_KEY` `"<metadata>"`, `MERGE_METADATA_LOCAL_KEY`
`"<metadata:local>"`, `MERGE_UNVERIFIABLE_KEY` `"<unverifiable>"` (`:1034-1039`).

The original plan branched on `result.complete` alone. **That conflates two
opposite outcomes**: `refused` means *nothing was written*, while `failed` means
*partial progress*. Report them differently, checking in this order:

```python
def _report_merge(self, result, dest_title, attempted: int) -> None:
    if result.refused:                      # input validation; NOTHING written
        self.notify(f"Merge refused — nothing changed: {reasons}", severity="error")
        return
    if result.complete:
        self.notify(f"Merged {len(result.merged)} tasks into {dest_title}",
                    severity="information")
        return
    keys = dict(result.failed)
    if MERGE_METADATA_LOCAL_KEY in keys:
        # The merge LANDED and the sources are durably removed. Re-offering the
        # merge would refuse with unknown_column. The retry is a re-save.
        msg = (f"Merged {len(result.merged)} into {dest_title}; columns removed, "
               "but collapsed state was not saved — it self-heals on next launch.")
    elif MERGE_METADATA_KEY in keys:
        msg = (f"Merged {len(result.merged)} tasks into {dest_title}, but the "
               "column list was not saved — re-run the merge to finish.")
    elif MERGE_UNVERIFIABLE_KEY in keys:
        msg = (f"Merged {len(result.merged)} into {dest_title}; source columns kept "
               f"because {files} could not be read — fix them and re-run.")
    else:
        msg = (f"Merged {len(result.merged)} of {attempted} into {dest_title} — "
               f"{len(result.failed)} failed, re-run to finish.")
    self.notify(msg, severity="warning")
```

A bare "Merged" toast on a partial merge is the specific failure this clause
exists to prevent. Per-member reasons (`write_failed:` / `not_attempted` /
`not_written` / `file_missing` / `unreadable`) need no per-reason wording — the
count plus "re-run" is the actionable part.

`attempted` = the number of member filenames gathered across all sources
**before** the call (`merged` alone cannot yield the denominator).

### Wiring notes

- `.picker-dialog` already carries the t1366 scroll/focus fix; style the new
  dialog with `#column_edit_dialog` / `#dep_picker_dialog` + `.picker-dialog`,
  adding no new ids unless layout demands it.
- **No `KNOWN_BINDING_SOURCES` edit.** `aitask_board` is already listed in
  `lib/shortcut_scopes.py:47` and `register_all_known_bindings()` introspects
  every class in the module. Follow the existing column modals and declare **no**
  `_shortcuts_scope` (they declare none); a new scope would only matter to the
  filtered `?`-editor sweep. `tests/test_shortcut_scopes.py` enforces this.
- Guard re-entry with the house idiom `if self._modal_is_active(): return`
  (`:8031`), as `action_collapse_column` does.

## Step 3 — Workstream C: confirmed absent, so take the simple arm

Verified 0 hits for `collapsed_groups` / `boardgroup` across `board/` and `lib/`.
`BOARD_KEYS == BOARD_LAYOUT_KEYS == ("boardcol", "boardidx")`, no group headers,
no composite keys. Build against the current model. **Do not** pre-build group
handling, and **do not** leave a note claiming an order that did not happen —
t1243_10 already carries the reciprocal note and owns the integration.

## Shared `BINDINGS` / `check_action` region

- **t1210_5** (Ready) adds `m`/`M` to By-Trail and edits the same `check_action`
  `bytrail` branches. **This child lands first**, so it gates `e` hidden in
  `bytrail` on its own and records the predicate in `## Notes for sibling tasks`
  for t1210_5 to rebase onto. No key conflict (`M` is unbound).
- **t1268** (landed) reworked By-Trail footer labels — no interaction.
- **t1418** (landed) supplies `MultiRowFooter`; verify the new label renders
  under it, not against a single-row footer.

---

## Tests — `tests/test_board_column_dialog.py` (new)

`tests/test_board_column_manage.py` is headless-by-design (t1377_4: "no Pilot, no
app"); the dialog needs `Pilot`, so it gets its own module. Mirror
`test_board_move_command.py`'s dual style: `_mock_app()` for gate/wiring tests,
real `KanbanApp` + `board_fixture` for behaviour.

| Case | Assertion |
|---|---|
| palette parity | `"Manage Columns"` / `"Merge Columns"` in `_COMMANDS`; both action attrs resolve on `KanbanApp` (the generic parity tests cover discover/search automatically) |
| binding declared once | `keys.count("e") == 1`, action `column_manage`, `show is True` (mirrors `test_the_m_binding_is_declared_once`) |
| gate per view | `check_action("column_manage")` is `False` in `inflight`/`bytopic`/`bytrail` — **`False`, not `None`**, or it renders greyed instead of hidden — and truthy in `all`/`locked`/`free` |
| gate on an empty board | `check_action("column_manage")` is **not** `False` with nothing focused — the discriminating test against re-using `w`'s gate |
| gate cost | zero `_focused_card` / `_get_focused_col_id` calls (mirror `test_board_move_command.py:714-737`) |
| live footer surface | via `Pilot`: `"column_manage"` in `_footer_actions(app)` in a kanban view, absent after `app._set_base_filter("bytopic")` |
| reorder | dialog reorder rewrites `column_order`, persists, and survives a **fresh** `TaskManager` over the same tree |
| merge e2e | through the real `KanbanApp` on `tests/lib/board_fixture.py`: sources gone from `columns` **and** `column_order`, members at the destination bottom in original relative order (assert the full filename sequence, not membership) |
| **partial merge → warning** | stub `merge_columns` to return a partial `MergeResult`; assert `severity == "warning"` and that the message names both counts. **Negative control:** make the handler branch on `complete` only and show this test fails |
| **`<metadata:local>` does not re-offer the merge** | assert the message does **not** say "re-run the merge" and does say the columns were removed — the one case where re-running refuses |
| `<metadata>` vs member-failure wording | distinct messages; both `warning` |
| refused → error | `refused`-only result takes the **error** path and says nothing changed; **not** the "Merged 0 of N" path |
| `unordered` source visibility | listed as a merge source only when it holds tasks (drive `_work_report_columns()`'s real output) |
| add / edit / delete via dialog | each still reaches the same `TaskManager` method and the board refreshes **once**, on close |
| `_apply_column_edit` extraction | `open_column_edit` (header ✎) still adds/edits identically — characterization, written **before** the extraction |

Frozen tables: `EXPECTED_CALL_SITES` (`test_board_persistence_seam.py`) and
`FLIP_TABLE` (`test_board_movement.py`) must stay green **unedited** — this task
adds UI only and no `reload_and_save_board_fields` call site.

## Verification

```bash
bash tests/run_all_python_tests.sh    # read ONLY the last line for the verdict
bash tests/test_shortcut_scopes.py 2>/dev/null || true
```

Live acceptance (real terminal) is covered by t1377_7, which already pins the
exact checklist. **Known pre-existing caveat to expect during that pass:** at
startup the search `Input` takes focus, and a focused `Input` makes Textual drop
every single-character binding from `active_bindings`, so the footer shows only
non-printable keys until Escape is pressed (t1418 confirmed this against a stock
`Footer` control; it is not caused by this task). Press Escape before judging
whether `e` is in the footer.

## Coordination — read before starting

`aitask_board.py` is 10820 lines and t1243_8…12 / t1210_5 are all live editors of
it. **Re-read immediately before implementing**, grep for symbols rather than
trusting the line numbers above, keep the new UI strictly above the render layer,
stage explicit paths, and never `git stash` / `git add -A` in this shared
checkout.

Step 9 (Post-Implementation) handles cleanup, archival, and merge.

## Risk

### Code-health risk: medium
- `_apply_column_edit` re-parents `_handle_column_edit_result`, which is the live path for the header ✎ button and three palette commands — a green, load-bearing surface with **no existing test coverage** (no test file drives `ColumnEditScreen` or `DeleteColumnConfirmScreen` through Pilot today) · severity: medium · → mitigation: inline pre-phase characterize_column_edit_path
- This dialog is the **first and only** consumer of `merge_columns`, so its reporting contract (3 sentinels × 5 member reasons) is encoded prose→code with nothing else to cross-check it; the failure mode is a reassuring toast on a merge that did not land · severity: medium · → mitigation: the sentinel matrix in the core test table, each with a discriminating assertion
- A modal, a binding, a `check_action` branch, two palette entries and a helper extraction land in a 10820-line file that five sibling tasks are still editing · severity: low · → mitigation: additive-only; full Python suite before commit
- `check_action` is the board's hottest path (t1243_7: 59.08 ms → 0.05 ms per footer sweep, pinned by a 25 ms cross-run benchmark). A new branch is O(1) and queries nothing, but the file's history shows this is where cost hides · severity: low · → mitigation: the zero-DOM-query cost guard in the core test table
- The dialog makes **delete** materially more discoverable while `delete_column` still carries the known `MoveResult`-trusts-unwritten-tasks defect spawned as **t1445** (`Ready`) — the same drain-and-strand shape `merge_columns` was hardened against. This task does not touch `delete_column`, so it neither causes nor fixes it · severity: medium · → mitigation: noted — t1445 tracked independently (user decision: do not block; delete is already reachable via the Ctrl+P palette and the dialog runs the identical `delete_column` code, so the added exposure is discoverability only, not a new failure mode)

### Goal-achievement risk: low
- Every reuse target was verified to exist at a named line, the merge engine is landed and fully tested headlessly, and t1377_7 already pins the acceptance checklist — so "does it work" has an independent ground truth · severity: low · → mitigation: none needed
- Footer visibility is asserted in tests via `active_bindings`, but whether the label is *readable* at narrow widths is only provable in a real terminal · severity: low · → mitigation: covered by t1377_7's live pass

### Planned mitigations
- timing: pre-phase | name: characterize_column_edit_path | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (`_apply_column_edit` re-parents an untested load-bearing path) | desc: Pin the current add/edit/delete behaviour through open_column_edit and the palette actions before the helper extraction, so a regression in the header-button path fails loudly.

**Reassessment after inlining:** the single confirmed mitigation is an additive
characterization test in a file this plan already creates, and it is written
before the only refactor in the task. It makes code-health risk 1 *detectable*
without changing the plan's shape. Code-health stays **medium** (risk 2, the
sole-consumer reporting contract, and risk 5, t1445, are unchanged);
goal-achievement stays **low**.

## Post-Review Changes

### Change Request 1 (2026-08-07 04:30)

- **Requested by user:** three review findings, all verified CONFIRMED against
  source before being addressed.
- **Changes made:**
  1. **(high, blocking) The command palette bypassed the view gate.** The palette
     resolves `action_*` by name and never calls `check_action`, so Ctrl+P →
     "Manage Columns" / "Merge Columns" opened the persistent-column editor from
     In-Flight / By-Topic / By-Trail even though `e` is hidden there. The finding
     is exactly the lesson `action_move_to_column` already records at its own
     re-check (t1243_7, `aitask_board.py:8547-8550`) — missed when this dialog was
     written. Added the same base-filter rejection inside `_open_column_manage`,
     the shared opener both actions route through, so it cannot be added to one
     entry point and forgotten on the other. It **notifies** rather than
     returning silently (unlike `m`): a palette command is deliberately clicked,
     so a silent no-op reads as a bug. New `PaletteBypassTests` covers all three
     derived views for both actions, plus the kanban-view positive control and
     the `start_in_merge` routing. Verified live in tmux: the toast appears and
     no dialog opens in By-Topic; the same command opens normally in All.
  2. **(medium) The `<unverifiable>` message stated the blocker but not the
     remedy.** It named the unreadable files and that the sources were kept, but
     omitted the recovery direction the plan specified. Appended "— fix those
     file(s) and re-run the merge to finish." and asserted both halves in
     `MergeReportingTests`.
  3. **(low) The synthetic lane was reported by raw id.** `_title_of` fell back to
     `col_id` when `get_column_conf` returned None, which it always does for
     `unordered` — so a merge from/into the inbox was confirmed and toasted as
     "unordered" while the picker the user had just clicked said "Unsorted /
     Inbox". Now delegates to the existing `KanbanApp._column_title` (`:9045`),
     which already owns that mapping.
- **Files affected:** `.aitask-scripts/board/aitask_board.py`,
  `tests/test_board_column_dialog.py`.
- **Verification:** each fix has a negative control with a named failing test —
  removing the palette guard fails `test_manage_is_rejected_in_every_derived_view`
  and `test_merge_is_rejected_in_every_derived_view`; restoring the raw-id
  fallback fails `test_the_synthetic_lane_is_named_not_shown_as_its_raw_id`;
  dropping the recovery sentence fails
  `test_unverifiable_sentinel_names_the_files_AND_the_recovery`. Full Python
  suite green.

## Final Implementation Notes

- **Actual work done:** `.aitask-scripts/board/aitask_board.py` — `ColumnManageScreen`
  + `ColumnManageItem` + `MergeColumnsConfirmScreen`; `Binding("e",
  "column_manage", "Columns")` (shown); the `column_manage` / `merge_columns`
  branch in `check_action`; two `_COMMANDS` entries; `action_column_manage` /
  `action_merge_columns` / `_open_column_manage` / `_merge_source_columns` /
  `_report_merge`; the `_apply_column_edit` extraction; CSS for
  `#column_manage_dialog`; `WorkReportColumnSelectScreen` generalised to
  `ColumnMultiSelectScreen(columns, initial, prompt=…)`; and the corrected
  `update_column` rename comment. `tests/test_board_column_dialog.py` — new,
  40 tests. `tests/test_board_move_command.py` — one added declaration
  assertion (extending t1243_7's guard as its sibling note instructed).
  `tests/test_board_work_report.py` — 4 references retargeted to the renamed
  class.

- **Deviations from plan:**
  1. **The `check_action` gate mirrors `move_col_*`, not `w`.** The plan said to
     mirror `work_report`; verification showed `w` *additionally* requires a
     focused column because it reports on one. Copying it would have made `e`
     dead on an empty or filter-emptied board — the case that most needs "Add".
     Pinned by `test_available_with_nothing_focused`, whose negative control
     (restoring `w`'s gate) also breaks three live tests.
  2. **Merge reporting branches on the sentinel, not on `complete` alone**, and
     separates `refused` (nothing written → **error**, "nothing changed") from
     `failed` (partial → **warning**). The plan's `complete`-only shape conflated
     them.
  3. **`ColumnMultiSelectScreen` reuse required a rename**, not just a call. The
     plan said "reuse `WorkReportColumnSelectScreen`"; using a work-report-named
     class for merge sources would have been dishonest, so it was parameterised
     by `prompt` and renamed, with its 4 test references retargeted.
  4. **A fifth "Close" button was designed and then removed** — see below.

- **Issues encountered:** four defects, each fixed and pinned by a test whose
  negative control reproduces it. **Three were invisible to unit tests.**
  1. **My own harness hid a case.** `_apply_column_edit` was absent from the
     mock's `_REAL_METHODS`, so it resolved to a truthy auto-MagicMock and
     `_handle_column_edit_result`'s "changed?" branch always fired — the
     cancelled-edit test was silently vacuous. Caught by the pre-phase
     characterization the moment the extraction landed, which is exactly what
     that mitigation was for. Same class of bug t1243_7 recorded for
     `_focused_placeholder`.
  2. **Button row clipped at 100 columns.** `#detail_buttons` is
     `align: center middle` with no wrapping, so a five-button row was cut off —
     "Close" was visible in the DOM but unreachable on screen. Found only in a
     live tmux capture. Dropped the button (Esc is in the dialog's own hint line
     and matches every other modal here) and added a width test comparing the
     summed button widths against the dialog width.
  3. **⚠ The board never refreshed after a merge — the sharpest bug in the
     task.** `KanbanApp` binds `escape` with `priority=True`, so
     `action_focus_board` wins over the modal's own binding and closes any active
     modal with a bare `self.screen.dismiss()` — **discarding the result**. This
     dialog is the first modal whose dismiss value carries meaning (the "did
     anything change?" flag), so a merge closed with Escape left the board
     rendering the merged-away column until the next manual `r`. Every unit test
     passed; it was visible only because the board *behind* the dialog was stale
     in a real terminal. Fixed via `handle_escape`, the hook
     `action_focus_board` already checks for and which had **zero implementers**
     before this task. The missing test (a *changed* dialog must refresh exactly
     once) was written first and observed failing `0 != 1`.
  4. **The command palette bypassed the view gate** — see Post-Review Changes
     above. The palette resolves `action_*` by name and never consults
     `check_action`; t1243_7 had already recorded this exact lesson at its own
     re-check and it was missed here.

  The recurring lesson: **the gate on a binding is not a gate on the action, and
  a passing test suite says nothing about what the surface behind a modal is
  showing.** Both of the worst defects needed a real terminal or a second entry
  point to surface.

- **Key decisions:**
  - **Column rename stays unreachable** (user decision at planning). Ids are
    auto-slugged, so re-slugging on a title edit would rewrite every member
    task's `boardcol` as a side effect of a cosmetic change, and ids are also
    referenced by the work-report protocol. t1377_4's comment claiming the path
    was "dead until t1377_5 makes the rename reachable" was rewritten to say it
    is dormant *by decision*, so the next reader does not treat it as an
    unfinished handoff. Its collapsed-state migration fix is untouched.
  - **Refresh is deferred to close, not per edit** — a modal that recomposed the
    board under itself once per operation. Both halves are pinned (refresh
    exactly once when changed; never when untouched).
  - **The palette guard notifies; `m`'s equivalent returns silently.** A keypress
    that does nothing is unremarkable; a palette entry the user deliberately
    clicked doing nothing reads as a bug.
  - **Live acceptance ran against a throwaway fixture tree**, never the real
    board — the flow mutates column config, and a stray keypress on the real
    board would have been destructive.

- **Upstream defects identified:**
  - `tests/lib/board_fixture.py:561-583 (PristineTreeMixin) — restores only
    **/*.md, while snapshot() in the same module treats metadata/board_config*.json
    as part of the tree. Any test class that mutates COLUMNS leaks board config
    into the next test, and the leak is self-concealing: with the column already
    dropped from config, merge_columns refuses it as unknown_column and writes
    nothing, while a "the source column was removed" assertion still passes —
    because the previous test removed it. Cost me a vacuous pair of assertions.
    Worked around locally with a _PristineConfigMixin in
    tests/test_board_column_dialog.py rather than editing a harness 31 modules
    share.`
  - `.aitask-scripts/board/aitask_board.py:8223-8230 (action_focus_board) — the
    app's priority=True escape binding closes ANY active modal with a bare
    self.screen.dismiss(), discarding the dismiss result. Every modal whose
    dismiss value carries meaning silently loses it when closed with Escape;
    it is benign only because every other board modal happens to treat None as
    "cancelled". The handle_escape hook checked one line above is the escape
    valve and had no implementers until this task. A modal author has no way to
    discover this except by hitting it.`

- **Notes for sibling tasks:**
  - **t1210_5 (`Ready`, lands AFTER this)** — the plan assumed t1210_5 would land
    first; it did not, so this task gated `bytrail` itself. The predicate to
    rebase onto is `elif action in ("column_manage", "merge_columns"): if
    self.base_filter in ("inflight", "bytopic", "bytrail"): return False`. `e` is
    taken; `M` and `G` remain unbound. **When you add a palette entry, re-check
    the gate inside the `action_*` too** — `check_action` alone is not a gate.
  - **t1377_6 (docs)** — document: the `e` key ("Columns" in the footer), the
    Manage Columns dialog (reorder via `shift+↑/↓`, Enter to edit, Esc to close,
    Add/Edit/Delete/Merge buttons), the two palette entries "Manage Columns" and
    "Merge Columns", that column management is unavailable in In-Flight /
    By-Topic / By-Trail, and that merge accepts N sources including Unsorted /
    Inbox (offered only when it holds tasks). Column **rename** is deliberately
    not a feature — do not document it.
  - **t1377_7 (manual verification)** — its checklist was written before this
    task and predates three behaviours worth adding, each of which was a real
    defect caught late here:
    - Ctrl+P → "Manage Columns" / "Merge Columns" from In-Flight / By-Topic /
      By-Trail must warn and open **nothing** (the palette bypasses
      `check_action`; the binding being hidden is not sufficient).
    - After a merge, closing the dialog **with Escape** (not a button) must
      leave the board showing the new column set — the escape path discards the
      dismiss result unless `handle_escape` is honoured.
    - Merging from/into the inbox must say "Unsorted / Inbox" in the
      confirmation and the toast, never the raw id `unordered`.
    Also note the pre-existing startup quirk (t1418): the search `Input` holds
    focus at launch and Textual drops every single-character binding from the
    footer until Escape is pressed — press Escape before judging whether
    `e Columns` is present.
  - **t1243_10** — `merge_columns` and the fixed `update_column` still need their
    composite-group-key half when `collapsed_groups` lands; `_title_of` in
    `ColumnManageScreen` delegates to `KanbanApp._column_title`, so a
    group-aware title only needs changing there.
  - **t1445** — the `e` dialog adds a second, more discoverable entry point into
    `delete_column`, which still trusts `MoveResult` and can count a task as
    moved that was never written. Not blocked on (user decision), but more users
    can now reach it.

- **t1445** — the `e` dialog adds a **second, more discoverable entry point**
  into `delete_column`, which still trusts `MoveResult` and can count a task as
  moved that was never written. This task deliberately does not block on it
  (user decision), but the fix is now reachable by more users; treat that as
  raising its priority rather than as new scope here.
- **Manual-verification failure:** item "[t1377_5] Add, edit and delete a column through the new dialog and confirm each still works as it did from the command palette" failed; follow-up task t1454.
