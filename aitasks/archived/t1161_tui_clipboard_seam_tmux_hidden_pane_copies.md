---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [tui, tmux]
implemented_with: claudecode/fable5
created_at: 2026-07-19 11:04
updated_at: 2026-07-19 11:05
completed_at: 2026-07-19 11:05
---

TUI clipboard copies silently fail to reach the system clipboard when the copying pane is not in the tmux client's visible window.

## Problem

All Textual TUI copy actions (minimonitor concern-copy, codebrowser copy-path buttons, agent-command screen copy-command/copy-prompt) used Textual's `App.copy_to_clipboard`, which emits a bare OSC 52 escape. tmux (verified on 3.7b, `set-clipboard on`) forwards a pane's OSC 52 to the outer terminal **only when the pane is in the client's visible window** — from a background window, or a session with no attached terminal client, the text is stored as a tmux paste buffer and the system clipboard is left untouched while the TUI still shows its "copied to clipboard" notification.

User-visible symptom: after minimonitor copies shadow concerns, Omarchy's Super+V universal paste (sendshortcut Shift+Insert) appears broken — there is simply nothing on the system clipboard. Diagnosed end-to-end: the Omarchy binding, ghostty's `shift+insert=paste_from_clipboard`, and the Wayland clipboard were all working; the copy never arrived.

## Fix

- New tmux-gateway method `TmuxClient.set_clipboard(text)` — `tmux load-buffer -w -` (text on stdin), which sets a tmux buffer AND forwards to attached clients via OSC 52 regardless of pane visibility.
- New canonical seam `lib/tui_clipboard.copy_to_system_clipboard(app, text)`: always performs the Textual OSC 52 copy (the working path outside tmux), and when `$TMUX` is set also pushes through the gateway.
- All 5 direct `copy_to_clipboard` call sites converted to the seam.
- Guard test `tests/test_tui_clipboard_seam.sh` fails on any future direct `copy_to_clipboard` call outside the seam module (with negative controls), and runs the seam's unit tests.
- Convention documented in `aidocs/framework/tui_conventions.md`.

## Acceptance Criteria

- Copy from a hidden/background tmux pane lands on the system clipboard (verified live: helper run in a detached window set the Wayland clipboard).
- `tests/test_tmux_exec.py`, `tests/test_tui_clipboard.py`, `tests/test_tui_clipboard_seam.sh`, `tests/test_no_raw_tmux.sh` all pass.
