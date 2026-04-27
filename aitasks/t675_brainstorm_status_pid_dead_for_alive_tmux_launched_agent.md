---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [ait_brainstorm, agentcrew]
created_at: 2026-04-27 16:40
updated_at: 2026-04-27 16:40
---

## Symptom

In the `ait brainstorm` Status tab, an agent that is **alive and actively
heartbeating** is rendered with two contradictory annotations:

- "Ungrouped Agents" section: `initializer_bootstrap  Running` (with a fresh
  heartbeat age)
- "Running Processes" section: `initializer_bootstrap  PID:34862 …  DEAD`

Concrete repro (live session): brainstorm-635, agent `initializer_bootstrap`
is in a normal heartbeat loop running

```
ait crew status --crew brainstorm-635 --agent initializer_bootstrap heartbeat \
  && ait crew status --crew brainstorm-635 --agent initializer_bootstrap set --progress 20
```

The recorded PID 34862 is dead. The actual `claude` process executing the
agent is PID 34863 inside tmux pane `%6`. So heartbeats are real, status is
genuinely `Running`, but the recorded `pid` field is wrong.

## Root cause

The bug is structural and affects **every interactive (tmux-launched) agent**.
It just becomes visible on `initializer_bootstrap` because the agent stays
alive long enough for users to look at the Status tab and notice.

**`.aitask-scripts/lib/agent_launch_utils.py:391-403`**, in the
`new_window=True` branch of `launch_in_tmux()`:

```python
elif config.new_window:
    tmux_cmd = [
        "tmux", "new-window", "-t", tmux_window_target(config.session, ""),
        "-n", config.window,
        *cwd_args,
        command,
    ]
    proc = subprocess.Popen(tmux_cmd, stderr=subprocess.PIPE)
    proc.wait()
    if proc.returncode != 0:
        stderr = proc.stderr.read().decode() if proc.stderr else ""
        return proc, f"tmux new-window failed: {stderr}"
    return proc, None
```

`subprocess.Popen` here spawns the **`tmux new-window` launcher** as a child
of the runner. That launcher's only job is to ask the tmux server to create a
new pane and run `command` inside it. The launcher then exits — its PID is
short-lived. `proc.wait()` waits for the launcher (not the agent), and the
function returns `proc` whose `pid` is the dead launcher PID.

`.aitask-scripts/agentcrew/agentcrew_runner.py:625` then writes that PID to
`<agent>_status.yaml`:

```python
update_yaml_field(status_file, "pid", proc.pid)
```

The actual agent process is the command running inside the tmux pane, with a
different PID that is never captured.

## Why nothing self-corrects

- **Heartbeat path doesn't update `pid`.**
  `.aitask-scripts/agentcrew/agentcrew_status.py:cmd_heartbeat` (lines 187–212)
  writes only `<agent>_alive.yaml.last_heartbeat` (and optional
  `last_message`). It never writes `<agent>_status.yaml.pid`. So a live
  heartbeating agent has no way to register its real PID.

- **`sync_stale_processes()` doesn't resync, and won't run anyway.**
  `.aitask-scripts/agentcrew/agentcrew_process_stats.py:220-261` early-returns
  when the runner is alive. If it did run, it only marks the agent as `Error`
  with `error_message: "Process exited unexpectedly"` — it does not look up
  the actual live PID.

## Why both displays are "correct"

Both display sections in `.aitask-scripts/brainstorm/brainstorm_app.py` are
honest readers of `_status.yaml`:

- "Ungrouped Agents" (`_mount_agent_row`, lines ~2256–2293) shows
  `data.get("status")` directly → `Running` (correct, agent IS running).
- "Running Processes" (`ProcessRow.render`, lines 933–958, fed by
  `get_all_agent_processes`) renders `DEAD` based on
  `os.kill(recorded_pid, 0)` (`agentcrew_process_stats._check_pid_alive`,
  lines 51–62) → `False` for the dead launcher PID.

The lie is in the recorded `pid` field. Fix the source, not the displays.

## Fix candidates (to evaluate during planning)

1. **Tmux pane-pid lookup at launch time.** After `tmux new-window`, query
   tmux for the spawned pane's `#{pane_pid}` (the pane shell), then walk to
   the leaf descendant process. Write that PID to `_status.yaml`. Most
   accurate; couples to tmux specifics. Need to capture the pane id at spawn
   time via `tmux new-window -P -F "#{pane_id}"` and then resolve
   `#{pane_pid}` for that pane.

2. **Heartbeat-side self-registration.** Change `cmd_heartbeat` so the
   heartbeat caller writes its own `os.getpid()` (or, better, the leaf agent
   process pid that the wrapper script knows) into `_status.yaml.pid` if it
   differs from the recorded value. Self-correcting, launch-mechanism-
   agnostic. Caveats: (a) must reconcile with `sync_stale_processes` so the
   "PID dead but heartbeat fresh" race doesn't flip the agent to Error
   between launch and first heartbeat; (b) the heartbeat is invoked by the
   wrapper, so capturing the agent's own PID (not the wrapper's) requires
   the wrapper to pass it explicitly or the heartbeat caller to be the agent
   itself. Confirm which during planning.

3. **Combination.** Best-effort tmux pane-pid capture at launch (closes the
   gap immediately) plus heartbeat-side self-correction (covers other launch
   modes and edge cases). Highest robustness.

The planning phase should pick one based on coverage of non-interactive
launch modes (`background`, `detached`, etc. in `launch_in_tmux`) and the
heartbeat caller's knowledge of the real agent PID.

## Acceptance criteria

- After launching an interactive agent in a fresh brainstorm session, the
  PID stored in `<agent>_status.yaml` is the PID of a process that is alive
  for as long as the agent is alive (verifiable via `ps -p <pid>` and
  `os.kill(pid, 0)`).
- The brainstorm Status tab "Running Processes" row no longer shows `DEAD`
  for an agent that is actively heartbeating.
- Existing displays in "Ungrouped Agents" continue to show the correct
  `status` and heartbeat age.
- Non-tmux launch paths (background / detached, if any are still in use) are
  audited and either fixed in the same change or surfaced as an explicit
  follow-up.

## Out of scope

- Adding agent-management actions (kill / clean up) to the Status tab —
  that is t535.
- Removing defensive workarounds in the brainstorm flow that exist because
  status used to be untrustworthy — that is t672.
- Heartbeat-staleness → status-field interaction policy — that was settled
  in t671 and should not be revisited here.
