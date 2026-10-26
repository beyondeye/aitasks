---
priority: high
effort: low
depends: []
issue_type: manual_verification
status: Implementing
labels: [tmux, tui_switcher, codeagent, minimonitor]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
assigned_to: dario-e@beyond-eye.com
anchor: 1689
followup_kind: risk_mitigation
created_at: 2026-10-26 08:09
updated_at: 2026-10-26 08:23
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

- [ ] From a shell whose PATH puts `~/.local/bin` ahead of `~/.local/share/mise/shims` and has no `__MISE_*` vars (e.g. `env -u __MISE_ORIG_PATH -u __MISE_SESSION -u __MISE_DIFF PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:/usr/bin" bash`), `ait codeagent invoke explore` shows the Claude Code banner within normal boot time (no blank pane, no `mise use -g` loop in `ps`)
- [ ] From that same bad-order shell, the gateway repro boots the agent: `PATH="$HOME/.local/bin:/usr/share/omarchy/bin:$HOME/.local/share/mise/shims:/usr/bin" tmux new-window -d -n repro 'ait codeagent invoke explore'`; the pane_pid's process is the real `claude`, not `/bin/bash ~/.local/bin/claude`
- [ ] TUI switcher `x` (explore) and `e` (code agent), pressed from a companion minimonitor and from the board, open an agent pane that boots the real `claude`
- [ ] `ait monitor` / `ait minimonitor` spawn paths (monitor_core spawn_tui, the minimonitor new-window) produce working panes
- [ ] First-server launch via systemd-run: with no `-L ait` server running, start `ait ide` (or the board's first session) and check that `tmux -L ait show-environment -g PATH` lists mise's shims ahead of `~/.local/bin`, and that the first window works
- [ ] Healthy-order behaviour is unchanged: from a normal mise-activated interactive shell, pane PATH still starts with `~/.aitask/bin` and agents boot as before
- [ ] Optional: run `bash tests/test_tmux_spawn_path_live.sh` and the full `tests/run_all_python_tests.sh` on this host (a mise host takes the PATH-changing branches that macOS never does)
