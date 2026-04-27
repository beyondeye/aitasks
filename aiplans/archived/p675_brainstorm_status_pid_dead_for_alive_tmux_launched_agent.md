---
Task: t675_brainstorm_status_pid_dead_for_alive_tmux_launched_agent.md
Base branch: main
plan_verified: []
---

# Plan: Fix recorded PID for tmux-launched agents (t675)

## Context

In the `ait brainstorm` Status tab an agent that is **alive and actively
heartbeating** (e.g. `initializer_bootstrap` looping
`ait crew status … heartbeat && … set --progress 20`) is rendered with two
contradictory annotations:

- "Ungrouped Agents": `initializer_bootstrap  Running` (fresh heartbeat)
- "Running Processes": `initializer_bootstrap  PID:34862 …  DEAD`

Both displays are honest readers of `<agent>_status.yaml`. The lie is in the
recorded `pid` field. Live evidence: `_status.yaml` records PID `34862` (a
dead `tmux new-window` launcher); the actual `claude` process running the
agent is PID `34863` inside tmux pane `%6`.

**Root cause:** `launch_in_tmux()` in
`.aitask-scripts/lib/agent_launch_utils.py:366-420` returns the
`subprocess.Popen` object for the short-lived `tmux new-window` /
`new-session` / `split-window` *launcher*, not the agent process running
inside the spawned pane. `agentcrew_runner.py:625` then writes
`proc.pid` (the dead launcher) into `<agent>_status.yaml.pid`. Heartbeats
never update this field. `sync_stale_processes()` only marks `Error` and
won't run anyway while the runner is alive.

This affects **every interactive (tmux-launched) agent**, not just
`initializer_bootstrap` — long-lived initializer made it visible.

**Intended outcome:** the PID stored in `<agent>_status.yaml` is the PID
of the actual agent process inside the tmux pane, alive for as long as
the agent is alive. The brainstorm Status tab stops showing `DEAD` for
healthy agents.

## Approach

Capture the pane's process PID at launch time using tmux's own
`#{pane_pid}` formatter — the canonical, race-free way to ask tmux which
PID it just fork-exec'd. Two mechanisms:

- For `new-window` / `split-window`: add `-P -F "#{pane_pid}"`. tmux prints
  the pane pid to stdout when the command is created.
- For `new-session`: `new-session -d` doesn't accept `-P`. After the
  session is created, query `tmux list-panes -t =SESS:WIN -F "#{pane_pid}"`
  on the freshly created pane.

Change `launch_in_tmux()`'s return contract from
`(subprocess.Popen, str | None)` to `(int | None, str | None)` — the
first element is now the captured pane pid. The 9 existing TUI callers
already use `_, err = launch_in_tmux(...)` and ignore the first value, so
this is a non-breaking rename for them. The single meaningful consumer
(`agentcrew_runner._launch_interactive`) updates to use the int directly.

Heartbeat-side PID self-correction (originally listed as Fix candidate 2)
is **deliberately out of scope**: it is unnecessary once launch-time
capture is correct, and the heartbeat caller is a wrapper bash process
(`ait crew status heartbeat`), not the agent itself, so capturing
`os.getpid()` there would not yield the agent's PID without additional
plumbing.

## Files to modify

### 1. `.aitask-scripts/lib/agent_launch_utils.py`

Function: `launch_in_tmux()` (lines 366–420).

Change the signature:

```python
def launch_in_tmux(command: str, config: TmuxLaunchConfig) -> tuple[int | None, str | None]:
    """Launch a command in tmux according to the given config.

    Returns (pane_pid, error). pane_pid is the PID of the process tmux
    fork-exec'd inside the spawned pane (the agent process), or None if
    the launch succeeded but the pid could not be captured. error is None
    on success, otherwise a human-readable message describing the tmux
    failure.
    """
```

Per-branch changes:

- **`new_session=True` (lines 372–390):** keep the existing
  `subprocess.Popen` + `proc.wait()` of `tmux new-session -d …`; on
  success, query the new pane's pid:
  ```python
  pane_pid = _query_first_pane_pid(config.session, config.window)
  ```
  Return `(pane_pid, None)`. The `subprocess.Popen` to `tmux switch-client`
  stays unchanged (it's only used for client switching, not pid capture).

- **`new_window=True` (lines 391–403):** insert `-P -F "#{pane_pid}"` into
  `tmux_cmd`, switch from `subprocess.Popen + wait` to `subprocess.run`,
  parse stdout:
  ```python
  tmux_cmd = [
      "tmux", "new-window",
      "-P", "-F", "#{pane_pid}",
      "-t", tmux_window_target(config.session, ""),
      "-n", config.window,
      *cwd_args,
      command,
  ]
  result = subprocess.run(tmux_cmd, capture_output=True, text=True, timeout=5)
  if result.returncode != 0:
      return None, f"tmux new-window failed: {result.stderr.strip()}"
  return _parse_pane_pid(result.stdout), None
  ```

- **Split-window (lines 404–420):** same pattern as `new_window`. Keep the
  existing `subprocess.Popen(["tmux", "select-window", …])` call after
  parsing the pane pid.

Add two private helpers near the top of the file (or inside
`launch_in_tmux`'s module scope):

```python
def _parse_pane_pid(stdout: str) -> int | None:
    """Parse the first line of tmux -P -F output as an int pid, or None."""
    line = stdout.strip().splitlines()[0] if stdout.strip() else ""
    try:
        return int(line) if line else None
    except ValueError:
        return None


def _query_first_pane_pid(session: str, window: str) -> int | None:
    """Query the first pane's pid in a freshly created session/window."""
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-t", tmux_window_target(session, window),
             "-F", "#{pane_pid}"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    return _parse_pane_pid(result.stdout)
```

### 2. `.aitask-scripts/agentcrew/agentcrew_runner.py`

Switch the launcher contract from `subprocess.Popen` to `int | None` (pid).

- **`_launch_headless()` (lines 403–417):** change the trailing
  `return proc` to `return proc.pid`. Leave `_log_handles[ctx.name] = log_fh`
  unchanged. The Popen for headless is the actual agent process, so its
  `.pid` is already correct.

- **`_launch_interactive()` (lines 420–476):**
  - Rename the `proc, err = launch_in_tmux(...)` (line 437) to
    `pane_pid, err = launch_in_tmux(...)`.
  - Drop the local `proc: subprocess.Popen | None = None` declaration; use
    `pane_pid: int | None = None`.
  - In the standalone-terminal fallback (lines 461–469), keep the
    `subprocess.Popen([term, "-e", ...])` call but also extract its pid:
    `pane_pid = proc.pid`. Note in a 1-line code comment that this fallback
    captures the terminal emulator's pid (a known limitation distinct from
    the tmux bug — flagged in Final Implementation Notes as a separate
    follow-up candidate, NOT fixed here).
  - Change the function's return type annotation and trailing `return proc`
    to `return pane_pid` (returning `int | None`).

- **`LAUNCHERS` registry (line 493):** update the type annotation:
  ```python
  LAUNCHERS: dict[str, Callable[[LaunchContext], int | None]] = {…}
  ```

- **`launch_agent()` call site (lines 608–629):**
  - Rename `proc = launcher(ctx)` (line 609) to `pid = launcher(ctx)`.
  - Lines 625–629 become:
    ```python
    if pid is None:
        log(f"WARN: Could not capture pid for agent '{name}' — "
            f"writing 0 (process tracking will be degraded)", batch)
        pid = 0
    update_yaml_field(status_file, "pid", pid)
    agents[name]["pid"] = pid
    update_yaml_field(alive_path, "last_heartbeat", now_utc())
    if batch:
        print(f"LAUNCHED:{name}:{pid}")
    ```
  - The `OSError as e:` branch (line 617) currently catches errors from
    `subprocess.Popen`. The launcher functions still raise OSError for
    legitimate launch failures, so no change there.

### 3. TUI callers (no functional change)

Nine call sites in `aitask_board.py`, `monitor_app.py`, `codebrowser_app.py`,
`history_screen.py` already use `_, err = launch_in_tmux(...)`. They ignore
the first value. No code change required — the type annotation tightens
from "Popen" to "int | None" but the discard pattern is the same.

### 4. Tests

Add `tests/test_launch_in_tmux_pane_pid.py` (Python, runs under
`bash tests/run_python_tests.sh` if present, or directly via
`python3 tests/test_launch_in_tmux_pane_pid.py`):

- Unit-level: monkey-patch `subprocess.run` to simulate `tmux new-window
  -P -F "#{pane_pid}"` returning a pid string; assert `launch_in_tmux`
  returns `(int, None)`.
- Empty stdout → `(None, None)` (launch succeeded, pid uncapturable).
- Non-zero return → `(None, "tmux new-window failed: …")`.
- Same three for split-window branch.
- For `new_session`: simulate the followup `tmux list-panes` call.

Optionally a tmux-gated integration test (skipped if `shutil.which("tmux")`
is None) that:
1. spawns `sleep 60` in a fresh `_test_aitask_pid_<rand>` window via
   `launch_in_tmux`,
2. asserts the returned pid is alive (`os.kill(pid, 0)` succeeds),
3. `tmux kill-window` cleanup.

### 5. Manual end-to-end verification

1. Start a fresh brainstorm session that launches `initializer_bootstrap`.
2. While the agent is heartbeating, open `ait brainstorm` Status tab.
3. Confirm the "Running Processes" row for `initializer_bootstrap`:
   - shows a non-DEAD green/yellow dot
   - `PID:<n>` matches a process visible in
     `tmux list-panes -t =aitasks -a -F "#{pane_id} #{pane_pid} #{pane_current_command}"`
   - `os.kill(<n>, 0)` succeeds: `python3 -c "import os; os.kill(<n>,0)"`.
4. Confirm the "Ungrouped Agents" row continues to show `Running` with
   fresh heartbeat age — the existing display should be unchanged.
5. Regression: pick a task via `/aitask-pick` from the board TUI (which
   calls `launch_in_tmux` for the codeagent window) and confirm the agent
   spawns correctly.

## Out of scope

- **Heartbeat-side PID self-correction.** Once launch-time capture is
  correct, redundant. The heartbeat caller is a bash wrapper, not the
  agent, so `os.getpid()` there would be wrong without extra plumbing.
- **Standalone-terminal fallback PID.** The `_launch_interactive` fallback
  for environments without tmux records the terminal emulator's pid (same
  class of bug). Documented in Final Implementation Notes as a follow-up
  candidate; not fixed here because (a) different code path, (b) the
  user's bug is specifically about tmux launches, (c) the fix shape
  differs (no `pane_pid` equivalent for terminal emulators).
- **Backfill of currently-running brainstorm sessions.** The fix only
  affects newly launched agents. Sessions started before the fix retain
  their wrong PID until restarted — acceptable given the bug only
  affects display, not correctness, and the fix corrects all future
  launches.

## Critical files

- `.aitask-scripts/lib/agent_launch_utils.py` (lines 366–420) — primary fix
- `.aitask-scripts/agentcrew/agentcrew_runner.py` (lines 403, 420–476,
  493, 608–629) — consumer update
- `tests/test_launch_in_tmux_pane_pid.py` (new) — coverage

## Verification (one-liner reproducer of the bug, must fail before the
fix and pass after)

After implementing, in a brainstorm session with at least one alive agent:

```bash
crew_id="$(ls .aitask-crews/ | head -1)"
wt=".aitask-crews/$crew_id"
for f in "$wt"/*_status.yaml; do
  agent="$(basename "$f" _status.yaml)"
  pid="$(grep '^pid:' "$f" | awk '{print $2}')"
  status="$(grep '^status:' "$f" | awk '{print $2}')"
  [ "$status" = "Running" ] || continue
  if kill -0 "$pid" 2>/dev/null; then
    echo "OK $agent pid=$pid alive"
  else
    echo "FAIL $agent pid=$pid DEAD"
  fi
done
```

Before the fix: at least one `FAIL …` line for tmux-launched agents.
After the fix: every Running agent reports `OK`.

## Step 9 (post-implementation) reminder

After commit, archive via the standard task-workflow Step 9 path:
`./.aitask-scripts/aitask_archive.sh 675`. No worktree to clean up
(profile `fast`, `create_worktree: false`).

## Final Implementation Notes

- **Actual work done:**
  - `launch_in_tmux()` in `.aitask-scripts/lib/agent_launch_utils.py` now
    returns `(int | None, str | None)` instead of `(subprocess.Popen, str
    | None)`. The first element is the pane's PID (the agent process tmux
    fork-exec'd) — captured via `tmux -P -F "#{pane_pid}"` for `new-window`
    / `split-window`, and via a follow-up `tmux list-panes` query for
    `new-session` (which doesn't accept `-P`).
  - Added `_parse_pane_pid()` and `_query_first_pane_pid()` helpers.
  - In `agentcrew_runner.py`, the `LAUNCHERS` registry signature changed
    to `Callable[[LaunchContext], int | None]`. `_launch_headless` returns
    `proc.pid`; `_launch_interactive` returns the pane pid from
    `launch_in_tmux`. `launch_agent()` writes the captured pid into
    `_status.yaml`, with a `WARN` log and `pid=0` fallback if capture
    fails.
  - 9 TUI callsites in `aitask_board.py`, `monitor_app.py`,
    `codebrowser_app.py`, `history_screen.py` were unchanged because they
    already use `_, err = launch_in_tmux(...)` and ignore the first
    value; only the discarded variable's *type* tightened from `Popen`
    to `int | None`.
  - New test file `tests/test_launch_in_tmux_pane_pid.py` (17 tests, 15
    unit + 2 live-tmux integration). Unit tests assert: argv shape
    contains `-P -F "#{pane_pid}"`, success returns `(int, None)`, empty
    stdout returns `(None, None)`, non-zero return yields a `tmux …
    failed: …` error message — for all three branches (`new-window`,
    `split-window`, `new-session`). Integration tests spawn `sleep 30` in
    a fresh test session/window and verify the returned pid is alive
    via `os.kill(pid, 0)`.
  - `tests/test_multi_session_monitor.sh` Tier 1o updated to patch both
    `subprocess.Popen` and `subprocess.run` (since post-t675 the
    `new-window` and `split-window` calls route through `subprocess.run`).
    The same `-c <cwd>` property is asserted — 43/43 still pass.

- **Deviations from plan:** none of substance. The standalone-terminal
  fallback PID handling shipped exactly as planned (capture
  `proc.pid` of the terminal emulator, with a 1-line code comment
  flagging it as a known limitation distinct from the tmux bug —
  candidate for a separate follow-up task if the fallback path becomes
  load-bearing).

- **Issues encountered:**
  - The existing `tests/test_multi_session_monitor.sh` Tier 1o test
    initially failed because it patched only `subprocess.Popen`. Switched
    the test to patch both `Popen` and `run`. This was anticipated as a
    risk in the plan ("9 TUI callers… ignore the first value… no code
    change required") but the plan didn't enumerate `tests/` as a
    callsite — the real fix counted four files modified, not three.

- **Key decisions:**
  - **Return-type change vs new-function approach:** chose to repurpose
    `launch_in_tmux`'s return tuple rather than introduce a parallel
    `launch_agent_in_tmux()` function. Justification: 9 of 10 callers
    already discard the first tuple element, so the contract change is
    cosmetic for them and only the runner needs real updates. A parallel
    function would have left the original misleading return type in
    place, inviting future bugs.
  - **No heartbeat-side PID self-correction.** Originally listed in the
    task description as Fix candidate 2; deliberately left out because
    (a) launch-time capture eliminates the need; (b) the heartbeat
    caller is `bash` running `ait crew status heartbeat`, not the agent
    — so `os.getpid()` there would be wrong without explicit plumbing
    (passing `--pid $$` from the agent process, which itself is hard to
    identify reliably from inside `claude`/`gemini`/etc.).
  - **`subprocess.run` for new-window / split-window, but
    `subprocess.Popen` for new-session.** The two branches use different
    mechanisms because tmux's `new-session -d` does not accept `-P`. Kept
    the existing Popen+wait pattern there to minimize surface change and
    preserve the existing stderr-capture behavior.

- **Upstream defects identified:** None.

  (One adjacent issue is documented in-code only: the
  standalone-terminal fallback in `_launch_interactive` records the
  terminal emulator's pid rather than the agent process's. Same class of
  bug as the original tmux issue but a much smaller blast radius —
  fallback path only fires when tmux is absent. Tagged with an in-code
  comment in `agentcrew_runner.py:_launch_interactive`. Not surfaced as
  an upstream-defect bullet because it does not seed the t675 symptom —
  it is a separate, known-tolerable limitation. Fix would be its own
  task if/when needed.)

