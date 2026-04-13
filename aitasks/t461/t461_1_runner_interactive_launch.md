---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-13 11:43
updated_at: 2026-04-13 11:55
---

## Context

Parent task t461 adds an "interactive launch" mode for code agents in agentcrew,
so they run inside a tmux window the user can watch and type into (instead of
the current `subprocess.Popen` headless launch). This child task introduces
the schema field and teaches the agentcrew runner to branch on it.

Task 468 already built the reusable tmux helpers in
`.aitask-scripts/lib/agent_launch_utils.py` (`launch_in_tmux`,
`load_tmux_defaults`, `TmuxLaunchConfig`, `maybe_spawn_minimonitor`,
`is_tmux_available`, `find_terminal`). This task wires them into the runner.

## Key Files to Modify

- `.aitask-scripts/agentcrew/agentcrew_runner.py` — `launch_agent()`
  (currently lines ~398-497). This is the only function where code agents
  get spawned for a crew.
- `.aitask-scripts/aitask_crew_addwork.sh` — add a `--launch-mode <mode>`
  flag and write it into the agent `_status.yaml` block (currently around
  lines 160-170 where the yaml block is emitted).

## Reference Files for Patterns

- `.aitask-scripts/lib/agent_launch_utils.py` — read the whole file. It has
  `launch_in_tmux(command, config) -> (proc, err_or_None)`,
  `load_tmux_defaults(project_root) -> dict`, `TmuxLaunchConfig` dataclass,
  `is_tmux_available()`, `get_tmux_sessions()`, `get_tmux_windows(session)`,
  `find_terminal()`, `maybe_spawn_minimonitor(session, window_name)`.
- `.aitask-scripts/board/aitask_board.py` and `.aitask-scripts/lib/agent_command_screen.py` —
  see how the board TUI calls `launch_in_tmux` and wraps commands for the
  standalone-terminal fallback path (format: `[term, "-e", "sh", "-c", cmd_str]`).
- Existing `launch_agent()` body itself — do not change the headless branch.

## Implementation Plan

1. **Resolve effective launch_mode** inside `launch_agent()` after the
   `type_config` is loaded:

   ```python
   launch_mode = (
       agent_data.get("launch_mode")
       or type_config.get("launch_mode")
       or "headless"
   )
   ```

   The per-agent-type default (from `type_config`) is set up by sibling
   task t461_5; keep this resolution ready for it now.

2. **Keep the current headless path unchanged.** All existing behavior
   (Popen, log redirect, heartbeat file write, status transitions) stays
   exactly as it is when `launch_mode == "headless"`.

3. **Add the interactive branch**:

   a. Build the same command list but drop the `-p` flag, passing the
      short prompt as a positional arg so Claude Code opens interactively
      with it as the first user message:

      ```python
      cmd = [ait_cmd, "codeagent", "--agent-string", agent_string,
             "invoke", "raw", short_prompt]
      cmd_str = " ".join(shlex.quote(c) for c in cmd)
      ```

   b. **Preferred path (tmux)** — if `is_tmux_available()`:
      - `from agent_launch_utils import (load_tmux_defaults, TmuxLaunchConfig, launch_in_tmux, get_tmux_sessions, get_tmux_windows, maybe_spawn_minimonitor, is_tmux_available, find_terminal)`
      - `tmux_defaults = load_tmux_defaults(Path(_repo_root))`
      - `session = tmux_defaults["default_session"]`
      - `window_name = f"agent-{name}"`
      - `new_session = session not in get_tmux_sessions()`
      - `config = TmuxLaunchConfig(session=session, window=window_name, new_session=new_session, new_window=True)`
      - `proc, err = launch_in_tmux(cmd_str, config)`
      - If `err is None`: locate the window index via
        `get_tmux_windows(session)`, find the matching `window_name`,
        then call
        `subprocess.run(["tmux", "pipe-pane", "-O", "-o", "-t", f"{session}:{idx}.0", f"cat >> {shlex.quote(log_path)}"], check=False)`.
        Log a WARN on non-zero return but do NOT abort the launch.
      - Then call `maybe_spawn_minimonitor(session, window_name)` so the
        minimonitor split-pane attaches next to the agent window.
      - If `err is not None`, fall through to the terminal path below.

   c. **Fallback path (standalone terminal)** — if tmux is unavailable OR
      `launch_in_tmux` returned an error, call `find_terminal()`. On
      success, spawn with
      `proc = subprocess.Popen([term, "-e", "sh", "-c", cmd_str], cwd=_repo_root or ".")`.
      Log a WARN that monitor integration is lost (no log-file mirroring
      possible in this path — see "Known limitations" below).

   d. **Error path** — if neither tmux nor a terminal is available,
      transition the agent to `Error` with
      `error_message = "Interactive launch requires tmux or a terminal emulator"`
      and return without starting a process.

   e. Store `proc.pid` on the agent (note: this is the tmux CLI / terminal
      wrapper pid, not the Claude Code pid). The runner's liveness check
      uses heartbeat files, not pid liveness, so this caveat is safe.
      Add a short comment noting the distinction.

4. **Update `aitask_crew_addwork.sh`** — add parsing for
   `--launch-mode <headless|interactive>` in the arg-parsing block (around
   lines 60-87). Validate the value, default to `headless` when unset, and
   emit `launch_mode: <value>` into the `_status.yaml` block (around lines
   160-170) alongside `agent_type`, `group`, etc.

5. **Write `tests/test_launch_mode_field.sh`**: a self-contained bash test
   that:
   - Creates a temp crew directory via `./ait crew init`.
   - Runs `./ait crew addwork --batch --launch-mode interactive --crew
     <id> --name test_agent --type explorer --work2do -` with a heredoc
     work file.
   - Asserts the resulting `<agent>_status.yaml` contains
     `launch_mode: interactive` using `grep` + `assert_contains` helper.
   - Repeats without `--launch-mode` and asserts the field is
     `launch_mode: headless` (the default).
   - Follows the existing test helper pattern in `tests/test_*.sh`.

## Known limitations (document in code comments)

- When the standalone-terminal fallback is used, the log file is empty
  because there's no equivalent of `tmux pipe-pane` outside tmux.
- Stored pid is the wrapper pid, not the Claude Code pid. Runner polling
  relies on heartbeat files.

## Verification Steps

1. `shellcheck .aitask-scripts/aitask_crew_addwork.sh` must pass.
2. `bash tests/test_launch_mode_field.sh` must pass.
3. Manual: inside a tmux session named `aitasks`, create a small test
   crew and run the runner against an agent with `launch_mode: interactive`.
   Confirm a window `agent-<name>` appears in the session with Claude Code
   starting, and the log file shows the pipe-pane capture with ANSI codes.
4. Manual: outside tmux, set an agent to `interactive` and run the runner.
   Confirm a standalone terminal opens. (Skip this if no terminal emulator
   is available in the test environment.)
5. Manual: on a system with neither tmux nor a terminal, confirm the
   agent transitions to `Error` with the documented message.
6. Headless regression: an agent with `launch_mode: headless` (or absent)
   must behave exactly as today — Popen, logs to `<name>_log.txt`, no
   tmux window.

## Dependencies

- Sibling t461_5 will add the `type_config.get("launch_mode")` lookup
  data. This task's resolution line is written to accommodate that lookup
  even before t461_5 lands — when the key is missing, it falls back to
  "headless" correctly.
