---
Task: t461_1_runner_interactive_launch.md
Parent Task: aitasks/t461_interactive_override_in_agencrew.md
Sibling Tasks: aitasks/t461/t461_2_*.md, aitasks/t461/t461_3_*.md, aitasks/t461/t461_4_*.md, aitasks/t461/t461_5_*.md, aitasks/t461/t461_6_*.md
Archived Sibling Plans: aiplans/archived/p461/p461_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# p461_1 — Runner interactive-launch path + status-yaml schema

## Goal

Teach `agentcrew_runner.launch_agent()` to branch on a new `launch_mode`
field in the agent status yaml, spawning the agent inside a tmux window
(preferred) or a standalone terminal (fallback) when the value is
`interactive`. Also add the `--launch-mode` flag to `aitask_crew_addwork.sh`
so the field is set at agent creation time.

## Files

### Modified

1. `.aitask-scripts/agentcrew/agentcrew_runner.py`
   - `launch_agent()` (current ~398-497)
2. `.aitask-scripts/aitask_crew_addwork.sh`
   - Arg parsing (~60-87)
   - Status yaml emission (~160-170)

### New

3. `tests/test_launch_mode_field.sh`

## Implementation steps

### 1. `aitask_crew_addwork.sh` — new flag

- Parse `--launch-mode <headless|interactive>`:
  ```bash
  --launch-mode)
      LAUNCH_MODE="$2"; shift 2;;
  ```
- Initialize `LAUNCH_MODE="${LAUNCH_MODE:-headless}"` before the parse
  loop.
- Validate after parsing: `[[ "$LAUNCH_MODE" =~ ^(headless|interactive)$ ]] || die "--launch-mode must be headless or interactive"`.
- Emit the field in the status yaml block:
  ```bash
  cat > "$STATUS_FILE" <<YAML
  agent_name: $AGENT_NAME
  agent_type: $AGENT_TYPE
  group: $GROUP
  launch_mode: $LAUNCH_MODE
  status: Waiting
  depends_on: [$DEPS]
  ...
  YAML
  ```

### 2. `agentcrew_runner.launch_agent()` — mode resolution

Right after `type_config = agent_types_config.get(atype, {})`:

```python
launch_mode = (
    agent_data.get("launch_mode")          # per-agent
    or type_config.get("launch_mode")      # per-type (t461_5)
    or "headless"                           # framework
)
```

### 3. `launch_agent()` — headless branch (unchanged)

All existing code from the `try:` block stays inside
`if launch_mode == "headless":`. No other change.

### 4. `launch_agent()` — interactive branch

Before the try/except, add imports at module top:
```python
import shlex
from pathlib import Path
from .aitask_scripts.lib.agent_launch_utils import (
    is_tmux_available, load_tmux_defaults, launch_in_tmux,
    get_tmux_sessions, get_tmux_windows, maybe_spawn_minimonitor,
    find_terminal, TmuxLaunchConfig,
)
```
(Adjust the import path to match how other modules import from
`.aitask-scripts/lib/`. The `agent_launch_utils.py` file uses plain
module-level imports; mirror that. The project uses an sys.path insert
rather than a package structure.)

Then inside `launch_agent()`, when `launch_mode == "interactive"`:

```python
# Reuse short_prompt/prompt_rel/ait_cmd from the existing setup
cmd = [ait_cmd, "codeagent", "--agent-string", agent_string,
       "invoke", "raw", short_prompt]
cmd_str = " ".join(shlex.quote(c) for c in cmd)

log_path = os.path.join(worktree, f"{name}_log.txt")
launched = False
proc = None

# Preferred: tmux
if is_tmux_available():
    tmux_defaults = load_tmux_defaults(Path(_repo_root or "."))
    session = tmux_defaults["default_session"]
    window_name = f"agent-{name}"
    new_session = session not in get_tmux_sessions()
    config = TmuxLaunchConfig(
        session=session, window=window_name,
        new_session=new_session, new_window=True,
    )
    proc, err = launch_in_tmux(cmd_str, config)
    if err is None:
        launched = True
        # Mirror pane output to log file
        windows = get_tmux_windows(session)
        win_idx = next((idx for idx, n in windows if n == window_name), None)
        if win_idx is not None:
            pp = subprocess.run(
                ["tmux", "pipe-pane", "-O", "-o",
                 "-t", f"{session}:{win_idx}.0",
                 f"cat >> {shlex.quote(log_path)}"],
                capture_output=True, text=True,
            )
            if pp.returncode != 0:
                log(f"WARN: pipe-pane failed for {name}: {pp.stderr}", batch)
        maybe_spawn_minimonitor(session, window_name)
    else:
        log(f"WARN: tmux launch failed for {name}: {err}", batch)

# Fallback: standalone terminal
if not launched:
    term = find_terminal()
    if term is not None:
        log(f"WARN: falling back to standalone terminal ({term}) for {name} — no monitor integration", batch)
        proc = subprocess.Popen(
            [term, "-e", "sh", "-c", cmd_str],
            cwd=_repo_root or ".",
        )
        launched = True

# Error: neither path worked
if not launched:
    err_msg = "Interactive launch requires tmux or a terminal emulator"
    log(f"ERROR: {err_msg} (agent {name})", batch)
    update_yaml_field(status_file, "status", "Error")
    update_yaml_field(status_file, "error_message", err_msg)
    update_yaml_field(status_file, "completed_at", now_utc())
    agents[name]["status"] = "Error"
    return

# Track pid (wrapper pid, not Claude Code pid — heartbeat is authoritative)
update_yaml_field(status_file, "pid", proc.pid)
agents[name]["pid"] = proc.pid
alive_path = os.path.join(worktree, f"{name}_alive.yaml")
update_yaml_field(alive_path, "last_heartbeat", now_utc())
if batch:
    print(f"LAUNCHED:{name}:{proc.pid}")
```

**Important:** wrap the whole headless/interactive branching with a
single `try/except OSError` so both paths share the same error handler
that exists at `launch_agent()`'s current end.

### 5. `tests/test_launch_mode_field.sh`

- Bash test following the pattern of `tests/test_terminal_compat.sh`
  etc. (read one as a template).
- Create temp crew dir under `$TMPDIR` via `./ait crew init --batch`.
- Call `./ait crew addwork --batch --launch-mode interactive
  --crew <id> --name test_agent --type explorer --work2do - <<<'test work'`.
- Grep the resulting `_status.yaml` for `launch_mode: interactive`;
  use the existing `assert_contains` helper.
- Repeat without `--launch-mode`; assert `launch_mode: headless`.
- Print `PASS: test_launch_mode_field` on success.

## Verification

1. `shellcheck .aitask-scripts/aitask_crew_addwork.sh` passes.
2. `bash tests/test_launch_mode_field.sh` passes.
3. Manual: create a one-agent brainstorm crew, mark the agent interactive,
   run the runner from inside a tmux session named `aitasks`. Confirm a
   new window `agent-<name>` spawns Claude Code and the log file fills
   with ANSI-laden output.
4. Regression: an unmarked agent still launches headless.
5. Force the tmux path to fail (move tmux out of PATH), confirm fallback
   to a standalone terminal.
6. Force both to fail (rename all terminals too) and confirm Error
   transition with the documented message.

## Known limitations

- Fallback terminal path does not mirror output to the log file.
- Stored `pid` is the wrapper pid (tmux CLI or terminal wrapper), not the
  Claude Code pid. Runner polling uses heartbeat files, so this is safe.

## Notes for sibling tasks

- **t461_2 (setmode CLI)** mutates the same `launch_mode` yaml field via
  `update_yaml_field`. Keep the validation set in sync if you add a new
  mode.
- **t461_3 (wizard toggle)** consumes the `--launch-mode` flag added here
  via `brainstorm_crew._run_addwork()`.
- **t461_5 (per-type defaults)** fills the `type_config.get("launch_mode")`
  slot the resolution line already reads.
- **t461_6 (log viewer)** renders the ANSI stream produced by `pipe-pane`.
  Any format decisions made here affect the viewer's fidelity.
