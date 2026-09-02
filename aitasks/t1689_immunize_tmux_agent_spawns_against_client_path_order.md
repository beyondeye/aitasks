---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [tmux, tui_switcher, codeagent, minimonitor]
gates: [risk_evaluated]
created_at: 2026-09-02 14:59
updated_at: 2026-09-02 14:59
---

## Symptom

Pressing `x` (explore) or `e` (code agent) in the TUI switcher opens a new tmux
window, but the code agent never appears: the agent pane stays **blank**
indefinitely while the companion minimonitor pane renders normally. Observed
2026-09-02 at 13:59:25, 13:59:55 and 14:00:39 (three agent+minimonitor pane
pairs, each killed by the user after 25s / 6s / 9s). Spawns at 13:52 and 13:54,
and every spawn after 14:13, worked. Typing `claude` in a fresh interactive pane
always works.

## Root cause (reproduced, with control)

The agent pane runs the **Omarchy mise shim** at `~/.local/bin/claude`
(written by Omarchy migration `1787573629` on 2026-08-29):

```bash
#!/bin/bash
export MISE_MINIMUM_RELEASE_AGE=0
mise use -g --quiet "claude" || exit 1
exec mise x "claude" -- "claude" "$@"
```

`mise x claude -- claude` resolves the trailing `claude` through PATH. When
**both** of these hold, it resolves back to the same shim, which `exec`s itself
in the same PID forever (34% CPU, `mise use -g` re-run and
`~/.config/mise/config.toml` rewritten on every iteration, nothing ever drawn):

1. `~/.local/bin` precedes `~/.local/share/mise/shims` (and the mise install
   dirs) in PATH, and
2. the mise session variables `__MISE_ORIG_PATH` / `__MISE_SESSION` /
   `__MISE_DIFF` are **absent** (with them present, `mise x` rebuilds PATH from
   the original order and finds the real binary — which is why the same shim
   works from every interactive shell and from inside an agent's Bash tool).

**tmux supplies exactly that combination.** `tmux new-window` / `split-window`
copies **only `PATH`** from the *client process* that issued the command into
the new pane's environment (marker test: `PATH=/usr/bin:/x tmux new-window -d
'echo $PATH > f'` → `/usr/bin:/x`; it even overrides `-e PATH=…`) and drops
every `__MISE_*` variable. So the pane's PATH order is whatever the spawning
process happened to have. Prompt-driven interactive shells end up healthy
(mise's prompt hook reorders PATH), but any shell that sourced
`~/.bash_profile`/`~/.bashrc` *without* a prompt keeps `~/.local/bin` first —
on this machine that is Claude Code's Bash-tool snapshot, `bash -lc`, and
anything launched from them (the user's rc files prepend `~/.local/bin`; Omarchy's
own `default/bash/envs` only *appends* it).

### Evidence that the failing panes took this path
- mise's remote-versions cache for claude (`~/.cache/mise/claude/remote_versions-*.msgpack.z`,
  plus `2.1.25x/bin_paths-*`) was rewritten at **13:59:26**, one second after the
  first failed spawn. `mise use -g claude` produces exactly that fingerprint
  (verified by re-running it with a forced-stale cache); the healthy mise-shim
  path (`claude` → `~/.local/share/mise/shims/claude`) never refreshes the cache
  and never touches the network, even with a forced-stale cache or an empty /
  missing config. No agent transcript shows a `claude`/`gh`/`mise` invocation in
  that minute.
- The Omarchy-shim path additionally blocks up to **~27s** on a stalled network
  (`fetch_remote_versions_timeout = 20s`, measured with a black-holed proxy) —
  a second way to get a long blank pane even when the recursion does not bite.

### What was ruled out
SSH env, `BASH_ENV`, systemd user-manager env, package upgrades, git/worktree
activity, file writes in the repo or `~/.aitask` during the window, config churn
(mise shim resolves fine with an empty or missing config), a new claude release
(installs happened 08:10/08:13, spawns worked after), Claude Code auth/session
state. The live companion → companion → companion spawn chain boots Claude
Code in ~10–14s every time.

### Unresolved
Every TUI alive after the failure has the healthy PATH order, and the user
reports pressing the key in a companion minimonitor. The specific client that
held the bad order at 13:59 died with the failed windows and could not be
identified. The task should therefore make spawns **independent of the caller's
PATH** rather than chase that client.

## Reproduction

```bash
# looping (bad order, no __MISE_*): pane stays blank, pane_pid is bash running the shim
PATH="$HOME/.local/bin:/usr/share/omarchy/bin:$HOME/.local/share/mise/shims:/usr/bin" \
  tmux new-window -d -n repro -c "$PWD" 'ait codeagent invoke explore'
sleep 10; tmux list-panes -t repro -F '#{pane_pid}' | xargs -I{} tr '\0' ' ' < /proc/{}/cmdline
# -> /bin/bash /home/ddt/.local/bin/claude --model … ; children: mise use -g --quiet claude (new pid each second)

# control (healthy order): Claude Code banner within ~10s
PATH="/usr/share/omarchy/bin:$HOME/.local/share/mise/shims:$HOME/.local/bin:/usr/bin" \
  tmux new-window -d -n ctrl -c "$PWD" 'ait codeagent invoke explore'

# the resolution itself, without tmux
env -i PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:/usr/bin" HOME=$HOME \
  mise x claude -- sh -c 'command -v claude'      # -> ~/.local/bin/claude  (recursion)
env -i PATH="$HOME/.local/share/mise/shims:$HOME/.local/bin:/usr/bin" HOME=$HOME \
  mise x claude -- sh -c 'command -v claude'      # -> …/mise/installs/claude/latest/claude
```

## Fix design

1. **Gateway-level (primary, covers every spawn).** In `lib/tmux_exec.py`
   (`TmuxClient.spawn` / `run` / `run_via_control` for `new-window` and
   `split-window`) hand the tmux *client* subprocess a deliberate PATH instead
   of inheriting the caller's: e.g. the server's global PATH
   (`tmux show-environment -g PATH`) or the caller's PATH re-ordered so mise's
   shims dir precedes `~/.local/bin`. Because tmux copies the client's PATH into
   the pane, this makes every pane's PATH independent of whoever spawned it.
   Mirror in `lib/tmux_exec.sh` (`ait_tmux`) for the shell call sites
   (`tmux_bootstrap.sh`, `aitask_ide.sh`). Note the control-mode channel: a
   command sent through the persistent `tmux -C attach` client uses *that*
   client's PATH, captured at attach — decide whether to sanitize at attach or
   route spawns through a fresh subprocess.
2. **Belt-and-braces in `aitask_codeagent.sh cmd_invoke`** (before `exec`):
   if the resolved agent binary is a shell script that re-invokes `mise x`
   (the Omarchy shim shape) *and* `mise which <agent>` resolves, exec the mise
   result (or the mise shim) directly, or at minimum fail loudly with a hint
   instead of looping. Remember the `e` path spawns `claude --model … /aitask-pick N`
   directly (no `codeagent invoke`), so (1) is still required.
3. Tests: a unit test on the gateway that the tmux client argv/env carries the
   sanitized PATH; a shell test that drives the real `new-window` with the bad
   order and asserts the pane's `claude` resolves to mise (or that the guard
   in (2) fires). Do not rely on the omarchy shim being installed — synthesize
   a recursing shim in a temp `bin/` for the test.
4. Docs: a short note in `aidocs/framework/tmux_gateway.md` (PATH is copied
   from the client; the gateway owns the sanitized value) and a troubleshooting
   line in the website TUI-switcher / codeagent docs.

Consider reporting the shim recursion upstream to Omarchy as well (the shim
should exec `$(mise which claude)` rather than re-resolving by name).

## Acceptance criteria
- With the bad PATH order in the spawning process and no `__MISE_*` vars, `x`/`e`
  in the switcher (and `maybe_spawn_minimonitor`, `monitor_core` kill/spawn,
  `minimonitor_app` new-window, `tmux_bootstrap.sh`, `aitask_ide.sh`) still
  produce a pane whose agent process is the real `claude` binary within the
  normal boot time.
- The healthy-order behaviour is unchanged (pane PATH still starts with
  `~/.aitask/bin` as today, mise install dirs still resolve).
- `tests/test_no_raw_tmux.sh` still passes — no new raw `tmux` call sites.
