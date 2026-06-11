---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [tui, codeagent, tmux]
created_at: 2026-06-11 12:26
updated_at: 2026-06-11 12:26
---

## Problem

When a framework TUI is run **outside tmux** and spawns a code agent into a
new terminal window (e.g. `ait board` → pick a task → `ait pick` launches a
code agent), quitting the TUI **kills the spawned agent**. The agent should
outlive the TUI that launched it. This also affects other TUIs that spawn
agents/processes (codebrowser, syncer, etc.). It is mostly masked today
because we usually run the TUIs inside tmux, but it is a real, annoying bug
in the non-tmux path.

## Root cause

The terminal-spawn path uses a bare `subprocess.Popen([terminal, "--", ...])`
with **no `start_new_session=True` / no `setsid`**, so the spawned terminal
emulator (and the agent inside it) stays in the TUI's process group / session
and shares its controlling terminal. When the TUI exits, the child is torn
down with it.

By contrast, the **tmux launch path survives precisely because it detaches**:
`.aitask-scripts/lib/tmux_exec.py` wraps new-session creation in
`systemd-run --user --slice=session.slice --property=KillMode=none`
(falling back to `setsid`). The terminal path has no equivalent detachment.

Confirmed: `grep` for `start_new_session`/`setsid` across all the spawn-site
files returns nothing.

## Affected spawn sites (terminal-emulator path — no detachment)

- `.aitask-scripts/board/aitask_board.py:4718` — pick (code agent)
- `.aitask-scripts/board/aitask_board.py:4762` — create task
- `.aitask-scripts/board/aitask_board.py:4775` — brainstorm TUI
- `.aitask-scripts/codebrowser/codebrowser_app.py:1425` — explain/qa agent
- `.aitask-scripts/codebrowser/codebrowser_app.py:1503` — create task
- `.aitask-scripts/codebrowser/history_screen.py:420` — qa agent
- `.aitask-scripts/lib/sync_action_runner.py:254` — syncer

## Related (also undetached — different shape, no terminal wrapper)

These spawn directly into the parent's process group and would die with the
TUI even though they are not terminal-wrapped:

- `.aitask-scripts/monitor/monitor_app.py:1569` — `ait crew logview`
- `.aitask-scripts/brainstorm/brainstorm_app.py:3847` — `ait crew logview`

(Decide during planning whether to fix these in the same pass — they share the
root cause: no session detachment.)

## Suggested fix

Centralize the detachment rather than patching six call sites independently:

- Add a small `spawn_in_terminal(...)` helper next to `find_terminal()` in
  `.aitask-scripts/lib/agent_launch_utils.py` that does
  `subprocess.Popen([terminal, "--", *cmd], start_new_session=True, ...)`.
  (`start_new_session=True` is the POSIX `setsid` equivalent — makes the child
  a new session/process-group leader, detached from the TUI's controlling tty.)
- Route all the terminal-spawn sites above through the helper.
- Note: `codebrowser/` has its own `find_terminal()` in
  `codebrowser/agent_utils.py`; ensure the codebrowser sites get the same
  detachment (either import the shared helper or add `start_new_session=True`
  locally — prefer sharing).
- Consider whether the two `crew logview` spawns should also gain
  `start_new_session=True`.

## Verification

- Run a TUI **outside tmux** (e.g. `ait board`), spawn an agent, quit the TUI,
  and confirm the agent process survives (e.g. visible in `ps`, terminal stays
  open). Re-confirm the tmux path is unaffected.
- The `else:` (suspend) branches that run inline when no terminal is found are
  expected to still block/exit with the TUI — that is the intended fallback,
  not part of this fix.
