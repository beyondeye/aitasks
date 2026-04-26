---
Task: t652_agentcrew_add_missedreporting_state_and_allow_errorstate_rec.md
Base branch: main
plan_verified: []
---

# t652 — Add MissedHeartbeat state and allow Error → Completed recovery

## Context

During the brainstorm-635 crew run, the `initializer_bootstrap` agent was processing a long task (large file reads, LLM thinking) and missed its heartbeat. `agentcrew_runner.mark_stale_as_error()` flipped it Running → Error mid-work. The work was actually correct and complete, but recovering required a 4-hop transition chain (Error → Waiting → Ready → Running → Completed).

Two independent fixes:

1. **MissedHeartbeat as a soft-stale intermediate** — give long-running agents a grace window before being declared dead. Auto-recover if a heartbeat arrives during the window.
2. **Direct Error → Completed transition** — let an agent that proves it finished work self-mark Completed without re-running the 4-hop dance.

### Decisions confirmed with user

- **Grace window**: reuse `heartbeat_timeout_minutes` (no new config key). Total tolerance becomes 2× `heartbeat_timeout_minutes`.
- **Error recovery**: allow `Error → Completed` directly in `AGENT_TRANSITIONS`. No `--force` flag.
- **Crew roll-up**: `MissedHeartbeat` counts as Running in `compute_crew_status()` — no spurious crew-level Error flip during the grace window.

## Files modified

| File | Change |
|------|--------|
| `.aitask-scripts/agentcrew/agentcrew_utils.py` | Add `MissedHeartbeat` to `AGENT_STATUSES`; extend `AGENT_TRANSITIONS`; teach `compute_crew_status` and `get_overall_status` (utils.py:394–407) about MissedHeartbeat; add `get_missed_heartbeat_agents()` helper. |
| `.aitask-scripts/agentcrew/agentcrew_runner.py` | Replace `mark_stale_as_error` with `mark_stale_as_missed_heartbeat`; add `process_missed_heartbeat_agents` (recovery + grace-expired). Wire both into runner main loop near the existing `get_stale_agents` call (~line 912). |
| `.aitask-scripts/agentcrew/agentcrew_status.py` | No transition-table edits needed (validate_agent_transition picks up the new entries). Adjust the `if new_status in ("Completed", "Aborted", "Error")` branch (status.py:118) so `MissedHeartbeat` is **not** treated as terminal. |
| `.aitask-scripts/agentcrew/agentcrew_process_stats.py` | Include `MissedHeartbeat` in active-process filters at process_stats.py:142 and process_stats.py:251 (a process dying while MissedHeartbeat should still be marked Error). |
| `.aitask-scripts/agentcrew/agentcrew_dashboard.py` | Add `MissedHeartbeat` color (`#F1FA8C` — yellow, distinct from Paused orange and Error red) at dashboard.py:62–70. |
| `.aitask-scripts/lib/agentcrew_utils.sh` | Add `AGENT_STATUS_MISSED_HEARTBEAT="MissedHeartbeat"` constant in the existing block (utils.sh:20–26) — keeps the bash mirror in sync per the source-comment at agentcrew_utils.py:13. |
| `tests/test_crew_runner.sh` | New tests: Running→MissedHeartbeat (stale heartbeat), MissedHeartbeat→Running (heartbeat resumes within grace), MissedHeartbeat→Error (grace expires). |
| `tests/test_crew_status.sh` | New tests: `set` command allows `Error → Completed`; `set` command allows `Running → MissedHeartbeat → Running` and `MissedHeartbeat → Error`. |

## State machine details

### `agentcrew_utils.py` — new constants and transitions

```python
AGENT_STATUSES = [
    "Waiting", "Ready", "Running", "MissedHeartbeat",
    "Completed", "Aborted", "Error", "Paused",
]

AGENT_TRANSITIONS: dict[str, list[str]] = {
    "Waiting": ["Ready"],
    "Ready": ["Running"],
    "Running": ["Completed", "Error", "Aborted", "Paused", "MissedHeartbeat"],
    "MissedHeartbeat": ["Running", "Error", "Aborted"],   # NEW
    "Paused": ["Running"],
    "Completed": [],
    "Aborted": [],
    "Error": ["Waiting", "Completed"],   # CHANGED: + Completed
}
```

`Aborted` is included in `MissedHeartbeat`'s outgoing transitions because `graceful_shutdown` (runner.py:799) may need to terminate an agent that is currently MissedHeartbeat.

### `compute_crew_status` (utils.py:89–121) — treat MissedHeartbeat as active

Two minimal edits:

```python
# Old
if "Error" in status_set and "Running" not in status_set:
    return "Error"
if "Running" in status_set:
    return "Running"
...
if "Paused" in status_set and "Running" not in status_set:
    return "Paused"

# New
active = {"Running", "MissedHeartbeat"}
if "Error" in status_set and not (status_set & active):
    return "Error"
if status_set & active:
    return "Running"
...
if "Paused" in status_set and not (status_set & active):
    return "Paused"
```

`get_overall_status` (utils.py:394–407) gets the same treatment for symmetry.

## Heartbeat lifecycle (runner.py)

### New status-file field

Per-agent `_status.yaml` gains `missed_heartbeat_at: <utc-timestamp>` set when transitioning into MissedHeartbeat, cleared on transition out.

### New helper in `agentcrew_utils.py`

```python
def get_missed_heartbeat_agents(worktree: str) -> list[str]:
    """Return agent names currently in MissedHeartbeat state."""
    out = []
    for f in list_agent_files(worktree, "_status.yaml"):
        d = read_yaml(f)
        if d.get("status") == "MissedHeartbeat":
            out.append(d.get("agent_name", ""))
    return [n for n in out if n]
```

### Replace `mark_stale_as_error` (runner.py:310–322)

```python
def mark_stale_as_missed_heartbeat(worktree, stale_agents, agents, batch):
    """Soft-stale: Running -> MissedHeartbeat (grace window before Error)."""
    for name in stale_agents:
        status_file = os.path.join(worktree, f"{name}_status.yaml")
        current = agents[name].get("status", "")
        if validate_agent_transition(current, "MissedHeartbeat"):
            log(f"Agent '{name}' heartbeat missed — marking as MissedHeartbeat (grace window starts)", batch)
            update_yaml_field(status_file, "status", "MissedHeartbeat")
            update_yaml_field(status_file, "missed_heartbeat_at", now_utc())
            agents[name]["status"] = "MissedHeartbeat"
            append_to_agent_log(worktree, name, "STALE: heartbeat missed — entering grace window")
```

### New: process MissedHeartbeat agents each iteration

```python
def process_missed_heartbeat_agents(worktree, agents, hb_timeout_seconds, batch):
    """For each MissedHeartbeat agent:
       - heartbeat fresh again (< hb_timeout) -> recover to Running
       - grace expired (now - missed_heartbeat_at >= hb_timeout) -> Error
    """
    for name, data in agents.items():
        if data.get("status") != "MissedHeartbeat":
            continue
        status_file = os.path.join(worktree, f"{name}_status.yaml")
        alive_path = os.path.join(worktree, f"{name}_alive.yaml")

        # Recovery check: did a fresh heartbeat arrive?
        hb_age = heartbeat_age_seconds(alive_path)
        if hb_age is not None and hb_age < hb_timeout_seconds:
            log(f"Agent '{name}' heartbeat resumed — recovering to Running", batch)
            update_yaml_field(status_file, "status", "Running")
            update_yaml_field(status_file, "missed_heartbeat_at", "")
            data["status"] = "Running"
            append_to_agent_log(worktree, name, "RECOVERED: heartbeat resumed -> Running")
            continue

        # Grace-expired check
        missed_at = data.get("missed_heartbeat_at", "")
        if missed_at and seconds_since(missed_at) >= hb_timeout_seconds:
            log(f"Agent '{name}' grace window expired — marking as Error", batch)
            update_yaml_field(status_file, "status", "Error")
            update_yaml_field(status_file, "error_message", "Heartbeat timeout — grace window expired")
            update_yaml_field(status_file, "completed_at", now_utc())
            data["status"] = "Error"
            append_to_agent_log(worktree, name, "STALE: grace expired -> Error")
```

`heartbeat_age_seconds` and `seconds_since` are small helpers — extend the existing time utilities in `agentcrew_utils.py` (where `now_utc` already lives).

### Wire into runner main loop (runner.py ~line 912)

Replace the existing `mark_stale_as_error(...)` call with:
```python
mark_stale_as_missed_heartbeat(worktree, stale, agents, batch)
process_missed_heartbeat_agents(worktree, agents, hb_timeout_seconds, batch)
```

`hb_timeout_seconds` is already in scope (derived from `meta.get("heartbeat_timeout_minutes", 5) * 60` at runner.py:854).

Order matters: mark new stales first, then evaluate recovery/grace for the full MissedHeartbeat set on the same iteration.

## CLI behavior (agentcrew_status.py)

The transition validation in `cmd_set` (status.py:109) is `validate_agent_transition(current, new_status)` — it picks up the extended `AGENT_TRANSITIONS` dict automatically. No code change needed there.

The terminal-timestamp branch at status.py:118 currently sets `completed_at` for `Completed | Aborted | Error`. `MissedHeartbeat` is **not** terminal, so leave the branch untouched — it correctly skips the timestamp.

When operator runs `ait crew status set --crew X --agent Y --status Completed` on an Error agent, `validate_agent_transition("Error", "Completed")` now returns True, the status flips, `completed_at` is set, crew status is recomputed.

## Verification

```bash
# State machine + transitions
bash tests/test_crew_status.sh
bash tests/test_crew_runner.sh

# Lint
shellcheck .aitask-scripts/lib/agentcrew_utils.sh

# Smoke: end-to-end on a real crew (manual)
ait crew init test_grace --agents '[{"name":"a"}]'
ait crew runner --crew test_grace &
ait crew status set --crew test_grace --agent a --status Ready
ait crew status set --crew test_grace --agent a --status Running
# Wait > heartbeat_timeout_minutes without sending heartbeat
ait crew status get --crew test_grace --agent a   # expect MissedHeartbeat
ait crew status heartbeat --crew test_grace --agent a   # send heartbeat
ait crew status get --crew test_grace --agent a   # expect Running (recovered)

# Direct Error -> Completed
ait crew status set --crew test_grace --agent a --status Error
ait crew status set --crew test_grace --agent a --status Completed   # now allowed
```

The new tests in `tests/test_crew_runner.sh` cover the auto-transition paths without needing the smoke run.

## Out of scope

- Configurable per-crew or per-agent `missed_heartbeat_grace_minutes` — deferred. Reusing `heartbeat_timeout_minutes` is the agreed default; a separate key can be added later if real-world tuning needs differ.
- Crew-status "Degraded" warning state — rejected; MissedHeartbeat is invisible at the crew level (rolls up as Running).
- `--force` flag on `ait crew status set` — rejected; the new `Error → Completed` transition removes the most common reason for it.

## Reference: Step 9 (Post-Implementation)

After implementation: commit code + plan separately (per task-workflow Step 8), then run Step 9 archival via `./.aitask-scripts/aitask_archive.sh 652`.
