---
Task: t552_refresh_for_codebrowser_history.md
Worktree: (none — working on current branch per profile)
Branch: main
Base branch: main
---

# Plan for t552 — Refresh command for codebrowser history screen

## Context

In the `ait codebrowser` TUI, the **history** screen (`h` key from the browser)
lists completed/implemented aitasks scanned from `aitasks/archived/`. Today the
list is populated **once** — on first mount of the screen — and then cached on
the app instance (`self.app._history_index`). If a task is completed (archived)
while the codebrowser is open, the history list goes stale and the only way to
see the new task is to quit and relaunch the TUI.

The task asks for a manual **refresh** command (`r` shortcut) on the history
screen that re-scans `aitasks/archived/` and updates the list in place,
preserving the user's current view state (scroll position, selected task,
label filter).

## Files to modify

- `.aitask-scripts/codebrowser/history_screen.py` — only file changed.

Everything else (data loading via `load_task_index_progressive`, UI update via
`HistoryLeftPane.set_data` / `apply_label_filter`) already exists and is reused.

## Current state — key references

- `HistoryScreen` class: `.aitask-scripts/codebrowser/history_screen.py:25`
- Current `BINDINGS` list: lines 28–46. **Line 39 already has**
  `Binding("r", "noop", show=False)` — this exists specifically to suppress
  the inherited `CodeBrowserApp` binding `Binding("r", "refresh_explain", ...)`
  (see `.aitask-scripts/codebrowser/codebrowser_app.py:157`). We replace this
  line, we do **not** add a new binding.
- Existing progressive loader (worker thread): `_load_data` at
  `history_screen.py:135–139`. It iterates `load_task_index_progressive` and
  pushes chunks to `_on_index_chunk` via `app.call_from_thread`.
- First-chunk handler `_on_index_chunk` at `history_screen.py:141–179` —
  **mounts** UI on first chunk (when `self._task_index is None`), or calls
  `left.update_index(index)` / sets `detail._task_index = index` on subsequent
  chunks.
- State-save helper `_save_state_to_app` at `history_screen.py:181–199` — reads
  `detail._nav_stack[-1]`, `detail._showing_plan`, `task_list.scroll_y`,
  `task_list._active_labels`. Same pattern reused here.
- Full rebuild path used on initial mount (cached case): `_populate_and_restore`
  at `history_screen.py:96–124` — calls `left.set_data(...)`,
  `detail.set_context(...)`, `left.apply_label_filter(...)`,
  `detail.show_task(...)`, and schedules `_restore_scroll` via `set_timer`.
- Full rebuild on the left pane: `HistoryLeftPane.set_data` at
  `history_list.py:382–388` — calls `HistoryTaskList.set_index` which already
  clears and re-populates all `HistoryTaskItem` rows (`history_list.py:214–222`)
  and re-seeds `RecentlyOpenedList` via `set_task_index`.
- Detail pane context reset: `HistoryDetailPane.set_context` (already used by
  the cached-mount path) — safe to call again.
- Codebrowser app refresh-in-progress feedback pattern: `action_refresh_explain`
  → `_refresh_explain_data` at `codebrowser_app.py:676–705` uses `self.notify`
  and an info-bar status message. We use `self.notify` only (history screen
  has no info bar).

## Approach

1. **Rewire the `r` binding** on `HistoryScreen` from `action_noop` to a new
   `action_refresh_history`, keeping it visible in the footer (remove
   `show=False`) so users discover it.

2. **Add a dedicated reload worker** `_reload_data` that mirrors `_load_data`
   but dispatches to `_on_reload_chunk` instead of `_on_index_chunk`. Using a
   separate handler keeps the initial-mount code path (`_on_index_chunk`, which
   mounts new UI when `self._task_index is None`) untouched, avoiding a
   double-mount race.

3. **Reload handler** `_on_reload_chunk` — on the **first** chunk it captures
   the current view state, calls `left.set_data(index)` which fully clears and
   rebuilds the task list and recently-opened list, then restores the view
   state (label filter, selected task, plan/task toggle, scroll). On
   **subsequent** chunks it falls back to the same progressive update used by
   the initial loader (`left.update_index(index)` + `detail._task_index`).

4. **Modal loading overlay** — pushing a `HistoryRefreshModal` (a Textual
   `ModalScreen`) over the history screen while the reload is running. The
   modal has no user-dismissable bindings and is displayed for **at least one
   second** even on a fast reload. While it is on screen, keypresses don't
   reach `HistoryScreen` so the user physically cannot stack reloads. The
   minimum-duration guarantee also gives the refresh a consistent, noticeable
   visual cue rather than a flicker on fast machines.

5. **Guards** — in addition to the modal, a `self._refreshing` flag and an
   early-out when `self._task_index is None` (i.e. the initial load is still
   running, no UI to overlay) keep the code path safe on the first-load edge
   case.

6. **User feedback** — the modal itself is the primary feedback ("Refreshing
   history…" centered over the screen). A `self.notify("History refreshed")`
   toast fires as the modal dismisses.

The refresh is safe to run mid-browse: the existing `is_mounted` guard in
chunk handlers already protects against late callbacks after the screen is
dismissed.

## Detailed edits

### Edit 0 — new imports

Add at the top of `history_screen.py`:
- `import time` (for `time.monotonic()` used for the min-display-time timer)
- Extend the existing `from textual.containers import Horizontal` to also
  import `Container` (needed by the modal)
- Extend `from textual.widgets import Header, Footer, LoadingIndicator` to
  also import `Static`
- Extend `from textual.screen import Screen` to also import `ModalScreen`

### Edit 0.5 — add `HistoryRefreshModal` class

Add a small `ModalScreen` subclass above `HistoryScreen` (around current
line 24):

```python
class HistoryRefreshModal(ModalScreen):
    """Blocking loading indicator shown while the history refresh runs."""

    DEFAULT_CSS = """
    HistoryRefreshModal {
        align: center middle;
        background: $background 60%;
    }
    HistoryRefreshModal #refresh_box {
        width: 40;
        height: 5;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
        content-align: center middle;
    }
    """

    # Intentionally no BINDINGS — the user cannot dismiss it manually. It is
    # dismissed programmatically by HistoryScreen once reload is done AND the
    # 1-second minimum display time has elapsed.

    def compose(self) -> ComposeResult:
        with Container(id="refresh_box"):
            yield Static("⟳ Refreshing history…")
```

### Detailed edits follow

All edits are in `.aitask-scripts/codebrowser/history_screen.py`.

### Edit 1 — binding change (line 39)

Replace:
```python
        # Override codebrowser app bindings to hide them from footer
        Binding("r", "noop", show=False),
```
with:
```python
        Binding("r", "refresh_history", "Refresh"),
        # Override codebrowser app bindings to hide them from footer
```

(Keep the explanatory comment above the remaining `noop` bindings; `r` is no
longer a noop override so the comment moves one line down and the `r` line
leaves the noop block.)

### Edit 2 — add refresh-state fields in `__init__`

In `HistoryScreen.__init__` (after line 75), add:
```python
        self._refreshing = False
        self._refresh_modal: Optional[HistoryRefreshModal] = None
        self._refresh_start_time = 0.0
```

### Edit 3 — add `action_refresh_history`

Insert directly after `action_noop` (currently at lines 225–227):

```python
    def action_refresh_history(self) -> None:
        """Re-scan aitasks/archived and refresh the history list in place."""
        if self._task_index is None:
            self.notify("History is still loading…", severity="warning", timeout=2)
            return
        if self._refreshing:
            return
        self._refreshing = True
        self._refresh_start_time = time.monotonic()
        self._refresh_modal = HistoryRefreshModal()
        self.app.push_screen(self._refresh_modal)
        self._reload_data()
```

### Edit 4 — add `_reload_data` worker

Insert after `_load_data` (currently ends at line 139):

```python
    @work(thread=True, exclusive=True, group="history_reload")
    def _reload_data(self) -> None:
        platform = detect_platform_info(self._project_root)
        first = True
        for index_chunk in load_task_index_progressive(self._project_root):
            self.app.call_from_thread(self._on_reload_chunk, index_chunk, platform, first)
            first = False
```

`exclusive=True` + a dedicated `group` name ensures a second `r` press while a
reload is already running is a no-op from Textual's side, belt-and-braces with
the `self._refreshing` flag.

### Edit 5 — add `_on_reload_chunk`

Insert after `_on_index_chunk` (currently ends at line 179):

```python
    def _on_reload_chunk(self, index, platform, is_first: bool) -> None:
        # Always refresh the app cache so re-open uses new data
        self.app._history_index = index
        self.app._history_platform = platform
        if not self.is_mounted:
            return
        self._task_index = index
        self._platform_info = platform
        try:
            left = self.query_one("#history_left", HistoryLeftPane)
            detail = self.query_one("#history_detail", HistoryDetailPane)
        except Exception:
            return
        if is_first:
            # Capture current view state before rebuilding
            try:
                task_list = left.query_one("#history_list", HistoryTaskList)
                saved_scroll = int(task_list.scroll_y)
                saved_labels = set(task_list._active_labels)
            except Exception:
                saved_scroll = 0
                saved_labels = set()
            saved_task_id = detail._nav_stack[-1] if detail._nav_stack else None
            saved_showing_plan = detail._showing_plan
            # Full rebuild of both lists and detail context
            left.set_data(index)
            detail.set_context(self._project_root, index, platform)
            if saved_labels:
                left.apply_label_filter(saved_labels)
            if saved_task_id:
                detail.show_task(saved_task_id, is_explicit_browse=False)
                if saved_showing_plan:
                    detail._showing_plan = True
            if saved_scroll > 0:
                self._restore_scroll_y = saved_scroll
                self.set_timer(0.1, self._restore_scroll)
            # Dismiss the modal, honoring the 1s minimum display time.
            elapsed = time.monotonic() - self._refresh_start_time
            remaining = max(0.0, 1.0 - elapsed)
            if remaining > 0.0:
                self.set_timer(remaining, self._dismiss_refresh_modal)
            else:
                self._dismiss_refresh_modal()
        else:
            # Progressive update — same path used by initial loader
            try:
                left.update_index(index)
                detail._task_index = index
            except Exception:
                pass
```

### Edit 6 — add `_dismiss_refresh_modal`

Insert right after `_on_reload_chunk`:

```python
    def _dismiss_refresh_modal(self) -> None:
        """Dismiss the refresh modal and clear refresh state."""
        modal = self._refresh_modal
        self._refresh_modal = None
        self._refreshing = False
        if modal is not None:
            try:
                modal.dismiss()
            except Exception:
                pass
        self.notify("History refreshed", timeout=2)
```

Notes:
- Reuses the existing `_restore_scroll` helper at line 126 by setting
  `self._restore_scroll_y`. That attribute is only read by
  `_populate_and_restore` during `on_mount`, which has already run by the time
  a refresh is possible, so overwriting it is safe.
- `left.set_data(index)` fully clears `HistoryTaskList` rows via
  `HistoryTaskList.set_index` (history_list.py:214) and refreshes the recent
  list via `RecentlyOpenedList.set_task_index` (history_list.py:294), so the
  `“r”` really does pick up new archived tasks and removes any that were
  un-archived.
- The modal blocks all keyboard input directed at `HistoryScreen`, so the
  `r` key cannot retrigger the refresh while it's running. The `_refreshing`
  flag is additionally released inside `_dismiss_refresh_modal`, i.e. **after**
  the 1-second minimum display has elapsed — so even if the user could somehow
  bypass the modal they still can't stack reloads until the first has fully
  released.
- Subsequent chunks trickle in via the progressive path like a normal load,
  after the modal is dismissed. Those progressive updates are non-blocking so
  the user can keep browsing while they arrive.

## Verification

Type check / lint:
```bash
python -m py_compile .aitask-scripts/codebrowser/history_screen.py
```

Manual smoke test (this is a TUI, no automated test covers it):

1. Start the codebrowser pointed at this repo:
   ```bash
   ./ait codebrowser
   ```
2. Press `h` to open the history screen. Confirm the footer shows a new
   `r Refresh` binding alongside the existing `h / v / l / a / q` ones.
3. Scroll part-way down the completed-tasks list and select a task so the
   detail pane shows something.
4. Apply a label filter (`l`) — pick one or two labels.
5. From another terminal, archive a freshly-completed task (or touch an
   archived file's mtime / add a synthetic test task in
   `aitasks/archived/`) so the scan result changes.
6. Back in the TUI press `r`. Expect:
   - A centered modal "⟳ Refreshing history…" appears immediately and stays
     visible for at least one second.
   - Once dismissed, a "History refreshed" toast appears.
   - The newly archived task appears in the list in the right sorted
     position.
   - Scroll position, selected task, and label filter are preserved.
7. Press `r` repeatedly in quick succession. Expect the modal to stay up for
   the single first reload; subsequent key presses while the modal is up are
   swallowed (no stacked modals, no crash).
8. Press `r` while the initial load is still running (easiest to reproduce
   on a cold cache immediately after opening the screen). Expect a
   "History is still loading…" warning toast and no crash.

## Post-implementation (Step 9)

- Commit message: `feature: Add refresh command to codebrowser history screen (t552)`
- Plan commit: `ait: Update plan for t552`
- Archive via `./.aitask-scripts/aitask_archive.sh 552`
- Push via `./ait git push`

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. Added `HistoryRefreshModal(ModalScreen)` above `HistoryScreen`, rewired the `r` binding from the hidden `noop` override to a visible `refresh_history` action, added `_refreshing` / `_refresh_modal` / `_refresh_start_time` instance fields in `__init__`, added `action_refresh_history` (with early-outs for still-loading and in-progress cases), added `_reload_data` worker (`@work(thread=True, exclusive=True, group="history_reload")`), added `_on_reload_chunk` that does a full `left.set_data` rebuild on the first chunk plus the usual `update_index` progressive path on subsequent chunks, and added `_dismiss_refresh_modal` that fires the dismissal + "History refreshed" toast. Modal dismissal honors a `max(0, 1.0 - elapsed)` timer so the indicator is always visible for at least a second. All edits in `.aitask-scripts/codebrowser/history_screen.py` (+109 / -4).
- **Deviations from plan:** None. One incidental tidy-up — the `from textual.widgets import Header, Footer, LoadingIndicator` import was rewritten as `from textual.widgets import Footer, Header, LoadingIndicator, Static` (alphabetized while adding `Static`). Functionally identical.
- **Issues encountered:** None. `python -m py_compile` clean on first attempt; module import test confirmed `HistoryScreen.BINDINGS` now contains `r → refresh_history` and the label shows in the footer.
- **Key decisions:**
  - Kept a separate `_on_reload_chunk` path rather than teaching `_on_index_chunk` a "refresh mode" — the initial handler has a "first chunk mounts UI" branch that we don't want touched, and keeping the two paths separate avoids a double-mount race while the progressive loader is still running.
  - Reused the existing `_restore_scroll_y` / `_restore_scroll()` plumbing from `_populate_and_restore` rather than introducing a new scroll-restore field. `_populate_and_restore` runs exactly once during `on_mount` and a refresh can only happen after that, so overwriting `_restore_scroll_y` later is safe.
  - The modal's 1-second minimum display time uses `time.monotonic()` captured at `action_refresh_history` entry and compared at first-chunk handling; this gives both a consistent visual cue on fast machines and a natural "typeahead guard" (while the modal is up, keypresses can't reach `HistoryScreen`).
- **Verification:** `python -m py_compile .aitask-scripts/codebrowser/history_screen.py` ✔. Module import via a one-shot Python harness confirmed `HistoryRefreshModal` class exists and `HistoryScreen.BINDINGS` lists `r → refresh_history` with description "Refresh" and `show=True`. User confirmed live smoke test in `./ait codebrowser → h` before approving the commit.
