---
priority: medium
effort: medium
depends: [t952_5]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t952_1, t952_2, t952_3, t952_4, t952_5]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 12:54
updated_at: 2026-06-11 09:33
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t952_1] AITASKS_TMUX_SOCKET unset: all tmux operations target the default socket (no -L), behavior unchanged. Set it to a test value: a separate isolated server is used and the flag appears in spawned argv. — PASS 2026-06-11 09:22 auto: shell+python gateway confirmed — AITASKS_TMUX_SOCKET unset emits no args (default socket); set emits -L <val> (isolated server); targets =sess / =sess:win. Backed by test_tmux_exec.py(35), test_tmux_run_parity, test_tmux_exact_session_targeting(10/10).
- [x] [t952_2] Launch an agent from the TUI (launch_in_tmux): new window/pane appears, pane PID is captured, and focus switches to it correctly. — PASS 2026-06-11 09:22 auto: test_launch_in_tmux_pane_pid.py(17) pins gateway-routed new-window argv (-P -F #{pane_pid}), pane-PID parse, and split-window select-window follow-up. Mocked-Popen unit level; live agent launch not exercised.
- [x] [t952_2] `j` TUI switcher cross-session teleport (switch-client) lands on the correct pane in the correct session, with no prefix-match crossing into a sibling project session. — PASS 2026-06-11 09:27
- [x] [t952_2] minimonitor companion pane spawns beside the monitor and despawns only when the primary pane dies (not before; no orphaned companion left behind). — PASS 2026-06-11 09:28
- [x] [t952_2] codebrowser window opens/focuses correctly via launch_or_focus_codebrowser (set-environment + new-window/select-window). — PASS 2026-06-11 09:29
- [x] [t952_3] `ait monitor` refresh captures live pane content with the control-mode client active; killing the control client mid-run falls back to subprocess with no visible stall or content gap. — PASS 2026-06-11 09:22 auto: test_tmux_control.sh(12 cases) + test_tmux_control_resilience.sh(A-E) cover control-mode capture, transport failure, reconnect, and subprocess-fallback parity. 'No visible stall' visual not directly asserted.
- [x] [t952_3] From the monitor: send-keys, send-enter, kill-pane, and switch-to-pane each act on the correct target pane. — PASS 2026-06-11 09:30
- [x] [t952_4] `ait ide` attaches to the configured session and switches to the monitor window; the compound `attach \; select-window` command works (\; not mangled by the socket wrapper). — PASS 2026-06-11 09:31
- [x] [t952_4] Detached-session persistence: spawn a session via the shell path, then close the launching terminal — PASS 2026-06-11 09:32
- [skip] [t952_4] syncer window auto-spawns when tmux.syncer.autostart is configured. — SKIP 2026-06-11 09:33 tmux.syncer.autostart not configured in this setup — nothing to exercise
- [x] [t952_5] `ait projects` list / resolve return identical results to pre-refactor across quoted, unquoted, stale, and AITASKS_PROJECTS_INDEX-override registry entries. — PASS 2026-06-11 09:22 auto: test_registry_reader_parity.sh(27/27) freezes byte-for-byte parity for unquoted/single/double-quoted/all-4-fields/stale entries with AITASKS_PROJECTS_INDEX override; test_projects_cmd.sh(16/16) green.
- [x] [t952_5] Introduce a raw `tmux` call in a non-allowlisted file: test_no_raw_tmux.sh fails; remove it: the guard passes. — PASS 2026-06-11 09:22 auto: empirical negative test — injected raw 'tmux kill-server' in non-allowlisted .aitask-scripts/_rawtmux_probe_t952_6.sh: guard FAILED naming file:line (exit 1); removed file: guard PASSED (exit 0).
