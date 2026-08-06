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

## Notes for sibling tasks

*(fill in at Step 8 — record the final `e` binding + `check_action` predicate for
t1210_5 to rebase onto and for t1377_6's docs, and the `_apply_column_edit`
seam.)*

- **t1445** — the `e` dialog adds a **second, more discoverable entry point**
  into `delete_column`, which still trusts `MoveResult` and can count a task as
  moved that was never written. This task deliberately does not block on it
  (user decision), but the fix is now reachable by more users; treat that as
  raising its priority rather than as new scope here.
