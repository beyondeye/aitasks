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

## Final Implementation Notes

- **Actual work done:**
  - `aitask_crew_addwork.sh`: added `LAUNCH_MODE="headless"` default near
    other defaults, `--launch-mode` arg parsing, post-parse validation
    (`^(headless|interactive)$`), `launch_mode: ${LAUNCH_MODE}` line in the
    `STATUS_CONTENT` heredoc (placed right after `group:`), and a help-text
    entry.
  - `agentcrew_runner.py`: added `import shlex` and a new
    `from lib.agent_launch_utils import (...)` block; resolved
    `launch_mode` immediately after `type_config` is loaded
    (per-agent → per-type → "headless"); split `launch_agent()` into
    headless / interactive / unknown branches inside a single
    `try/except OSError`. Headless branch is byte-identical in behavior to
    the previous code (Popen with redirected log_fh, same banner writes,
    same heartbeat write, same `LAUNCHED:` print). Interactive branch:
    tmux preferred (window `agent-<name>`, `pipe-pane` mirroring,
    `maybe_spawn_minimonitor`), terminal fallback (`find_terminal`,
    no log mirroring, WARN logged), Error path with the documented
    message if neither works.
  - `tests/test_launch_mode_field.sh`: new — 5 cases, 7 assertions, all
    PASS. Covers default, explicit headless, interactive, invalid value,
    missing value.
  - `tests/test_crew_runner.sh`: added one line so `setup_test_repo()`
    also copies `lib/agent_launch_utils.py` into the sandbox — without it
    the runner import fails at module load.

- **Deviations from plan:**
  - Plan suggested an example import like `from .aitask_scripts.lib.agent_launch_utils import …` with an "adjust as needed" note. The correct form is `from lib.agent_launch_utils import …` — `agentcrew_runner.py` line 15 already inserts `.aitask-scripts/` into `sys.path`, so `lib.*` is the right import root. Verified with a standalone `python3 -c` before editing.
  - Plan had the `try/except` wrap both branches; in the actual code the headless branch starts inside `try:` directly so the existing OSError handler at the bottom catches Popen failures from both branches without code duplication. Same effect, slightly cleaner layout.
  - Added an `else` clause logging "Unknown launch_mode" and returning, instead of letting it silently fall through.

- **Issues encountered:**
  - First run of `tests/test_crew_runner.sh` hung at Test 2: the runner module failed to import inside the sandbox because `lib/agent_launch_utils.py` wasn't being copied. The Python error was being swallowed by `>/dev/null 2>&1` higher up the call chain — visible only when removing redirection. Fix was the one-line `cp` addition to the test fixture.

- **Key decisions:**
  - Pid stored in interactive branch is the wrapper pid (tmux CLI or terminal launcher), not the Claude Code pid. This is documented inline as a comment, and is safe because runner liveness checks use heartbeat files.
  - Log mirroring via `tmux pipe-pane` happens after `launch_in_tmux` returns success; `pipe-pane` failures emit a WARN but don't abort the launch (the agent is already running at that point).
  - Standalone-terminal fallback explicitly logs that monitor integration is lost (no log file mirroring).

- **Verification results:**
  - `shellcheck .aitask-scripts/aitask_crew_addwork.sh`: 3 pre-existing
    informational issues (SC1091 x2, SC2001), no new ones.
  - `shellcheck tests/test_launch_mode_field.sh`: clean.
  - `python3 -m py_compile agentcrew_runner.py`: OK.
  - `bash tests/test_launch_mode_field.sh`: 7/7 PASS.
  - `bash tests/test_crew_init.sh`: 32/32 PASS (no regressions).
  - `bash tests/test_crew_runner.sh`: 31/31 PASS (no regressions).
  - Live tmux/terminal verification (manual steps in plan §4-§6) was not
    performed in this session — those need a live tmux session and are
    documented for the human reviewer.

- **Notes for sibling tasks:**
  - The validation regex in `aitask_crew_addwork.sh` is `^(headless|interactive)$`. **t461_2 (setmode CLI)** must extend this set in lock-step if it ever introduces a new mode (e.g., `monitored`).
  - The yaml field name is `launch_mode` (snake_case), located between `group:` and `status:` in `_status.yaml`. **t461_3 (wizard toggle)** should pass `--launch-mode` through `brainstorm_crew._run_addwork()` rather than writing the field directly, so the addwork validator catches typos.
  - `type_config.get("launch_mode")` is the slot **t461_5 (per-type defaults)** fills. The resolution chain already prefers per-agent yaml over per-type, so per-type acts as a fallback default — exactly what t461_5 needs.
  - The pipe-pane mirror writes the **raw tmux pane output** (ANSI + cursor codes) to `<name>_log.txt`. **t461_6 (log viewer)** must therefore render ANSI; piping through `cat`/`less -R` will not be sufficient.
  - Stored `pid` for interactive agents is the tmux CLI / terminal wrapper pid, not the Claude Code pid. Anything that wants to introspect the actual agent (e.g., a future "attach" command) needs to walk the tmux pane, not `proc.pid`.
