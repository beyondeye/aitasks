---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitor, tmux]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-06 23:04
updated_at: 2026-06-06 23:09
---

## Problem

`ait ide` (and the TUI switcher) can end up with a **board TUI running in a
tmux window named `monitor`**, plus a duplicate `monitor` window. Reproduced
live in session `aitasks_go`:

```
1: monitor   <- genuine monitor TUI ("tmux Monitor - 2 sessions...")
2: monitor   <- actually a BOARD TUI ("Esc to return to board")  <-- BUG
4: board     <- genuine board TUI
```

Window index 2 is named `monitor` but is running the **board** application.

## Root cause

`monitor_app.py` `on_mount` (around line 675) renames its tmux window with no
target:

```python
subprocess.run(["tmux", "rename-window", "monitor"], capture_output=True, timeout=5)
```

This is the **only** code in the repo that names a window `monitor` (`ait ide`
and `tmux_bootstrap.sh` create it with `-n monitor`; the board never renames
itself). Because the call has **no `-t` target**, tmux applies it to the
"current window." With multiple attached clients (the live monitor reports
"2 sessions attached"), tmux's untargeted current-window resolution is
ambiguous and can land on the **active window of another client** — a board
the user just launched/switched to — relabeling that board window `monitor`.

### Knock-on effect

The TUI switcher identifies running TUIs **by window name**
(`_running_names` in `tui_switcher.py`). Once a board window is mislabeled
`monitor`, the switcher treats it *as* monitor, so a subsequent genuine
monitor launch creates a **second** `monitor` window — the observed duplicate.

## Fix direction

Pin the rename to monitor's own pane instead of relying on the ambiguous
current-window resolution:

```python
pane = os.environ.get("TMUX_PANE")
argv = ["tmux", "rename-window"]
if pane:
    argv += ["-t", pane]
argv += ["monitor"]
subprocess.run(argv, capture_output=True, timeout=5)
```

`TMUX_PANE` is already read reliably elsewhere in monitor
(`tmux_monitor.py:200`), so the pane target is essentially always available;
fall back to the untargeted form only when it is unset.

## Files

- `.aitask-scripts/monitor/monitor_app.py` (`on_mount`, ~line 662-679) — the fix
- `.aitask-scripts/monitor/tmux_monitor.py:200` — confirms `TMUX_PANE` availability
- `.aitask-scripts/lib/tui_switcher.py` — name-based `_running_names` matching (knock-on context)

## Notes

- Consider auditing other untargeted `tmux` window/pane mutations for the same
  multi-client hazard while here.
- Adjacent but distinct: t633/t632 cover exact tmux **session** targeting for
  `ait ide`; this bug is about **window rename** targeting — not folded in.
- Verification: with two attached clients to the same session, launch a board
  and a monitor; confirm no board window is ever renamed `monitor` and no
  duplicate `monitor` window appears.
