---
Task: t2143_verify_on_mise_linux_host.md
Base branch: main
Output branch: main
---

# t2143 — Manual-verification auto-execution log (autonomous)

Host: Omarchy Linux, tmux 3.8, mise 2026.10.12, systemd user manager running,
claude 2.1.310 via mise. Fix under test: t1689 (`86b4b96af`, in HEAD).

**Isolation.** Every spawn ran on scratch tmux servers (`-L ait_v2143`,
`-L ait_v2143sd`) with `TMUX`/`TMUX_PANE` unset and
`AITASKS_TMUX_SOCKET=ait_v2143` set server-wide, so no TUI could address the
live `-L ait` server hosting this session. Scratch servers were started from
the bad-order env:
`env -u __MISE_* -u TMUX -u TMUX_PANE PATH="$HOME/.local/bin:/usr/share/omarchy/bin:$HOME/.local/share/mise/shims:/usr/bin"`.

**Pane inspection** (`inspect.sh`): pane_pid → `/proc/<pid>/exe`, cmdline,
PATH head, child processes, count of `mise use -g --quiet claude` processes,
`Claude Code` banner in `capture-pane`.

**Control-power caveat.** On this host's mise version the original infinite
loop no longer reproduces even without the fix: under the bad order
`mise x claude -- sh -c 'command -v claude'` still resolves to
`~/.local/bin/claude` (the hazard is present), but the nested `mise x` inherits
`__MISE_DIFF` and the second hop reaches the real binary. A raw bad-order pane
running bare `claude --version` (no ait) printed `2.1.310` with rc 0. So
items 1–4 prove the fixed routes boot the real binary on this host; they
cannot prove the fix is what prevents a loop here. The normalizers (shell and
Python agree) do move `mise/shims` ahead of `~/.local/bin` for the bad PATH.

## Execution Log

### Item 1
- Item text: from a bad-order shell, `ait codeagent invoke explore` shows the banner (no blank pane, no `mise use -g` loop)
- Approach: TUI/tmux — pane running `env PATH=<bad> bash --noprofile --norc -c 'ait codeagent invoke explore'`
- Output (trimmed): exe=`mise/installs/claude/2.1.310/claude`, cmdline `…/installs/claude/latest/claude --model claude-opus-5-5 /aitask-explore`, mise-use procs 0, banner `Claude Code v2.1.310`
- Verdict: pass (with the control caveat above)

### Item 2
- Item text: literal gateway repro `PATH=<bad incl. omarchy bin> tmux new-window -d -n repro 'ait codeagent invoke explore'`; pane_pid is the real claude
- Approach: CLI — the literal command on the scratch server
- Output (trimmed): pane_pid exe = real claude binary (not `/bin/bash ~/.local/bin/claude`), banner up, 0 mise-use procs
- Verdict: pass (with the control caveat)

### Item 3
- Item text: switcher `x` and `e` from a companion minimonitor and from the board boot the real claude
- Approach: TUI — `ait board` launched from the bad-order env; `send-keys j x`, `j e R` on the board pane, then the same on companion minimonitor `%9`
- Output (trimmed): agent-explore-1 (board x), agent-raw-1 (board e, bare `claude --model claude-sonnet-5-5`), agent-explore-2 (minimonitor x), agent-raw-2 (minimonitor e): all exe `mise/installs/claude/2.1.310/claude`, banner up, 0 mise-use procs. Companion minimonitors spawned alongside.
- Verdict: pass

### Item 4
- Item text: `ait monitor` / `ait minimonitor` spawn paths (monitor_core spawn_tui, minimonitor new-window) produce working panes
- Approach: TUI + Python probe. Minimonitor `m` with no monitor window → `new-window 'ait monitor'`. `spawn_tui_probe.py`: `TmuxMonitor("v2143")`, `start_control_client()`, `spawn_tui("codebrowser")`, run from a bad-order pane on a server whose global PATH is bad
- Output (trimmed): monitor window rendered (pane PATH `~/.aitask/bin:mise/shims:~/.local/bin`); probe `control_alive True`, `spawn_tui True`; codebrowser rendered, pane PATH `~/.aitask/bin:mise/shims:~/.local/bin` (normalized, not the server's bad global PATH, so the pane-creating verb bypassed the control client)
- Verdict: pass

### Item 5
- Item text: first-server launch via systemd-run: global PATH lists mise shims ahead of `~/.local/bin`; first window works
- Approach: CLI — `ait_tmux_new_session_persistent v2143sd "$PWD" agent "ait codeagent invoke explore"` (the `ait ide` first-start function, `tmux_bootstrap.sh:953`) from the bad-order env with `AITASKS_TMUX_SOCKET=ait_v2143sd`. A fresh socket stood in for "no `-L ait` server", because the live `-L ait` server hosts this session and must not be killed
- Output (trimmed): rc 0; server cgroup `session.slice/ait-tmux-v2143sd-*.service` (systemd rung taken); `show-environment -g PATH` = `mise/shims:~/.local/bin:/usr/share/omarchy/bin:/usr/bin` (user-manager PATH starts `/usr/share/omarchy/bin:mise/command-wrappers/bin:…`, so the PATH came from `--setenv`); first window booted real claude 2.1.310 with banner
- Verdict: pass

### Item 6
- Item text: healthy-order behaviour unchanged: from a normal mise-activated shell, pane PATH still starts with `~/.aitask/bin` and agents boot as before
- Approach: CLI — normalize this session's own activated PATH (shell + Python); spawn panes via `ait_tmux new-window` and `TmuxClient.run(["new-window", …])` from it; read pane PATH; spawn an agent
- Output (trimmed): both normalizers return CHANGED. mise 2026.10.x puts `~/.local/share/mise/command-wrappers/bin` (symlinks to `/usr/bin/mise`) first; it is not in the normalizer's mise set, so it counts as the first "other" entry and `~/.aitask/bin` loses its leading-framework slot. Pane PATH from both gateways starts `mise/installs/java/21/bin`; `command-wrappers/bin` moved 1 → 9, `~/.aitask/bin` 2 → 10. Agent still booted the real claude (banner up)
- Verdict: fail → follow-up **t2144** (diagnosis appended to it)

### Item 7
- Item text: optional: run `bash tests/test_tmux_spawn_path_live.sh` and the full `tests/run_all_python_tests.sh` on this host
- Approach: CLI
- Output (trimmed): live test `Results: 18 passed, 0 failed, 18 total`; full suite `PYTHON SUITE: PASSED (runner=pytest, exit=0)` — parallel lane 9911 passed / 6 skipped (8m03s), serial carve-out 13 passed
- Verdict: pass

## Cleanup
- Scratch tmux servers `-L ait_v2143` and `-L ait_v2143sd`: killed (`kill-server` on those sockets only); `-L ait` untouched
- The systemd transient unit `ait-tmux-v2143sd-*` went with its server (`--collect`)
- Scratch helpers `inspect.sh`, `spawn_tui_probe.py`, `pysuite.log` live in the session scratchpad (outside the repo)
