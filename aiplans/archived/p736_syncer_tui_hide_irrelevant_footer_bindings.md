---
Task: t736_syncer_tui_hide_irrelevant_footer_bindings.md
Worktree: (current branch — profile fast, create_worktree=false)
Branch: main
Base branch: main
---

# Plan: Hide irrelevant footer bindings in `ait syncer` based on selected row

## Context

The `ait syncer` TUI has five visible footer bindings — `r` Refresh, `s` Sync (data), `u` Pull, `p` Push, `f` Fetch on/off — but three of them (`s`, `u`, `p`) are context-dependent on the row selected in the branches table:

- `s` (sync_data) is meaningful only when the `aitask-data` row is selected.
- `u`/`p` (pull/push) are meaningful only when the `main` row is selected.

Today the action handlers (`action_sync_data`, `action_pull`, `action_push` in `.aitask-scripts/syncer/syncer_app.py:248-273`) each do an in-action `if self._selected_ref_name() != …` guard and emit a corrective `notify(...)` toast on the wrong row. The footer keeps showing all five bindings regardless of the selection — so users see the full set, press one that doesn't apply, and get a toast telling them to use a different key. The intent is already row-scoped; the footer just doesn't reflect it.

The fix is to follow Textual's canonical idiom — a `check_action` method that returns `None` to hide a binding from the footer (and prevent it from firing) — already used in this codebase by `monitor_app.py:1256` and `aitask_board.py:3333`. The footer is re-evaluated when `self.refresh_bindings()` is called; in `monitor_app.py:1242` this happens whenever the active zone changes. For the syncer, the equivalent trigger is the existing `on_data_table_row_highlighted` handler.

## Files to modify

- `.aitask-scripts/syncer/syncer_app.py` — only file touched.

## Changes

### Change 1 — Add `check_action` to `SyncerApp`

Insert after `_update_subtitle` (currently line 134-136) or before `action_refresh` — somewhere in the early action area. The method returns `None` to hide bindings whose action is not applicable to the selected row, and `True` for everything else (i.e. the default permissive behavior). Universal bindings (`r`, `f`, `q`, `j`, `a`) are not touched — `True` is returned by the fallthrough.

```python
def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
    """Hide row-scoped bindings from the footer when they don't apply."""
    selected = self._selected_ref_name()
    if action == "sync_data" and selected != "aitask-data":
        return None
    if action in ("pull", "push") and selected != "main":
        return None
    return True
```

Notes:
- `_selected_ref_name()` (line 188) is safe to call from `check_action` — it reads the DataTable cursor and falls back to row 0 (`"main"`) when the table is empty or the cursor is unset, so the very first footer render before `on_mount` populates the table will get the correct `main`-row footer (showing `u`/`p`, hiding `s`).
- Returning `None` (vs `False`): `None` hides the binding entirely from the footer AND prevents the action from firing. `False` would show it greyed out. We want hidden — matches the user's request ("should not be shown") and the board/monitor convention.

### Change 2 — Call `refresh_bindings()` on row change

Update `on_data_table_row_highlighted` (line 243):

```python
def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
    self._refresh_detail()
    self.refresh_bindings()
```

This re-evaluates `check_action` for every binding and re-renders the Footer. Pattern reference: `monitor_app.py:1242`.

### Change 3 — Drop the dead notify guards in the three action handlers

Once `check_action` returns `None` for an inapplicable action, Textual prevents the action from firing — the body of `action_sync_data`/`action_pull`/`action_push` is unreachable on the wrong row. Remove the row-name guards and their corrective `notify(...)` calls so the source matches the new contract.

Before (lines 248-273, three handlers):
```python
def action_sync_data(self) -> None:
    if self._selected_ref_name() != "aitask-data":
        self.notify(
            "Sync (s) is for aitask-data only — use u/p for main.",
            severity="warning",
        )
        return
    self._sync_data_worker()

def action_pull(self) -> None:
    if self._selected_ref_name() != "main":
        self.notify(
            "Pull (u) is wired for main only — use s to sync aitask-data.",
            severity="warning",
        )
        return
    self._main_pull_worker()

def action_push(self) -> None:
    if self._selected_ref_name() != "main":
        self.notify(
            "Push (p) is wired for main only — use s to sync aitask-data.",
            severity="warning",
        )
        return
    self._main_push_worker()
```

After:
```python
def action_sync_data(self) -> None:
    self._sync_data_worker()

def action_pull(self) -> None:
    self._main_pull_worker()

def action_push(self) -> None:
    self._main_push_worker()
```

No comments — the row-scoping is self-evident from `check_action` immediately above.

### Out of scope (no change)

- `action_agent_resolve` (line 275) — its binding is already `show=False` and it's enabled only when `_last_failure` is set. Not touched.
- The action workers, `_main_worktree`, `_git`, failure-screen flow — unchanged.
- The `s` binding label "Sync (data)" — keep as-is; the footer will only show it on the `aitask-data` row, where the parenthetical is informative.

## Verification

Manual TUI verification (the syncer is a Textual TUI; aitasks does not have automated tests for footer rendering):

1. Launch `./ait syncer` in a tmux pane inside the project.
2. **`main` row footer:** With cursor on `main` (default — first row), the footer shows: Refresh, Pull, Push, Fetch on/off, Quit. **No `s` Sync.**
3. **`aitask-data` row footer:** Press ↓ to move cursor to `aitask-data`. The footer updates to: Refresh, Sync (data), Fetch on/off, Quit. **No `u` Pull, no `p` Push.**
4. **Round trip:** Press ↑ back to `main`; the footer reverts to the main set.
5. **Functional regression spot-check:** Press `r` (refresh) — both rows should refresh. Press `f` — toggles fetch and shows a notify; subtitle updates. Press `q` — quits.
6. **Action no-fire on hidden bindings:** Pressing `s` while `main` is selected does nothing (no notify, no worker). Pressing `u` or `p` while `aitask-data` is selected does nothing. (Previously these would emit corrective toasts; now the bindings are hidden and Textual blocks the action.)
7. **Source check:** Confirm the three notify-warning strings are gone:
   ```bash
   grep -n "Sync (s) is for aitask-data only\|Pull (u) is wired for main only\|Push (p) is wired for main only" \
     .aitask-scripts/syncer/syncer_app.py
   ```
   Expected: no matches.

No automated test added — footer rendering does not have a snapshot-test harness in this project, and the syncer has no existing pytest coverage. If/when one is added (e.g., as part of the brainstorm-integration work), it should cover these footer cases — defer to a sibling refactor task at that time.

## Step 9 (post-implementation)

- Profile is `fast` with `create_worktree: false` — no worktree to clean up. Step 9 will run the standard archival via `aitask_archive.sh 736`.
- No linked issue, no PR, no folded tasks.

## Estimated diff size

~9 lines removed, ~10 lines added in `.aitask-scripts/syncer/syncer_app.py`. Single file, single commit.

## Post-Review Changes

### Change Request 1 (2026-05-04 13:00)

- **Requested by user:** Add a progress indicator (Textual standard widget) while a sync/pull/push operation is running. Today there is only a notify on completion, so the user has no in-flight feedback that something is happening.
- **Changes made:**
  - Added `_set_busy(self, busy: bool)` helper on `SyncerApp` that toggles `self.query_one("#branches", DataTable).loading`. Setting `Widget.loading = True` is Textual's canonical, built-in way to overlay a `LoadingIndicator` on a widget — no custom widget code needed.
  - `action_sync_data`/`action_pull`/`action_push` each call `self._set_busy(True)` before kicking off their respective worker.
  - `_sync_data_worker`, `_main_pull_worker`, and `_main_push_worker` each have their existing body wrapped in a `try` block; a `finally` clause queues `self.call_from_thread(self._set_busy, False)` so the indicator is always cleared regardless of which exit path the worker takes (early-return notifies, `_fail` failure-screen path, success path, or unexpected exception).
  - The indicator is intentionally NOT plumbed through `_refresh_worker` (background, runs every 30s automatically) or `_run_interactive_sync_shared` (user is interactively resolving conflicts). Scope kept to the three explicit user-triggered slow operations.
- **Files affected:** `.aitask-scripts/syncer/syncer_app.py` (only file).
- **Verification additions:**
  - Press `s` on `aitask-data` row → branches table shows the LoadingIndicator overlay until the sync completes (notify fires) or fails (failure screen pushes).
  - Press `u` or `p` on `main` row → same overlay behavior on success and on `_fail` paths.
  - Periodic 30s tick should NOT show the loading overlay (refresh worker is not wrapped).
  - On worker exception (e.g. `run_sync_batch` raises) the overlay still clears thanks to `try/finally`.

## Final Implementation Notes

- **Actual work done:**
  - Added `check_action(action, parameters)` to `SyncerApp` returning `None` for `sync_data` when the selected row is not `aitask-data`, and for `pull`/`push` when the selected row is not `main`. Returns `True` for everything else, leaving universal bindings (`r`, `f`, `q`, `j`, `a`) unaffected.
  - Added `self.refresh_bindings()` to `on_data_table_row_highlighted` so the Footer re-evaluates bindings on every row cursor change.
  - Removed the in-action row guards and corrective notify warnings from `action_sync_data`/`action_pull`/`action_push` — Textual prevents the action from firing when `check_action` returns `None`, so those defensive blocks are unreachable.
  - **Post-Review (Change Request 1):** Added `_set_busy(busy)` helper that toggles `DataTable.loading` (Textual's standard widget-level loading overlay using the built-in `LoadingIndicator`). The three actions set busy True before launching their worker; each of `_sync_data_worker`, `_main_pull_worker`, `_main_push_worker` wraps its body in `try`/`finally` and queues `self._set_busy(False)` via `call_from_thread` on every exit path.
- **Deviations from plan:** None on the original three changes. Change Request 1 (progress indicator) was not in the original plan and was added as a follow-up after user review.
- **Issues encountered:** None. Sanity import + `getattr` checks confirm `check_action` and `_set_busy` are bound on the class. Manual TUI verification deferred to the user (per the plan — no automated footer/loading snapshot harness in this project).
- **Key decisions:**
  - Used `Widget.loading` reactive (canonical Textual mechanism) rather than wiring a custom `LoadingIndicator` widget into the layout. Single attribute, zero layout changes, matches "use textual standard widgets".
  - Scoped the loading overlay to the `#branches` DataTable (where the user's focus is and where the operation's effect lands) rather than the whole screen. Less visually disruptive.
  - Did NOT plumb the indicator through `_refresh_worker` (background, runs every 30s automatically) or `_run_interactive_sync_shared` (user is in conflict-resolution screen — busy indicator would be misleading). Limited to user-triggered slow operations.
  - `try/finally` in the workers is safer than `_set_busy(False)` calls before each early-return — guarantees cleanup on all paths including unexpected exceptions.
- **Upstream defects identified:** None.
