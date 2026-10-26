---
priority: high
effort: low
depends: []
issue_type: manual_verification
status: Done
labels: [tmux, tui_switcher, codeagent, minimonitor]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
assigned_to: dario-e@beyond-eye.com
anchor: 1689
followup_kind: risk_mitigation
created_at: 2026-10-26 08:09
updated_at: 2026-10-26 09:51
completed_at: 2026-10-26 09:51
---

## Origin

Risk-mitigation ("after") follow-up for t1689, created at Step 8d after implementation landed.

## Risk addressed

systemd-run --setenv rung untestable on macOS; real `mise x` + Omarchy shim not exercised.

- Code-health: The systemd-run rung's new `--setenv=PATH=…` changes the first server's global PATH for **every** Linux/systemd user (user-manager PATH → caller's normalized PATH), and cannot be exercised live on this macOS host — only its argv is unit-tested · severity: medium
- Goal-achievement: The `mise x` re-resolution mechanism comes from the task's Omarchy-host analysis; mise is not installed here, so the fix is proven against a synthetic recursing shim and the real tmux PATH mechanics, not against real `mise x` + the Omarchy shim · severity: medium

## Goal

On the Omarchy/mise Linux host where t1689's blank-pane bug was observed, confirm that the shipped fix boots the real agent binary on every spawn route, including the two that could not run on the macOS development host: the systemd-run first-server rung and the real `mise x` Omarchy shim. Use t1689's archived task body ("Reproduction") and plan (`aiplans/archived/p1689_*.md`) for the exact commands. The fix normalizes the PATH each tmux client carries (mise shims/installs first) and keeps the launcher (`tmux`/`setsid`/`systemd-run`) the binary the caller's PATH resolves.

## Verification Checklist

- [x] From a shell whose PATH puts `~/.local/bin` ahead of `~/.local/share/mise/shims` and has no `__MISE_*` vars (e.g. `env -u __MISE_ORIG_PATH -u __MISE_SESSION -u __MISE_DIFF PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:/usr/bin" bash`), `ait codeagent invoke explore` shows the Claude Code banner within normal boot time (no blank pane, no `mise use -g` loop in `ps`) — PASS 2026-10-26 09:36 auto: scratch -L ait_v2143 server, bad-order PATH, no __MISE_*: pane boots real claude (exe mise/installs/claude/2.1.310/claude), banner up, 0 mise-use procs. Control: bare claude also boots on mise 2026.10.12 (nested mise x inherits __MISE_DIFF), so the loop no longer reproduces here; normalizer confirmed to move shims first
- [x] From that same bad-order shell, the gateway repro boots the agent: `PATH="$HOME/.local/bin:/usr/share/omarchy/bin:$HOME/.local/share/mise/shims:/usr/bin" tmux new-window -d -n repro 'ait codeagent invoke explore'`; the pane_pid's process is the real `claude`, not `/bin/bash ~/.local/bin/claude` — PASS 2026-10-26 09:36 auto: literal repro (raw tmux new-window, omarchy-bin bad PATH) on scratch server: pane_pid is the real claude binary (not /bin/bash ~/.local/bin/claude), banner up; same control caveat as item 1
- [x] TUI switcher `x` (explore) and `e` (code agent), pressed from a companion minimonitor and from the board, open an agent pane that boots the real `claude` — PASS 2026-10-26 09:40 auto: scratch server (global PATH bad order, no __MISE_*), board launched from bad-order PATH. Switcher x and e(R) from the board, and x and e(R) from a companion minimonitor: all 4 panes boot the real claude 2.1.310 (pane_pid exe in mise/installs), banner up, 0 mise-use procs; e route runs bare 'claude' so it relies on gateway normalization alone
- [x] `ait monitor` / `ait minimonitor` spawn paths (monitor_core spawn_tui, the minimonitor new-window) produce working panes — PASS 2026-10-26 09:41 auto: minimonitor m -> new-window 'ait monitor' booted the monitor (pane PATH ~/.aitask/bin:mise/shims:~/.local/bin). monitor_core.TmuxMonitor.spawn_tui('codebrowser') with a LIVE control client (control_alive True) from a bad-order pane on a server whose global PATH is bad: rc True, codebrowser rendered, pane PATH normalized (shims before ~/.local/bin), so the pane-creating verb bypassed the control client
- [x] First-server launch via systemd-run: with no `-L ait` server running, start `ait ide` (or the board's first session) and check that `tmux -L ait show-environment -g PATH` lists mise's shims ahead of `~/.local/bin`, and that the first window works — PASS 2026-10-26 09:37 auto: ait_tmux_new_session_persistent (the ait ide first-start path) on fresh socket ait_v2143sd from a bad-order PATH: systemd-run rung taken (server in session.slice/ait-tmux-v2143sd-*.service); show-environment -g PATH = mise/shims:~/.local/bin:/usr/share/omarchy/bin:/usr/bin (user-manager PATH has no such order); first window booted real claude 2.1.310 with banner. Fresh socket used since the live -L ait server hosts this session
- [fail] Healthy-order behaviour is unchanged: from a normal mise-activated interactive shell, pane PATH still starts with `~/.aitask/bin` and agents boot as before — FAIL 2026-10-26 09:38 follow-up t2144
- [x] Optional: run `bash tests/test_tmux_spawn_path_live.sh` and the full `tests/run_all_python_tests.sh` on this host (a mise host takes the PATH-changing branches that macOS never does) — PASS 2026-10-26 09:50 auto: tests/test_tmux_spawn_path_live.sh 18/18 passed; full tests/run_all_python_tests.sh: PYTHON SUITE: PASSED (runner=pytest, exit=0), parallel lane 9911 passed / 6 skipped + serial carve-out 13 passed
