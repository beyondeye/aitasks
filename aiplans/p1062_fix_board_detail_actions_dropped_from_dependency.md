---
Task: t1062_fix_board_detail_actions_dropped_from_dependency.md
Worktree: (current branch — profile fast)
Branch: (current branch — profile fast)
Base branch: main
---

# Plan: Fix board task-detail actions dropped when opened from a dependency (t1062)

## Context

In `ait board`, opening a task's detail screen and then opening a **dependency**
(or parent / child / verifies / folded) task's detail from within it leaves that
nested screen's actions dead. Repro: open task **968** detail → open dependency
**929_3** detail → press **p** (pick). Instead of picking 929_3, the screen
bounces back to 968 and nothing happens.

**Root cause.** `TaskDetailScreen` (`.aitask-scripts/board/aitask_board.py:3119`)
does not perform its actions itself — it signals every action to its caller via
`self.dismiss(<result>)` (`"pick"`, `"edit"`, `"edit_plan"`, `"rename"`,
`"delete_archive"`, `"brainstorm"`, `"reverted"`, `"locked"`, `"unlocked"`) and
relies on the **caller's result callback** to act on it. Only the top-level board
push wires that callback:

```python
self.push_screen(TaskDetailScreen(focused.task_data, self.manager), check_edit)  # :5336
```

Every **nested** open pushes `TaskDetailScreen` with **no callback**, so the
dismiss result is silently discarded and the screen just pops back to the parent
detail. This affects *all* actions from a nested detail, not just pick — only
Back/Escape (a bare `dismiss()`) works. The callback-less sites:

| Site | Location | read_only today |
|------|----------|-----------------|
| `DependsField._open_dep` (single) | `:1630` | `archived` |
| `DependsField` dep-picker item `DepPickerItem` | `:2479` | `archived` |
| `VerifiesField._open_verify` (single) | `:1708` | `archived` |
| `ChildrenField._open_child` (single) | `:1840` | `archived` |
| `ChildPickerItem` | `:2783` | `archived` |
| `FoldedTasksField._open_folded` (single) | `:1895` | `True` |
| `FoldedTaskPickerItem` | `:2845` | `True` |
| `ParentField._open_parent` | `:2155` | `archived` |
| target/anchor field `_open_target` | `:2119` | `archived` |
| `_reload_detail_screen` (module fn) | `:1805` | (none → False) |

(There may also be a `VerifiesField` multi-picker item — handle every
`push_screen(TaskDetailScreen(...))` site found by the grep below; the list above
is the confirmed set.)

## Approach (structural — one wired helper, no callback-less push possible)

Add a single app-level method on `KanbanApp` (class at `:4235`) that is the **only**
way a `TaskDetailScreen` gets pushed, always wired to a result handler. Route every
open site (board + all nested) through it. This makes "push without a callback"
structurally impossible rather than patching pick at one site (which would leave 7
other actions broken).

### 1. Extract the result handler from the `check_edit` closure

Today `check_edit` (`:5235`–`:5335`, inside `action_view_details`) is a closure over
`focused` — a board `TaskCard`. Lift it to a method that operates on the **dismissed
screen's task object**, and accepts the **source card when one exists** (board path)
so the existing board refresh stays byte-for-byte unchanged while nested/cardless
opens get a safe full refresh:

```python
def _on_detail_result(self, task_data, result, source_card=None):
    # body = current check_edit, with focused.task_data -> task_data throughout.
    # The if/elif structure is UNCHANGED: edit/edit_plan fall through to the
    # refresh tail; pick/brainstorm/rename/delete_archive keep their early returns.
```

Substitution rules inside the lifted body:

- `focused.task_data` → `task_data` everywhere (pick branch `:5242`, its inner
  `on_pick_result` `:5260`/`:5269`, the `run_aitask_pick` fallback `:5272`,
  `brainstorm` `:5274`/`:5277`, `rename` `:5283`/`:5285`, `delete_archive`
  `:5288`–`:5318`).
- **Do NOT substitute `focused.column_id`** — concern (2). Instead branch the
  granular-refresh tail (`:5321`–`:5335`) on `source_card`:

```python
# tail — reached for: edit, edit_plan, reverted, locked, unlocked, and None (Escape)
if not result and source_card is None:
    return                       # concern (3): nested Back/Escape stays passive
needs_locks = result in ("locked", "unlocked")
filename = task_data.filename
self.manager.reload_task(filename)
self.manager.refresh_git_status()
if needs_locks:
    self.manager.refresh_lock_map()
if source_card is not None:
    # BOARD PATH — identical to today's code (uses the visible card's column,
    # which is correct for expanded child cards; board_col is not consulted).
    old_col = source_card.column_id
    task = self.manager.task_datas.get(filename) or self.manager.child_task_datas.get(filename)
    new_col = task.board_col if task else old_col
    if new_col != old_col:
        self.refresh_columns({old_col, new_col}, refocus_filename=filename)
    else:
        self.refresh_column(old_col, refocus_filename=filename)
else:
    # NESTED/CARDLESS PATH — full board rebuild; _refocus_card (:4719) no-ops
    # when the (possibly filtered/off-board) task has no visible card.
    self.refresh_board(refocus_filename=filename)
```

This resolves concern (2) — the board path never touches `board_col`, so expanded
child cards refresh exactly as today — and concern (3) — a bare Escape from a nested
detail returns immediately with no reload/refresh, while the board's existing
refresh-on-close is preserved (its `source_card` is non-None).

### 2. Add the `open_task_detail` helper

```python
def open_task_detail(self, task, read_only=None, source_card=None):
    if read_only is None:
        read_only = getattr(task, "archived", False)
    self.push_screen(
        TaskDetailScreen(task, self.manager, read_only=read_only),
        lambda result: self._on_detail_result(task, result, source_card),
    )
```

### 3. Re-point `action_view_details` (board, `:5232`)

Replace the inline `check_edit` def + `self.push_screen(TaskDetailScreen(...), check_edit)`
(`:5336`) with:

```python
def action_view_details(self):
    focused = self._focused_card()
    if focused:
        self.open_task_detail(focused.task_data, source_card=focused)
```

Passing `source_card=focused` makes the board path's refresh identical to today's.

Per the agreed decision, this **unifies** read_only: archived tasks opened from the
board become read-only (matching every nested path), removing the current
archived-editable quirk.

### 4. Re-point every nested open site

**Replace only the `push_screen(TaskDetailScreen(...))` expression — preserve every
surrounding line**, especially any preceding `self.screen.dismiss()` (the picker
items dismiss the *picker* before opening the detail; dropping it would stack the
detail on top of the still-open picker).

Default (archived-derived) read_only sites:

```python
self.app.open_task_detail(task)            # DependsField, VerifiesField, ChildrenField,
                                           # ParentField, _open_target
```

Picker items keep their `self.screen.dismiss()` line, then call the helper:

```python
self.screen.dismiss()                      # DepPickerItem, ChildPickerItem  (unchanged)
self.app.open_task_detail(task)
```

Forced-read-only sites (folded) pass it explicitly:

```python
self.app.open_task_detail(task, read_only=True)              # FoldedTasksField
self.screen.dismiss(); self.app.open_task_detail(task, read_only=True)  # FoldedTaskPickerItem
```

Module-level `_reload_detail_screen(app, task, manager)` (`:1801`) — **keep its
dismiss-then-push (replace) semantics**, route the push through the helper:

```python
def _reload_detail_screen(app, task, manager):
    task.load()
    app.screen.dismiss()        # pop the stale detail FIRST (unchanged) — without this
    app.open_task_detail(task)  # the refreshed detail would stack on the stale one and
                                # Escape would reveal outdated content
```

(Dismissing the stale detail now also fires *its* wired callback with `result=None`;
that is harmless — passive for a nested detail, a benign board refresh for a
board-opened one — and the re-push restores the refreshed detail on top.)

**Find-all guard:** before editing, run
`grep -n "push_screen(\s*$\|TaskDetailScreen(" .aitask-scripts/board/aitask_board.py`
and convert every `push_screen(TaskDetailScreen(...))` occurrence (the multi-line
form hid sites from a naive single-line grep). After editing, re-grep to confirm the
**only** remaining `push_screen(TaskDetailScreen` is inside `open_task_detail`.

## Files to modify

- `.aitask-scripts/board/aitask_board.py` — add `open_task_detail` + `_on_detail_result`
  on `KanbanApp`; re-point `action_view_details` and all ~10 nested open sites.
- `tests/test_board_detail_nested_actions.py` — new Textual-pilot regression test
  (mirrors `tests/test_board_detail_arrow_nav.py`'s harness: chdir to repo root,
  import after chdir, drive the real `KanbanApp` via `app.run_test()`).

## Tests (real entry point + behavioral)

New `tests/test_board_detail_nested_actions.py` (mirrors the `test_board_detail_arrow_nav.py`
harness). Behavioral cases skipTest if the board loads < 2 parent tasks. Helper:
`assert_pick_routes_to(app, pilot, task)` — stub `app._resolve_pick_command =
lambda num: "true"`, `press("p")`, assert `app.screen` is now `AgentCommandScreen`
(imported from `aitask_board`) with `operation_args == [<task number without 't'>]`.
*Before the fix* the bare dismiss pops back with no callback → no `AgentCommandScreen`
is pushed, so each case fails — true regression tests. No tmux/agent launches occur:
pressing `p` only pushes `AgentCommandScreen`; we never dismiss it, so
`on_pick_result`/`launch_in_tmux` never run.

1. **Seam routes pick to the correct task.** `app.open_task_detail(taskB)`, then
   `assert_pick_routes_to(app, pilot, taskB)`. Isolated coverage of the wired helper.

2. **Multi-dep picker path (the actual repro).** Build
   `dep_items = [(numB, taskB, "…"), (numC, taskC, "…")]` and
   `app.push_screen(DependencyPickerScreen(dep_items, app.manager, taskA))`; query the
   `DepPickerItem` for taskB, `.focus()` it, `await pilot.press("enter")`. This is the
   exact 968→929_3 path: `DepPickerItem.on_key` dismisses the picker and (post-fix)
   calls `app.open_task_detail(taskB)`. Assert `app.screen.task_data is taskB`, then
   `assert_pick_routes_to(app, pilot, taskB)`.

3. **Detail-screen history / Esc-pop stack preserved.** `app.open_task_detail(taskA,
   source_card=None)` then `app.open_task_detail(taskB)` (stack now has both details).
   `await pilot.press("escape")` → assert `app.screen` is a `TaskDetailScreen` whose
   `task_data is taskA` (B popped, A revealed — not the board). `press("escape")` again
   → assert `app.screen` is no longer a `TaskDetailScreen` (back to the board). Guards
   that wiring the result callback did not break multi-level push/pop navigation.

4. **Structural invariant guard (covers the find-all conversion for every site).**
   Read the `aitask_board.py` source and assert there is **exactly one**
   `push_screen(<ws>TaskDetailScreen(` occurrence and that it lies within the
   `open_task_detail` method body. This fails loudly if any nested site
   (`ParentField`, `ChildPickerItem`, `FoldedTaskPickerItem`, `VerifiesField`,
   `_reload_detail_screen`, …) is missed or a new callback-less push is added later —
   directly enforcing the "no callback-less push possible" contract that behavioral
   tests on representative shapes (1–2) cannot cover exhaustively.

Run:
```bash
python3 -m pytest tests/test_board_detail_nested_actions.py -v
bash tests/run_all_python_tests.sh        # ensure no regression in board pilot tests
```

Manual sanity (Step 8): `ait board` → open a task with a dependency → open the
dependency → press `p`; confirm it picks the dependency. Spot-check edit (`e`),
rename (`n`), brainstorm (`b`) from a nested detail.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9: review/approve (Step 8), commit code as
`bug: <desc> (t1062)` (regular `git`), update + commit plan via `./ait git`, then
merge approval, archival, push.

## Risk

### Code-health risk: low
- Consolidation onto one helper. The board path is held behavior-identical by passing
  `source_card=focused` (the granular refresh uses the visible card's `column_id`
  exactly as today — no `board_col` substitution, so expanded child cards are
  unaffected). Nested opens use a full board refresh. Blast radius is wide in *line
  count* but each nested edit is an identical one-liner; the structural-invariant test
  + post-edit re-grep catch any missed site. · severity: low · → mitigation: TBD
- Unifying read_only changes board behavior for archived tasks (now read-only).
  Intended and user-approved; actionable buttons were already disabled for archived
  via other paths. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- The fix targets the confirmed root cause (callback-less push) and the regression
  test asserts the exact reported repro (pick on a nested dependency routes to that
  dependency). · severity: low · → mitigation: None needed.

## Final Implementation Notes

- **Actual work done:** Added `KanbanApp.open_task_detail` (the single wired push
  site) and `KanbanApp._on_detail_result` (lifted from the `check_edit` closure,
  operating on the dismissed screen's task with a `source_card`-branched refresh
  tail and a passive nested-Escape early return). Re-pointed every nested
  `TaskDetailScreen` open (Depends/Verifies/Children/Parent/target fields, the three
  picker items, and `_reload_detail_screen`) through the helper. Added
  `tests/test_board_detail_nested_actions.py` (4 cases) and a structural-invariant
  test (exactly one `TaskDetailScreen(` instantiation, inside `open_task_detail`).

- **Deviations from plan:** Added a fourth method, `KanbanApp.replace_screen_with_detail`,
  not in the approved plan. During testing the multi-dependency picker repro
  (968→929_3) still failed even with the callback wired: doing `self.screen.dismiss()`
  immediately followed by `push_screen(..., callback)` **inside a picker item's
  `on_key` handler** pushes the screen but silently drops the result callback (Textual
  processes the dismiss and the push in the same message). `call_after_refresh` was
  insufficient; only `call_later` (deferring the open past the current message) lets
  the callback attach. `replace_screen_with_detail` encapsulates this dismiss +
  deferred-open so the three picker items (`DepPickerItem`, `ChildPickerItem`,
  `FoldedTaskPickerItem`) and `_reload_detail_screen` share one documented site. The
  single-field opens (no preceding dismiss) attach the callback fine and stayed plain
  `open_task_detail` calls.

- **Issues encountered:** The picker-path callback drop above, root-caused via Pilot
  experiments (direct-call vs real-keypress; `direct`/`call_after_refresh`/`call_later`
  deferral modes). Resolved with the `call_later` deferral.

- **Key decisions:** Unified `read_only` (archived ⇒ read-only) across all open paths,
  including the board's own open — user-approved, removes the prior archived-editable
  quirk. Kept the board path's refresh byte-identical by threading the originating
  `source_card`, so expanded child cards (whose visible column ≠ their `board_col`)
  are unaffected.

- **Upstream defects identified:** None.
