---
priority: medium
effort: medium
depends: [1451]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1451]
followup_kind: manual_verification
created_at: 2026-08-07 17:12
updated_at: 2026-08-13 23:07
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1451

## Verification Checklist

- [ ] [guard] In a live `ait` session, launch an agent from `ait board` so a companion spawns; confirm `tmux show-options -p -t <companion> @aitask_monitor_kind` reads `minimonitor:<pid>` with that pid alive.
- [ ] [guard] Run `ait minimonitor` in another pane of that same window — it must print "A monitor is already running in this window." and exit without starting a TUI.
- [ ] [guard] Open `ait monitor` in its own window; confirm its pane carries `monitor:<pid>`, and that a second `ait monitor` attempt in that window is refused.
- [ ] [guard] Quit a minimonitor normally; confirm `@aitask_monitor_kind` is cleared on that pane (`tmux show-options -pqv -t <pane> @aitask_monitor_kind` prints nothing).
- [ ] [hook] On a board-launched agent window, confirm `tmux show-hooks -p -t <agent-pane>` lists a `pane-died` entry invoking `aitask_companion_cleanup.sh`, and that `remain-on-exit` is `on`.
- [ ] [hook] Exit that agent; confirm the companion despawns, the window closes, and no dead pane (`#{pane_dead}` = 1) lingers anywhere in the real `-L ait` session. NOTE: verified only against an isolated tmux server during implementation — this is the live-server gap.
- [ ] [hook] Repeat with a plain shell added to the window — the agent's exit must kill only the agent pane and leave the companion alive.
- [ ] [ordering] Spawn a shadow (`e` in minimonitor) BEFORE a companion exists in that window, then let the agent exit — confirm both the shadow and the companion are cleaned up. This is the shadow-first ordering t1451 fixed.
- [ ] [staleness] With a shadow running and a stale banner showing in minimonitor, interrupt tmux (stall or briefly kill the server) — confirm the banner is PRESERVED, not cleared.
- [ ] [coverage] Run `bash tests/test_monitor_shadow_spawn_live.sh` from a terminal that is NOT inside tmux. It refused to run during t1451 (`require_clean_ait_server`), and it is the only live coverage of the renamed `attach_companion_cleanup_hook`.
