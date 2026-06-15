---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [aitask_monitormini]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-15 10:36
updated_at: 2026-06-15 12:03
---

Trim the kill-agent confirmation dialog (`KillConfirmDialog`, defined in
`.aitask-scripts/monitor/monitor_shared.py:160`) when it is opened from
**minimonitor** — and fix a button-overflow rendering bug that affects the
dialog in narrow panes.

`KillConfirmDialog` is shared by two callers:
- Full monitor — `monitor_app.py:1558` (kills a *user-selected* pane from a list)
- Minimonitor — `minimonitor_app.py:793` via `action_kill_own_agent`, which
  always targets the single *followed companion agent* (`_find_own_agent_snapshot`)

## 1. Hide the terminal "Window Content Preview" in minimonitor

In the full monitor the preview (last 15 lines of pane content, rendered at
`monitor_shared.py:218-226`) helps disambiguate *which* pane is about to be
killed. In minimonitor the kill is always scoped to the one followed agent, so
the preview is redundant and just adds vertical bulk to a small dialog.

- Add a `show_preview: bool = True` constructor parameter to `KillConfirmDialog`.
- When `False`, skip yielding the `#kill-preview-label` and `#kill-preview`
  Statics in `compose()`.
- Minimonitor's call site (`minimonitor_app.py:793`) passes `show_preview=False`.
- Full monitor call site (`monitor_app.py:1558`) is unchanged (keeps the preview).

## 2. Keep the buttons inside the dialog width

The dialog (`#kill-dialog`) is `width: 80%`; the two buttons (`Kill` / `Cancel`)
sit in a `layout: horizontal` container (`#kill-buttons`) with `margin: 0 1`
each (`monitor_shared.py:181-182`, `228-230`). In a narrow minimonitor split
pane, 80% width is small enough that the buttons get pushed outside the visible
dialog area.

- Adjust the shared button-row CSS so the buttons always fit and stay centered
  inside the dialog (e.g. tighten margins, center/shrink the button row, and/or
  set a sensible `min-width` on the dialog). The fix lives in the shared dialog
  CSS and must remain harmless to the full monitor.

## Notes / scope
- Both changes live in `monitor_shared.py`, plus the one minimonitor call-site
  edit. Full monitor behaviour stays the same.
- The dialog is a Textual TUI — see `aidocs/framework/tui_conventions.md`.
- Verify the button fit by opening the dialog in a deliberately narrow
  minimonitor split pane.
