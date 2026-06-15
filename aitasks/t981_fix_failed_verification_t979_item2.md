---
priority: medium
effort: medium
depends: [978]
issue_type: bug
status: Implementing
labels: [verification, bug]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-12 11:28
updated_at: 2026-06-15 16:28
boardidx: 30
---

## Failed verification item from t978

> Detach tmux (prefix d) → resize the terminal much wider → reattach (tmux attach) → confirm the minimonitor pane snaps back to ~40 columns instead of staying proportionally wide (the reported bug)

### Source

- **Manual-verification task:** `aitasks/t979_manual_verification_pin_minimonitor_pane_width_on_resize_fol.md` (item #2)
- **Origin feature task:** t978
- **Origin archived plan:** `aiplans/archived/p978_pin_minimonitor_pane_width_on_resize.md`

### Commits that introduced the failing behavior

- a97bc6445 bug: Pin minimonitor companion pane width on resize (t978)

### Files touched by those commits

- .aitask-scripts/lib/tmux_exec.py
- .aitask-scripts/monitor/minimonitor_app.py
- .aitask-scripts/monitor/tmux_monitor.py
- tests/test_tmux_exec.py

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t979 item #2.

### Root cause (diagnosed during t979 auto-verification, 2026-06-12)

The re-pin **fires correctly but does not take effect when the terminal is made
wider** — i.e. the exact reported scenario. Diagnosis (reproduced on an isolated
tmux socket with a real PTY-attached client driving genuine SIGWINCH/on_resize):

1. `MiniMonitorApp.on_resize` → `_maybe_pin_width` **does** fire on a window
   growth, with `self.size.width` correctly reflecting the drifted width
   (e.g. 140), and **does** issue `resize-pane -x 40` (confirmed via instrumented
   logging: `action=RESIZE->40`).
2. But the pane stays at 140. The command is lost.

Isolated the cause to the **transport**, not timing or the argv:

| how `resize-pane -x 40` is issued (window just grown, client @400) | result |
|---|---|
| via the minimonitor's **control client** (`tmux -C attach`), immediately in `on_resize` | **pane stays 140 (FAIL)** |
| via a **subprocess** `tmux resize-pane`, immediately | pane → 40 (works) |
| via the **control client**, after a ~1.5s settle | pane → 40 (works) |
| via the control client on a *shrink* (400→300) | pane → 40 (works) |

So: an **immediate `resize-pane` sent through a tmux control-mode client during
the window-growth reflow loses the race** to tmux's proportional layout pass. The
minimonitor's `TmuxMonitor.resize_pane` routes through `run_via_control` (control
client when alive — the normal runtime state), so production hits exactly this
path. The unit tests (`TestResizePane`) only cover argv construction and pass —
they do not exercise the live control-client-vs-reflow race.

Note `tmux_exec.py:resize_pane` was added with no callers using the subprocess
(`backend=None`) path in this flow; the monitor always passes `backend`.

### Suggested fix directions (pick during planning)

- **Defer the re-pin** off the immediate `on_resize` (e.g. a short
  `set_timer`/`call_after_refresh`) so tmux finishes the proportional reflow
  before `resize-pane` is sent — the ~1.5s-settle case proves a delayed control
  command sticks (tune the delay; even one event-loop tick may suffice).
- **Route the re-pin through a subprocess** (`backend=None`) instead of the
  control client — an immediate subprocess `resize-pane` sticks even mid-reflow.
- **Verify-and-retry**: after issuing the resize, re-read `pane_width`; if still
  `> target`, re-issue (handles the race without guessing a delay).

Repro scripts used live under `/tmp/auto_verify_979/` at diagnosis time
(`pty_ctrl2.py` reproduces the failure with no minimonitor); see
`aiplans/p979_manual_verification_auto.md` for the full execution log.
