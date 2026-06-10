---
priority: medium
effort: medium
depends: [t952_5]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [952_1, 952_2, 952_3, 952_4, 952_5]
created_at: 2026-06-10 12:54
updated_at: 2026-06-10 12:54
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t952_1] AITASKS_TMUX_SOCKET unset: all tmux operations target the default socket (no -L), behavior unchanged. Set it to a test value: a separate isolated server is used and the flag appears in spawned argv.
- [ ] [t952_2] Launch an agent from the TUI (launch_in_tmux): new window/pane appears, pane PID is captured, and focus switches to it correctly.
- [ ] [t952_2] `j` TUI switcher cross-session teleport (switch-client) lands on the correct pane in the correct session, with no prefix-match crossing into a sibling project session.
- [ ] [t952_2] minimonitor companion pane spawns beside the monitor and despawns only when the primary pane dies (not before; no orphaned companion left behind).
- [ ] [t952_2] codebrowser window opens/focuses correctly via launch_or_focus_codebrowser (set-environment + new-window/select-window).
- [ ] [t952_3] `ait monitor` refresh captures live pane content with the control-mode client active; killing the control client mid-run falls back to subprocess with no visible stall or content gap.
- [ ] [t952_3] From the monitor: send-keys, send-enter, kill-pane, and switch-to-pane each act on the correct target pane.
- [ ] [t952_4] `ait ide` attaches to the configured session and switches to the monitor window; the compound `attach \; select-window` command works (\; not mangled by the socket wrapper).
- [ ] [t952_4] Detached-session persistence: spawn a session via the shell path, then close the launching terminal — the session survives (systemd-run/setsid scope intact).
- [ ] [t952_4] syncer window auto-spawns when tmux.syncer.autostart is configured.
- [ ] [t952_5] `ait projects` list / resolve return identical results to pre-refactor across quoted, unquoted, stale, and AITASKS_PROJECTS_INDEX-override registry entries.
- [ ] [t952_5] Introduce a raw `tmux` call in a non-allowlisted file: test_no_raw_tmux.sh fails; remove it: the guard passes.
