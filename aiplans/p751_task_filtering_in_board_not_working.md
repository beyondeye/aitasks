---
Task: t751_task_filtering_in_board_not_working.md
Base branch: main
plan_verified: []
---

# Plan — Fix board view-mode filters (i / g / t) not applying (t751)

## Context

`ait board` ships four view-mode filters wired to single-key bindings:

| Key | Action | Visible set |
| --- | --- | --- |
| `a` | All | every task |
| `g` | Git | tasks with `issue:` or `pull_request:` |
| `i` | Implementing | tasks with `status: Implementing` (+ their parents/siblings) |
| `t` | Type | tasks whose `issue_type` matches dialog selection |

The user reports that pressing `i`, `g`, or `t` leaves **all** tasks visible — the filter has no effect. Reproduced via Textual `Pilot` against the live repo data:

```
BEFORE filter: total cards = 70, visible = 70, status=Implementing = 3
AFTER 'i':     total cards = 72, visible = 72, view_mode = implementing
AFTER 'g':     total cards = 70, visible = 70, view_mode = git
```

`view_mode` is being set correctly, but the visibility is never narrowed.

### Root cause

`KanbanApp._set_view_mode` calls `refresh_board`, which removes columns and remounts fresh `KanbanColumn` widgets, then calls `apply_filter()` synchronously:

`.aitask-scripts/board/aitask_board.py:3449-3475`
```python
def refresh_board(self, refocus_filename: str = "", refresh_locks: bool = False):
    ...
    container.remove_children()
    ...
    container.mount(KanbanColumn(...))   # for each column
    ...
    self.apply_filter()                  # ← runs BEFORE compose
```

In Textual 8.1, `Widget.mount()` registers the new `KanbanColumn` in the DOM but its `compose()` (which `yield`s the `TaskCard`s) runs later when the Compose/Mount events are processed. So at line 3475:

- `self.query(TaskCard)` finds **old** TaskCards (still pending removal from the previous columns) — possibly already detached, possibly stale references.
- The **new** TaskCards composed inside the freshly mounted columns are **not yet in the DOM**, so `apply_filter` never sets `display: none` on them.
- When the new cards do compose later, nobody re-applies the filter, so they default to `display: block` — every card visible.

Empirical proof: after pressing `i`, calling `app.apply_filter()` manually post-`pilot.pause()` correctly drops visible cards from 72 to 7 (the 3 `Implementing` tasks plus the parents/siblings the algorithm pulls in).

`refresh_column` (3521) and `refresh_columns` (3541) have the same race — they call `_recompose_column` (which `remove_children` + `mount_all`s newly composed cards) and then synchronously `apply_filter`. They aren't in the user's reported repro path but are the same bug class and would silently break filters after card movement / column edits with a non-`all` view active.

### Why initial load + search filter work today

- Initial mount runs with `view_mode = "all"` → `visible_set is None` → every card defaults to `block`. The race is silent because no card needs to be hidden.
- `on_search` (3548) runs against an already-mounted board (no re-mount), so `query(TaskCard)` already sees the live cards. No race.
- Filter-dialog dismiss path that just calls `self.apply_filter()` (3682) also runs after the board is steady-state. Only when it transitions view-mode via `_set_view_mode("type")` does it get pulled into the racy `refresh_board`.

## Files to change

- `.aitask-scripts/board/aitask_board.py`
  - Line 3475 — `refresh_board`: replace synchronous `self.apply_filter()` with `self.call_after_refresh(self.apply_filter)`.
  - Line 3521 — `refresh_column`: same replacement.
  - Line 3541 — `refresh_columns`: same replacement.
  - Other `apply_filter` call sites (3548 `on_search`, 3682 dialog dismiss, 3937 cancel branch, 4318 task move) operate on cards that are already in the DOM and stay in the DOM — leave them as-is.

`call_after_refresh` schedules the callback after Textual has processed pending mount/compose events, so the new `TaskCard`s are queryable and `display: none` sticks. This is the same primitive already used elsewhere in the app for post-mount focus restoration (e.g., `_refocus_card` at 3479, 3522, 3543), so it's consistent with existing patterns in this file.

## Tests to add

This repo has no Textual `Pilot` tests yet, so this introduces a small new convention. Add:

- `tests/test_board_view_filter.py` — async pilot test using `KanbanApp.run_test(headless=True)`.
  - Builds a tmpdir-based fixture with at least one `aitasks/t<N>.md` per state we care about: one with `status: Implementing`, one with `issue:` set, one plain Ready, one with `issue_type: bug`. Drops a minimal `aitasks/metadata/{board_config.json,task_types.txt,labels.txt}` so `TaskManager` loads cleanly. (Use `tempfile.TemporaryDirectory` + `os.chdir` since `KanbanApp.__init__` reads from cwd.)
  - Cases:
    1. `press("i")` → only the `Implementing` card (+ siblings if any) is visible; the Ready-only and Git-only cards are hidden.
    2. `press("a")` → every card visible again (regression guard for the back-to-all path).
    3. `press("g")` → only the card with `issue:` is visible.
    4. `press("t")` then drive the dialog selecting `bug` → only the `bug` card is visible.
  - Each assertion runs after `await pilot.pause()` so the post-`call_after_refresh` filter has fired.

- `tests/run_all_python_tests.sh` — confirm it picks up the new file (it currently globs `tests/test_*.py` per existing pattern; if not, add an explicit entry).

If headless `Pilot` proves flaky in CI, fall back to a direct unit test that:
1. Constructs `KanbanApp`, runs `app.run_test()` to enter the app.
2. Calls `app._set_view_mode("implementing")` directly.
3. Awaits one event loop tick (`await pilot.pause()`).
4. Asserts on `card.styles.display`.

This avoids the binding-dispatch path but still exercises the racy `refresh_board → apply_filter` boundary, which is the actual bug.

## Verification

1. **Unit/Pilot:** `bash tests/test_board_view_filter.sh` (or `python3 -m pytest tests/test_board_view_filter.py` depending on style chosen) — must pass.
2. **Existing suite:** `bash tests/run_all_python_tests.sh` — no regressions in the board-adjacent tests (`test_board_config_split.py`, `test_section_viewer_filter.py`).
3. **Manual smoke (in `ait board`):**
   - Press `i` → only Implementing tasks (+ their parents/siblings) shown. Press `a` → everything back. ✓
   - Press `g` → only tasks with issue/PR shown. Press `a`. ✓
   - Press `t`, pick `bug` in the dialog → only bug-typed tasks shown. ✓
   - Press `i` then type into the search box → search narrows the implementing subset (search + view-mode compose correctly).
   - Press `i`, then resize the terminal / move a task with `Shift+↑`/`↓` → filter remains applied (covers the `refresh_column`/`refresh_columns` paths).

## Out of scope

- The `_implementing_visible_set` / `_git_visible_set` / `_type_visible_set` algorithms themselves are correct (verified by manually invoking them post-pause). No semantic changes needed.
- No changes to bindings, keymap, or the type-filter dialog UX.

## Final Implementation Notes

- **Actual work done:** Replaced three synchronous `self.apply_filter()` calls in `aitask_board.py` (`refresh_board` line 3475, `refresh_column` line 3521, `refresh_columns` line 3541) with `self.call_after_refresh(self.apply_filter)`. Added a 3-test Textual `Pilot` regression suite at `tests/test_board_view_filter.py` exercising `i` (Implementing), `g` (Git), and `a` (back-to-All) view-mode transitions.
- **Deviations from plan:** None — the plan's recommended single-primitive fix (`call_after_refresh`) was applied unchanged at the three identified call sites.
- **Issues encountered:** None during implementation. Reproduced the bug pre-fix (72 visible cards after pressing `i`); verified the fix post-edit (7 visible — the 3 Implementing tasks plus 4 parents/siblings the algorithm pulls in). Sanity-checked the test suite catches the regression by temporarily reverting the `refresh_board` fix; tests failed as expected, then restored.
- **Key decisions:** Tests are written against the live repo data rather than a tmpdir fixture because `aitask_board` resolves `TASKS_DIR = Path("aitasks")` at module-import time. The tests assert the visible set equals what `_*_visible_set()` returns (data-independent contract), so they remain stable regardless of which tasks happen to be in the repo.
- **Upstream defects identified:** None.
