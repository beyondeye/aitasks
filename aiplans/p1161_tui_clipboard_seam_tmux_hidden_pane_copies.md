---
Task: t1161_tui_clipboard_seam_tmux_hidden_pane_copies.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Fixed TUI clipboard copies silently never reaching the system clipboard when
the copying pane is not in the tmux client's visible window. Textual's
`App.copy_to_clipboard` emits a bare OSC 52 escape; tmux (verified on 3.7b
with `set-clipboard on`) forwards a pane's OSC 52 to the outer terminal only
for **visible** panes — from a background window, or a session with no
attached terminal client, the text lands in a tmux paste buffer and the
system clipboard stays untouched while the TUI still notifies "copied to
clipboard". The fix introduces a canonical clipboard seam that keeps the
OSC 52 copy and, inside tmux, additionally routes the text through the tmux
server with `load-buffer -w`, which forwards to attached clients regardless
of pane visibility.

## Files Modified

- `.aitask-scripts/lib/tmux_exec.py` — new gateway method
  `TmuxClient.set_clipboard(text, timeout)`: runs `tmux load-buffer -w -`
  with the text on stdin; returns `True`/`False`, swallowing
  timeout/`FileNotFoundError`/`OSError` per the gateway's error contract.
- `.aitask-scripts/lib/tui_clipboard.py` (new) — canonical seam
  `copy_to_system_clipboard(app, text)`: always performs the Textual OSC 52
  copy (keeps Textual's `_clipboard` mirror in sync; the working path outside
  tmux), and when `$TMUX` is set also pushes through a module-level
  `TmuxClient` (best-effort, failure not surfaced).
- `.aitask-scripts/monitor/minimonitor_app.py` — concern-copy modal callback
  (`_on_concerns_picked`) routed through the seam.
- `.aitask-scripts/lib/agent_command_screen.py` — copy-command / copy-prompt
  buttons routed through the seam.
- `.aitask-scripts/codebrowser/codebrowser_app.py` — copy-relative /
  copy-absolute path buttons routed through the seam.
- `.aitask-scripts/monitor/monitor_shared.py` — docstring pointer updated to
  name the seam instead of `app.copy_to_clipboard`.
- `aidocs/framework/tui_conventions.md` — new section "Clipboard copies route
  through `lib/tui_clipboard.copy_to_system_clipboard`" documenting the
  visible-pane limitation and the seam rule.
- `tests/test_tmux_exec.py` — `TestSetClipboard`: argv/stdin shape
  (`load-buffer -w -` + socket flag), non-zero rc → `False`, spawn-failure /
  timeout → `False`.
- `tests/test_tui_clipboard.py` (new) — seam unit tests: `$TMUX` set →
  gateway forward called with the text; unset → OSC 52 only; gateway failure
  is best-effort (no raise).
- `tests/test_tui_clipboard_seam.sh` (new) — enforcement guard: fails on any
  direct `.copy_to_clipboard(` call in `.aitask-scripts/**/*.py` outside the
  seam module; includes negative controls (rogue call flagged, docstring
  mention not flagged, seam's own call exempt) and runs the python unit
  tests.

## Probable User Intent

The user reported Omarchy's Super+V "universal paste" (a synthesized
Shift+Insert into the focused window) doing nothing. End-to-end diagnosis
showed the Omarchy binding, ghostty's `shift+insert=paste_from_clipboard`,
and the Wayland clipboard all working; the actual failure was copy-side —
minimonitor's shadow-concern copy (Textual OSC 52) was being swallowed by
tmux whenever the minimonitor pane was not in the visible window (or lived in
a session with no attached terminal, e.g. a second project session on the
`-L ait` server). The tmux paste buffer contained the payload while
`wl-paste` was empty. Intent: make every framework TUI copy reliably reach
the system clipboard from any pane, visible or not, without breaking the
non-tmux path.

## Final Implementation Notes

- **Actual work done:** gateway `set_clipboard` method + `lib/tui_clipboard`
  seam + 5 call-site conversions + guard test + unit tests + conventions doc.
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed).
- **Issues encountered:** N/A (changes were already made before wrapping).
- **Key decisions:**
  - Explicit helper function + grep-based guard test (source enforcement)
    over a `copy_to_clipboard` mixin override — no MRO surprises on
    Screen classes that only proxy `self.app.copy_to_clipboard`, and the
    guard blocks future direct calls.
  - Default `TmuxClient()` socket resolution (`AITASKS_TMUX_SOCKET` /
    `-L ait`) rather than parsing `$TMUX` — matches the server framework
    TUIs run on and avoids hand-threading `-S` against the gateway rules.
  - `load-buffer -w` chosen over `wl-copy`/platform tools: platform-agnostic
    (works over SSH and on macOS) and needs no new dependency; tmux < 3.2
    (no `-w`) degrades to `False` with the OSC 52 copy already done.
  - Verified live: running the seam from a detached tmux window set the
    Wayland clipboard (previously the exact failing scenario).
