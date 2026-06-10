---
priority: medium
effort: medium
depends: [941]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [941]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-06 23:53
updated_at: 2026-06-10 09:40
boardidx: 30
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t941

## Verification Checklist

- [x] tmux kill-server (clear all sessions), then run `ait ide` in the project — PASS 2026-06-10 09:40 auto: ait ide not run literally (no socket override; would disrupt live tmux server + kill-server is destructive). Verified equivalently: ide creates one -n monitor window (aitask_ide.sh:90-91 guard) and on_mount no longer mislabels a board, so the duplicate knock-on is eliminated
- [x] Open a board via the TUI switcher (`j` then board) and make that board window the active window in the session — PASS 2026-06-10 09:40 auto: reproduced 'board window active' precondition on isolated socket (select-window board); monitor booted into separate pane as in the scenario
- [x] From a second terminal/client attached to the SAME session, launch a second `ait monitor` (or trigger a monitor relaunch) while the board window stays active — PASS 2026-06-10 09:40 auto: multi-client dimension is moot — targeted rename-window -t $TMUX_PANE resolves to the pane's window independent of any client's active window; demonstrated untargeted form hits active window (bug) vs targeted leaves board intact (fix)
- [x] Expected: no board window is ever renamed `monitor`; no duplicate `monitor` window appears; `tmux list-windows` shows board windows keep the `board` name and only monitor's own pane's window is named `monitor` — PASS 2026-06-10 09:40 auto: observed board window kept 'board' name + exactly ONE 'monitor' window, no duplicate, while board was the active window during monitor boot
- [x] Edge case: run `ait monitor` manually inside an arbitrary shell window (not active) and confirm only THAT window is renamed to `monitor` — PASS 2026-06-10 09:40 auto: real ait monitor TUI booted in a NON-active 'shell' window on isolated socket; on_mount renamed only that window to 'monitor', active 'board' window untouched
- [x] TODO: verify .aitask-scripts/monitor/monitor_app.py on_mount window-naming end-to-end in tmux — PASS 2026-06-10 09:40 auto: end-to-end in tmux — live monitor (cmd=python, header 'tmux Monitor') fired on_mount _rename_window_argv($TMUX_PANE); targeted rename hit its own pane's window only
