---
priority: medium
effort: medium
depends: [t719_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [719_1, 719_2, 719_3, 719_4]
created_at: 2026-04-30 10:32
updated_at: 2026-04-30 10:32
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t719_2] `ait monitor` against a session with 5+ agent panes: pane list populates within one tick
- [ ] [t719_2] `ait monitor` content preview pane shows live agent output as the agent writes
- [ ] [t719_2] `ait monitor` idle indicator fires for an agent pane after the configured threshold (default 5s of no change)
- [ ] [t719_2] `ait monitor` `q` exits cleanly: no zombie tmux clients in `tmux list-clients` after exit
- [ ] [t719_2] `ait minimonitor` companion behavior: tab-to-focus-agent, send-Enter forwards to the right pane
- [ ] [t719_2] `ait minimonitor` `m` switches to full monitor without disturbing the agent pane
- [ ] [t719_2] Multi-session toggle (`M`) in monitor: cross-session capture works, sessions sorted, cache invalidates on toggle
- [ ] [t719_2] Compare-mode toggle (`d`): per-pane override applies; idle still fires under Codex CLI's animated ANSI under `stripped`; raw mode flagged in footer
- [ ] [t719_2] Cold tmux: launch monitor BEFORE the user's main agent windows exist; agents appearing later show up in the next tick
- [ ] [t719_3] Adaptive polling: idle session ramps the refresh interval up over ~30s; observe by infrequent UI updates / `strace -p` showing reduced tmux activity
- [ ] [t719_3] Adaptive polling: first pane content change after a long idle period brings the next tick back to base interval immediately
- [ ] [t719_3] Adaptive polling: `M` multi-session toggle re-baselines the interval and refreshes immediately
- [ ] [t719_4] (skip if Phase 4b not shipped) Pipe-pane: agent activity reflects in the pane preview within sub-second (snappier than `t719_3` baseline)
- [ ] [t719_4] (skip if Phase 4b not shipped) Pipe-pane: no leftover fifo files after `q` — `ls /tmp/ait-pipe-pane-* 2>/dev/null` is empty
- [ ] [t719_4] (skip if Phase 4b not shipped) Pipe-pane: forced crash (`kill -9`) followed by relaunch cleans up stale fifos at startup
- [ ] [All]    Fall-back path: kill the tmux server while monitor is open; confirm the apps don't crash and continue via subprocess fallback (sluggish but functional) until the user re-attaches
- [ ] [All]    Two aitasks projects side-by-side (e.g. `aitasks` and `aitasks_mob`): each project's monitor sees only its own panes; no cross-contamination between sessions
- [ ] [All]    `ait monitor` and `ait minimonitor` running concurrently in the same session: both refresh independently, no double-counting of fork events
