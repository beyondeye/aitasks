---
Task: t789_missing_shortcuts_from_tui_switcher_footer.md
Base branch: main
plan_verified: []
---

# Plan: Fix TUI switcher footer visibility (t789)

## Context

After **t713_4** ("Wire syncer TUI into switcher and monitors"), the TUI
switcher overlay (`.aitask-scripts/lib/tui_switcher.py`) gained a desync
status line (`#switcher_desync`) above the TUI list. The dialog layout was
not updated to reserve space for the existing footer hint
(`#switcher_hint`), so in small panes the dialog overflows the viewport and
the hint — which lists every keyboard shortcut — gets clipped from the
bottom. The clipping is worst in `minimonitor` (host pane often <20 rows)
and `monitor` when many tmux windows fill the list.

Current dialog layout (file: `.aitask-scripts/lib/tui_switcher.py`,
`TuiSwitcherOverlay.DEFAULT_CSS` at L282–L322):

```
border (2) + padding-y (2) + title (2) + session_row (1 even when empty) +
desync (2) + list (auto, max 22) + hint (~3 wrapped lines)
```

Sum is 30–35 rows. Dialog cap is `max-height: 30`, so when the parent pane
is e.g. 18 rows, the dialog renders taller than the pane and the bottom
(the hint footer) is clipped. The list itself is fine; it's the hint that
disappears.

## Approach

Two coordinated changes, both inside
`.aitask-scripts/lib/tui_switcher.py`:

1. **CSS — pin the hint to the bottom, let the list flex.** Use Textual's
   `dock: bottom` on `#switcher_hint` and `1fr` on `#switcher_list`. Cap the
   dialog at the viewport so it can never overflow.
2. **Compose — hide the session row in single-session mode.** Today the
   empty `Label` for `#switcher_session_row` still consumes its
   `padding: 0 0 1 0` (one row) even when its text is `""`. Toggle
   `display` so the row contributes zero rows when there is no multi-session
   context.

The desync line stays as-is (always 1 useful row of content) — it does not
need a display toggle.

## Files to modify

- `.aitask-scripts/lib/tui_switcher.py` — CSS + `_render_session_row` tweak.
- `tests/test_tui_switcher_footer_fit.sh` (new) — regression test verifying
  the CSS contract and the single-session hide.

## Detailed changes

### 1. `TuiSwitcherOverlay.DEFAULT_CSS` (L282–L322)

- `#switcher_dialog`: change `height: auto; max-height: 30;` →
  `height: 100%; max-height: 30;`
  - `height: 100%` makes the dialog fill the viewport (up to 30 rows), which
    gives `1fr` a definite parent height to compute against.
  - The dialog stays centered via the parent `align: center middle`; on a
    >30-row pane it still renders as a 30-row centered modal. On a 18-row
    pane it now fills the whole pane instead of overflowing it.
- `#switcher_hint`: add `dock: bottom;` and keep
  `padding: 1 0 0 0; text-align: center; color: $text-muted; width: 100%;`.
  Docking removes the hint from the normal flow and pins it to the bottom of
  the dialog — it is always visible regardless of list length.
- `#switcher_list`: change `height: auto; max-height: 22;` →
  `height: 1fr; min-height: 3;`. The list now claims all space between the
  header rows and the docked hint, scrolling internally when items overflow.
  The `min-height: 3` guards against the list collapsing to zero when the
  hint+header rows already exceed a tiny pane.

### 2. `_render_session_row` (L456–L472)

Add a single line after the `not self._multi_mode` early return that hides
the row so its padding does not consume a row:

```python
def _render_session_row(self) -> None:
    row = self.query_one("#switcher_session_row", Label)
    if not self._multi_mode:
        row.update("")
        row.display = False
        return
    row.display = True
    ...
```

Result: in single-session mode the session row contributes 0 rows; in
multi-session mode it shows normally.

### 3. Regression test — `tests/test_tui_switcher_footer_fit.sh`

Follow the pattern of `tests/test_tui_switcher_multi_session.sh`
(`AITASK_PYTHON` + `PYTHONPATH=$LIB_DIR`, `require_no_tmux`,
`assert_eq`/`assert_contains` helpers from inline definitions).

Coverage:

- **CSS contract** — import `TuiSwitcherOverlay`, read `DEFAULT_CSS`, assert:
  - `dock: bottom` appears inside `#switcher_hint`
  - `height: 1fr` appears inside `#switcher_list`
  - `height: 100%` and `max-height: 30` appear inside `#switcher_dialog`
- **Single-session row hide** — instantiate `TuiSwitcherOverlay` with
  `discover_aitasks_sessions` patched to return one session, drive
  `_init_multi_state` + `_render_session_row` with a mocked `query_one`,
  assert `row.display` is set to `False` and `row.update("")` is called.
- **Multi-session row show** — same fixture with two sessions, assert
  `row.display` is set to `True` and `row.update` receives a non-empty
  string containing both session names.

The test stays Tier 1 (no Textual runtime, no tmux) so it runs everywhere
the existing switcher tests run.

## Verification

End-to-end:

1. `bash tests/test_tui_switcher_footer_fit.sh` — passes (new regression).
2. `bash tests/test_tui_switcher_multi_session.sh` — still passes
   (no behavior change to multi-session logic).
3. Manual: `ait minimonitor` in a small tmux pane (~18 rows), press `j`.
   Confirm the full two-line hint footer is visible at the bottom, the
   desync line is visible at the top, and the TUI list scrolls internally
   when many tmux windows are present.
4. Manual: `ait board` (full-screen pane), press `j`. Confirm the dialog
   still renders as a centered modal (≤30 rows) with the hint at the
   bottom — no regression for the common case.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9: commit on `main`, archive via
`./.aitask-scripts/aitask_archive.sh 789`, push.

## Out of scope

- Compacting the hint text itself (one-line vs two-line shortcuts). The
  docking change makes the current two-line hint fit; further compaction
  can be a separate task if requested.
- Other TUIs' footer layouts (board, monitor, etc.) — this task is scoped
  to the switcher overlay only.
