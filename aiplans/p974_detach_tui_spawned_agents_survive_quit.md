---
Task: t974_detach_tui_spawned_agents_survive_quit.md
Base branch: main
plan_verified: []
---

# t974 — Detach TUI-spawned agents so they survive TUI quit

## Context

When a framework TUI runs **outside tmux** and spawns a code agent into a new
terminal window (e.g. `ait board` → pick a task → launch the pick agent),
quitting the TUI can **kill the spawned agent**. The agent should outlive the
TUI that launched it. The same gap affects other TUIs that spawn agents
(codebrowser, syncer). It is mostly masked today because we usually run TUIs
inside tmux, but it is a real bug in the non-tmux path.

**Root cause:** the terminal-spawn sites use a bare
`subprocess.Popen([terminal, "--", ...])` with **no `start_new_session=True` /
no `setsid`**, so the spawned terminal (and the agent inside it) stays in the
TUI's session / process group and shares its controlling terminal — when the
TUI exits, the child is torn down with it (SIGHUP on session-leader exit /
foreground-process-group teardown). By contrast the **tmux launch path
survives precisely because it detaches**: `lib/tmux_exec.py` wraps new sessions
in `systemd-run --slice=session.slice` / `setsid`. The terminal path has no
equivalent. Confirmed: `grep` for `start_new_session`/`setsid` across all spawn
files returns nothing.

**Fix:** make each terminal-spawn a new session leader via
`start_new_session=True` (the POSIX `setsid` equivalent — detaches from the
controlling tty, immune to SIGHUP, own process group so Ctrl-C to the TUI is
not forwarded). Centralize the duplicated terminal-spawn pattern into one
shared helper so every TUI gets it consistently.

## Approach

### 1. Add a shared `spawn_in_terminal()` helper

In `.aitask-scripts/lib/agent_launch_utils.py`, next to `find_terminal()`
(~line 105), add:

```python
def spawn_in_terminal(terminal: str, cmd: list[str], **popen_kwargs) -> subprocess.Popen:
    """Spawn `cmd` in a new terminal window, detached from this process.

    Wraps subprocess.Popen with start_new_session=True so the spawned terminal
    (and the agent inside it) becomes a new session / process-group leader. This
    lets the agent outlive the launching TUI even when the TUI is NOT running
    inside tmux (the tmux path already detaches via tmux_exec.py). `cmd` is the
    argv that follows the terminal's `--` separator.
    """
    return subprocess.Popen([terminal, "--", *cmd], start_new_session=True, **popen_kwargs)
```

`subprocess` is already imported in that module.

### 2. Route the 7 terminal-spawn sites through the helper

Each already calls `find_terminal()` from `agent_launch_utils`, so each just
adds `spawn_in_terminal` to that existing import and replaces the bare
`subprocess.Popen([terminal, "--", ...])` line. The `else:`/`with suspend()`
fallback branches (no terminal available → run inline, blocking) are **left
untouched** — running inline and exiting with the TUI is the intended fallback.

| File | Line | New call |
|------|------|----------|
| `board/aitask_board.py` | 4718 | `spawn_in_terminal(terminal, [wrapper, "invoke", "pick", num])` |
| `board/aitask_board.py` | 4762 | `spawn_in_terminal(terminal, [str(CREATE_SCRIPT)])` |
| `board/aitask_board.py` | 4775 | `spawn_in_terminal(terminal, [brainstorm_cmd, task_num])` |
| `codebrowser/codebrowser_app.py` | 1424 | `spawn_in_terminal(terminal, [wrapper, "invoke", operation, arg], cwd=str(self._project_root))` |
| `codebrowser/codebrowser_app.py` | 1503 | `spawn_in_terminal(terminal, cmd, cwd=str(self._project_root))` |
| `codebrowser/history_screen.py` | 419 | `spawn_in_terminal(terminal, [wrapper, "invoke", "qa", task_id], cwd=str(self._project_root))` |
| `lib/sync_action_runner.py` | 254 | `spawn_in_terminal(terminal, ["./ait", "sync"])` |

Imports to extend (all already import `find_terminal` from `agent_launch_utils`):
- `board/aitask_board.py:16` — add `spawn_in_terminal`
- `codebrowser/codebrowser_app.py:32` — add `spawn_in_terminal` (alongside `find_terminal as _find_terminal`)
- `codebrowser/history_screen.py:12` — add `spawn_in_terminal`
- `lib/sync_action_runner.py:53` — add `spawn_in_terminal`

### 3. Detach the two `crew logview` spawns (different shape — no terminal wrapper)

These spawn `./ait crew logview` directly (not terminal-wrapped), so they do
**not** go through the helper — just add the same flag inline:

- `monitor/monitor_app.py:1569` — add `start_new_session=True` to the `Popen(...)`
- `brainstorm/brainstorm_app.py:3847` — add `start_new_session=True` to the `Popen(...)`

### 4. Test

Add `tests/test_spawn_in_terminal.py` modeled on
`tests/test_launch_in_tmux_pane_pid.py` (insert `LIB_DIR` on `sys.path`,
`import agent_launch_utils`, patch `subprocess.Popen`). Assert:
- `spawn_in_terminal("alacritty", ["./ait", "sync"])` calls `subprocess.Popen`
  with `start_new_session=True`.
- The argv passed is `["alacritty", "--", "./ait", "sync"]`.
- Extra `**popen_kwargs` (e.g. `cwd=...`) are forwarded through.

## Scope notes / rejected

- **`codebrowser/agent_utils.py::find_terminal` is now dead code** — both
  codebrowser consumers import `find_terminal` from `agent_launch_utils`
  instead. Not removed here (out of scope); recorded as an upstream-defect note
  at commit time.
- **Not unifying the two `find_terminal()` copies** — orthogonal to this fix;
  would widen blast radius for no behavior gain.
- **Not touching the `suspend()` inline fallbacks** — they intentionally block
  and exit with the TUI when no terminal emulator exists.

## Verification

- `python3 tests/test_spawn_in_terminal.py` (or `bash`-run per repo convention) passes.
- `python3 -c "import ast,sys; [ast.parse(open(f).read()) for f in sys.argv[1:]]" .aitask-scripts/lib/agent_launch_utils.py .aitask-scripts/board/aitask_board.py .aitask-scripts/codebrowser/codebrowser_app.py .aitask-scripts/codebrowser/history_screen.py .aitask-scripts/lib/sync_action_runner.py .aitask-scripts/monitor/monitor_app.py .aitask-scripts/brainstorm/brainstorm_app.py` — all parse.
- Re-run a relevant existing suite (e.g. `bash tests/test_board_view_filter.py` or the launch-in-tmux test) to confirm no import regressions.
- **Manual (outside tmux):** run `ait board` in a plain terminal, pick a task to
  spawn an agent, quit the board, and confirm the agent process survives (visible
  in `ps`, its terminal stays open). Confirm the in-tmux path is unaffected.

Cleanup / archival per **Step 9 (Post-Implementation)** of the task workflow.

## Risk

### Code-health risk: low
- Additive shared helper + mechanical, pattern-identical edits across 6 files; reduces duplication rather than adding abstraction debt. `start_new_session=True` is a well-understood POSIX primitive with no behavior change beyond the intended detachment. · severity: low · → mitigation: none
- Moderate blast radius (board, codebrowser ×2, syncer, monitor, brainstorm) but each site is a single-line, low-risk change covered by a syntax-parse check and the new unit test. · severity: low · → mitigation: none

### Goal-achievement risk: low
- The fix targets the root cause directly and is the standard remedy; residual uncertainty is only whether the user's specific environment exhibited an additional kill path, which the manual outside-tmux verification confirms. · severity: low · → mitigation: covered by manual verification step
