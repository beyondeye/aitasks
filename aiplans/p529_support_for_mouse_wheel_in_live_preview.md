---
Task: t529_support_for_mouse_wheel_in_live_preview.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: t529 — Mouse wheel / scrollback / XL zoom in monitor preview panel

## Context

`ait monitor` is a Textual TUI that shows tmux panes and previews the focused
pane's output in a bottom "Content Preview" panel. Currently:

- The preview only renders the **last `max_h - 1` lines** of captured content
  (`monitor_app.py:632-633`), so even though the enclosing
  `ScrollableContainer` is scrollable in principle, the widget has no overflow
  to scroll through — scrollback is effectively unavailable.
- `capture_lines` defaults to **30** (`tmux_monitor.py:375`), leaving only a
  handful of lines of history even if we did show everything.
- `z` cycles three preset sizes (S/M/L) but there is no preset that fills
  almost the entire screen.
- `action_cycle_preview_size` (`monitor_app.py:846`) changes heights but does
  **not** refresh the preview content — the newly revealed area stays stale
  until the next 3-second refresh cycle (or 0.3s fast cycle if in PREVIEW
  zone).
- There is no control to hide the vertical scrollbar.

The user wants to be able to scroll back into previously-visible output, both
via a visible scrollbar and the mouse wheel, to add an "almost full screen"
preview preset that redraws immediately on activation, and to be able to
hide/show the scrollbar.

## Goals

1. Show the full captured scrollback in the preview (not just the last
   `max_h - 1` lines), so the `ScrollableContainer` has real overflow to
   scroll through.
2. Support mouse wheel scrolling inside the preview (relies on #1 — Textual's
   `ScrollableContainer` already handles `MouseScrollUp/Down` natively).
3. Show a vertical scrollbar by default, with a new `b` keybinding to
   toggle it on/off.
4. Add an **XL** preview preset that fills the viewport minus a small
   reserved area for the rest of the UI (header, session bar, pane list,
   footer).
5. Immediately refresh the preview content when the preview size changes so
   the freshly-revealed area is populated without waiting for the next 3s
   refresh cycle.
6. Bump the default `capture_lines` from 30 to **200** so there is
   meaningful scrollback while keeping the 0.3s fast-refresh cost
   modest. (Deferred-read-on-scroll is an attractive optimization but
   is explicitly out of scope — see "Out of Scope".)

## Files to Modify

- `.aitask-scripts/monitor/monitor_app.py` — preview sizing, rendering,
  scrollbar toggle, XL preset, immediate refresh, auto-tail behavior.
- `.aitask-scripts/monitor/tmux_monitor.py` — raise the `capture_lines`
  default so scrollback is meaningful.

## Design

### 1. Preview size presets (monitor_app.py)

Replace the three-entry `PREVIEW_SIZES` with a four-entry list where the
new XL entry uses a sentinel instead of fixed heights:

```python
PREVIEW_FULLSCREEN_RESERVE = 10  # lines reserved for other UI in XL mode

# (section_max_height, preview_max_height, label)
# "fullscreen" means: compute from self.size.height at apply time.
PREVIEW_SIZES = [
    (12, 10, "S"),
    (24, 22, "M"),
    (40, 38, "L"),
    ("fullscreen", "fullscreen", "XL"),
]
PREVIEW_DEFAULT_SIZE = 1  # Medium
```

### 2. Centralize size application (monitor_app.py)

Split the old `action_cycle_preview_size` into (a) the action that advances
the index and (b) a helper `_apply_preview_size()` that resolves XL to a
concrete height, applies styles, and triggers an immediate preview refresh.

### 3. Recompute XL on terminal resize (monitor_app.py)

When in XL mode the resolved height depends on the terminal size, so
re-apply whenever Textual fires `on_resize`.

### 4. Show the full scrollback (monitor_app.py)

In `_update_content_preview()`, stop slicing to `max_h - 1` lines. Render
the full captured content, which lets the `ScrollableContainer` naturally
scroll when there is overflow. Implement a tail-follow behavior so live
updates stay pinned to the bottom unless the user has scrolled up.

Check `was_at_bottom` (via `scroll.scroll_y >= scroll.max_scroll_y - 1`)
before calling `preview.update(content)`; if true, call
`self.call_after_refresh(lambda: scroll.scroll_end(animate=False))` so the
new content is tailed.

### 5. Scrollbar toggle (monitor_app.py)

Add a new `b` binding and `action_toggle_scrollbar()` that flips
`scroll.styles.scrollbar_size_vertical` between 1 (shown) and 0 (hidden).
Setting the size to 0 hides the bar without disabling scrolling (mouse
wheel and keyboard scrolling still work). New state:
`self._show_scrollbar: bool = True` in `__init__`.

Because the preview is inside the PREVIEW zone, `check_action()` already
hides non-`switch_zone` bindings while that zone is focused — so `b`, like
the existing `z`, is only actionable from the PANE_LIST zone. That matches
the existing UX convention and needs no change.

### 6. Larger default scrollback (tmux_monitor.py)

Bump the default from 30 to **200** in both places:

- `class TmuxMonitor.__init__(..., capture_lines: int = 30, ...)` — change
  default to 200.
- `load_monitor_config()` defaults dict `"capture_lines": 30` — change to 200.

Users who explicitly set `tmux.monitor.capture_lines` in
`aitasks/metadata/project_config.yaml` continue to get their chosen value
unchanged.

Rationale for 200 (not higher):

- 200 lines is ~8–10× the visible area in L mode — enough to cover most
  "what was that output a few seconds ago?" use cases.
- The 0.3s fast-refresh path re-parses the entire captured buffer through
  `_ansi_to_rich_text`. 200 lines keeps that cost at ~7× the current
  30-line baseline (rather than ~16× at 500), which is comfortably under
  a millisecond per tick on typical hardware.
- Power users can still raise it in `project_config.yaml`.

### 7. Mouse wheel scrolling

No explicit handler needed. Textual's `ScrollableContainer`
(`#preview-scroll`) already processes `MouseScrollUp` / `MouseScrollDown`
events natively. The current behavior looked broken only because the
content never overflowed (see §4). With the full scrollback rendered, the
mouse wheel will scroll the container naturally. Mouse events are separate
from the key-forwarding path in `on_key`, so forwarding keys to tmux in the
PREVIEW zone does **not** interfere with wheel scrolling.

## Out of Scope

- **Deferred-read-on-scroll optimization** — every 0.3s fast refresh still
  re-captures and re-parses the entire configured scrollback window. A
  future optimization could capture only a small tail when the user is
  tail-following and fetch a larger window from tmux only when they scroll
  up. The 200-line default makes the simple "capture all, render all"
  approach cheap enough that this optimization is not needed for this
  task; it can be added later as an internal change without any UI impact.
- No persistent "scrollbar shown" preference — the toggle is a per-session
  runtime setting.
- Horizontal scrollbar behavior is not changed.
- `minimonitor_app.py` is deliberately not touched — the task is about
  `ait monitor`, and the mini variant has a different layout.

## Implementation Steps

1. **monitor_app.py — constants**
   - Add `PREVIEW_FULLSCREEN_RESERVE = 10`.
   - Add `("fullscreen", "fullscreen", "XL")` entry to `PREVIEW_SIZES`.

2. **monitor_app.py — MonitorApp state**
   - Add `self._show_scrollbar = True` in `__init__`.

3. **monitor_app.py — BINDINGS**
   - Add `Binding("b", "toggle_scrollbar", "Scrollbar")`.

4. **monitor_app.py — size application**
   - Replace body of `action_cycle_preview_size` to delegate to new
     `_apply_preview_size()`.
   - Add `_apply_preview_size()` helper (handles XL sentinel, applies
     styles, notifies, and calls `_update_content_preview()`).
   - Add `on_resize()` handler that re-applies sizing only while XL is
     active.

5. **monitor_app.py — scrollbar toggle**
   - Add `action_toggle_scrollbar()` as described in §5.

6. **monitor_app.py — preview rendering**
   - Update `_update_content_preview()` to render all captured lines,
     preserve scroll position, and tail-follow when at the bottom.
   - Remove the `max_h - 1` slicing block.

7. **tmux_monitor.py — default scrollback**
   - Change `capture_lines: int = 30` parameter default to 200.
   - Change `"capture_lines": 30` in the `load_monitor_config` defaults
     dict to 200.

8. **Manual verification** (see Verification section).

## Verification

All verification requires a running tmux session with at least one visible
pane that produces output.

1. **Launch monitor**: from inside tmux, run `ait monitor`. Confirm it
   shows the pane list and preview panel. Focus a pane via `Tab` + arrow
   keys (or click).

2. **Scrollback visible**: focus an agent pane that has produced >40 lines
   of output. Confirm the preview shows the tail of the output and that
   a vertical scrollbar is visible on the right edge of the preview.

3. **Mouse wheel scroll**: hover the mouse over the preview and scroll
   up — the view should reveal older captured output. Scrolling back to
   the bottom should re-engage tail-follow, and new output lines should
   appear at the bottom without manual intervention.

4. **Scrollbar toggle**: in the PANE_LIST zone press `b`; the scrollbar
   should disappear but mouse-wheel scrolling should still function. Press
   `b` again to restore the bar.

5. **Zoom cycle including XL**: press `z` repeatedly and observe the
   notification cycling through `S → M → L → XL → S …`. In XL mode the
   preview should occupy nearly the whole window.

6. **Immediate refresh on zoom change**: press `z` to enlarge the preview;
   the freshly-exposed lines must be populated instantly (not blank until
   the next 3-second refresh cycle).

7. **Terminal resize in XL**: in XL mode, resize the terminal window. The
   preview should re-fit to the new height (minus the 10-line reserve).

8. **No regressions**: `r`, `a`, `k`, `n`, `i`, `s`, `q`, `j` bindings
   unchanged; PREVIEW zone still forwards keystrokes to tmux; `ait monitor`
   launches cleanly.

9. **Syntax check**: `python -m py_compile
   .aitask-scripts/monitor/monitor_app.py
   .aitask-scripts/monitor/tmux_monitor.py`.

## Post-Implementation

Follow the task-workflow SKILL.md Step 8 (user review) and Step 9
(archival) for commit, plan archive, and task finalization.

## Post-Review Changes

### Change Request 1 (2026-04-13 11:10)

- **Requested by user:** After first run, scrollbar show/hide action
  reported state but no scrollbar was visible and mouse wheel did
  nothing.
- **Root cause:** `PreviewPanel` CSS had `max-height: 22`, and
  `_apply_preview_size()` set `preview.styles.max_height` per preset.
  That capped the inner Static widget at the same height as the
  enclosing `ScrollableContainer`, so the Static could never overflow
  the container — leaving no scrollable range, no scrollbar, and no
  mouse wheel effect.
- **Changes made:**
  - Removed `max-height: 22` from the `PreviewPanel` CSS rule.
  - Added `scrollbar-gutter: stable` to `#preview-scroll` so toggling
    the scrollbar does not reflow the preview area.
  - `_apply_preview_size()` now only sets `max_height` on
    `#content-section` and `#preview-scroll`, leaving
    `#content-preview` (the Static) free to grow to content height.
- **Files affected:** `.aitask-scripts/monitor/monitor_app.py`
- **Answer to "should scroll only work when preview is live?":**
  No. Mouse wheel is a pointer event — it works whenever the cursor is
  over the preview, regardless of zone. The PREVIEW-zone key forwarding
  in `on_key` only intercepts keyboard events; `MouseScrollUp/Down`
  events flow through the normal propagation path and reach the
  `ScrollableContainer` natively.

### Change Request 2 (2026-04-13 11:15)

- **Requested by user:** Capture buffer looked much smaller than the
  new 200-line default.
- **Root cause:** `aitasks/metadata/project_config.yaml` explicitly set
  `tmux.monitor.capture_lines: 30`, a vestigial value from when 30 was
  the code default. An explicit project config value wins over the
  code default in `load_monitor_config()`.
- **Changes made:** Bumped
  `tmux.monitor.capture_lines` in `project_config.yaml` from 30 to 200
  to match the new code default.
- **Files affected:** `aitasks/metadata/project_config.yaml`

## Final Implementation Notes

- **Actual work done:**
  - `.aitask-scripts/monitor/monitor_app.py`: added
    `PREVIEW_FULLSCREEN_RESERVE` constant and XL preset entry; added
    `_show_scrollbar` state; added `b` binding for
    `action_toggle_scrollbar`; split `action_cycle_preview_size` into
    the action plus a new `_apply_preview_size()` helper that resolves
    the XL sentinel against `self.size.height`, applies section and
    scroll container heights (not the inner Static), and immediately
    calls `_update_content_preview()` so the freshly-revealed area is
    populated without waiting for the next 3s refresh cycle; added
    `on_resize()` that re-applies sizing only while XL is active;
    added `action_toggle_scrollbar()` that flips
    `scroll.styles.scrollbar_size_vertical` between 0 and 1; rewrote
    `_update_content_preview()` to render the full captured scrollback
    (no more `max_h - 1` slicing) with tail-follow behavior
    (`was_at_bottom` check against `scroll.scroll_y`/`max_scroll_y`
    before update, followed by `call_after_refresh(lambda:
    scroll.scroll_end(animate=False))` when at the tail); removed the
    CSS `max-height: 22` from `PreviewPanel` and added
    `scrollbar-gutter: stable` to `#preview-scroll`; bumped stale
    `capture_lines` defaults from 30 to 200 in `MonitorApp.__init__`
    and `main()` fallback.
  - `.aitask-scripts/monitor/tmux_monitor.py`: bumped `capture_lines`
    defaults from 30 to 200 in both `TmuxMonitor.__init__` and
    `load_monitor_config()`.
  - `aitasks/metadata/project_config.yaml`: bumped
    `tmux.monitor.capture_lines` from 30 to 200 (was overriding the
    new default, discovered during testing — see Change Request 2).
- **Deviations from plan:** None at the design level — the delivered
  behavior matches every goal in the original plan. Two post-review
  changes were needed once the feature was running in a real tmux
  session: the CSS `max-height` fix (which the original plan missed)
  and the `project_config.yaml` bump (not originally in scope because
  we hadn't inspected the committed project config before planning).
- **Issues encountered:**
  1. The `ScrollableContainer` was not actually scrollable because
     `PreviewPanel`'s CSS `max-height: 22` capped the Static widget
     at the same height as its container, leaving no overflow. Fixed
     by removing the CSS cap and only capping the container heights.
     Takeaway for future Textual scrolling work: always make sure the
     **inner** widget is free-growing (`height: auto`, no max-height)
     and only cap the enclosing scrollable container — otherwise there
     is no scrollable range.
  2. The new 200-line default in code was shadowed by an explicit
     `capture_lines: 30` in `project_config.yaml`. Config files with
     explicit values silently override code defaults; when bumping a
     default, also check committed config files for vestigial
     overrides.
- **Key decisions:**
  - Capped `capture_lines` at **200**, not 500. 200 lines is enough
    for typical "what did that agent say a minute ago?" scrollback
    while keeping the 0.3s fast-refresh re-parse cost modest (~7×
    the previous 30-line baseline, still sub-millisecond on typical
    hardware). Deferred-read-on-scroll (capture tail only on every
    tick, fetch full history on-demand when scrolling up) was
    considered and rejected for this task — it can be added later as
    an internal optimization without any UI impact. See "Out of
    Scope".
  - The XL preset uses a `"fullscreen"` sentinel resolved dynamically
    in `_apply_preview_size()` rather than a fixed height, so it
    adapts to the current terminal size. `on_resize()` re-applies it
    when the terminal is resized while XL is active.
  - Scrollbar toggle is per-session runtime state (not persisted).
    Adding it to `project_config.yaml` would be trivial but the task
    description didn't ask for persistence.
  - Tail-follow is implemented by checking `was_at_bottom` before the
    content update, then calling `scroll.scroll_end(animate=False)`
    from `call_after_refresh` so `max_scroll_y` reflects the new
    content height by the time we scroll.
