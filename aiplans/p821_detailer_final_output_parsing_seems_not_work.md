---
Task: t821_detailer_final_output_parsing_seems_not_work.md
Worktree: (current branch — profile 'fast')
Branch: (current branch — profile 'fast')
Base branch: main
---

# t821 — Brainstorm auto-apply scan misses agents that are still running

## Context

In brainstorm session `brainstorm-635` a `detail` operation (`detail_001`,
agent `detailer_001`) ran to completion, but its output was never parsed:
no `br_plans/n004_synthesizer_001_plan.md` was written, the node's
`plan_file` was never set, and the `detail_001` group is still `Waiting`.

### Root cause (verified)

The brainstorm engine applies an agent's `_output.md` via a **TUI poll
timer**, not the runner. On session load, `_load_existing_session()` calls
`_scan_existing_<role>()` to recover agents that need applying and seed the
poll timer. Each of the four scans
(`_scan_existing_{patchers,explorers,synthesizers,detailers}` in
`brainstorm_app.py`) contains:

```python
if (data or {}).get("status") != "Completed":
    continue
```

So the scan only ever tracks agents that are **already `Completed`** at
load time. An agent that is still **`Running`** when a fresh TUI loads is
silently dropped — never added to the tracking set/dict, no poll timer
watching it — so when it later completes, nothing calls the apply function.

Timeline confirming this for session 635:

- `detailer_001` process started **12:32:54**, completed **~12:47**.
- The current brainstorm TUI (`brainstorm_app.py 635`, PID 493199) was
  started **12:43:23** — i.e. *while the detailer was still Running*.
- At 12:43 `_scan_existing_detailers()` saw `status: Running` → skipped it.
  `_detailer_targets` stayed empty, no poll timer was created.
- At 12:47 the detailer completed. Nothing was watching → no apply.

`detail_001` stays `Waiting` because it is `apply_detailer_output()` (via
`update_operation(..., status="Completed")`) that flips the group — and it
never ran. There is **no `*_apply_error.log`**: apply was never *attempted*,
not failed.

The "runner stopped / restart stops immediately" symptom is a *consequence*,
not a separate bug: the runner monitors **agents**, not operations. All
agents reached a terminal state (`detailer_001` = `Completed`), so the
runner correctly logged `All agents in terminal state — stopping runner`.
Applying outputs is the TUI's job; the runner has nothing left to do.

This is a **shared-pattern bug** — all four `_scan_existing_*` functions
have the identical `Completed`-only filter. The detailer is simply the role
the user happened to hit (and the newest, added by t741). Fixing only the
detailer would knowingly leave the identical bug in explorer, synthesizer
and patcher, so all four are fixed together.

### Intended outcome

A fresh TUI loaded while an agent is mid-run still tracks that agent, so its
output is auto-applied when it completes — for every role.

## Approach

The `_poll_<role>()` timer is already a correct state machine: it skips
non-`Completed` agents, applies `Completed`-and-needs-apply, and drops
`Completed`-and-applied. The scan only needs to **seed** the tracking
collection with every not-yet-resolved agent so the poll timer is alive.

For a still-`Running` agent `_<role>_needs_apply()` returns `False` (its
`_output.md` is still the registration placeholder, no delimiters) — so the
current "skip if not needs_apply" guard would also wrongly drop it. The scan
decision must therefore be: track in-flight agents unconditionally, track
`Completed` agents only if their output still needs applying, never track
terminally-failed agents.

Agent status values (`lib/agentcrew_utils.sh`): `Waiting`, `Ready`,
`Running`, `Paused`, `Completed`, `Error`, `Aborted`.

## Files to modify

### 1. `.aitask-scripts/brainstorm/brainstorm_session.py` — shared decision helper

Add near the other apply helpers (e.g. after `_agent_to_group_name`):

```python
# Agent _status.yaml values that are terminal but yield no applyable
# output — the TUI auto-apply scan/poll stop watching these agents.
_AGENT_FAILED_STATUSES = ("Error", "Aborted")


def _agent_apply_scan_should_track(status: str, needs_apply: bool) -> bool:
    """Decide whether ``_scan_existing_<role>`` should track an agent.

    - Error/Aborted → never (no output will ever come).
    - Completed     → only if its output still needs applying.
    - Anything else (Waiting/Ready/Running/Paused/empty — still in flight)
      → yes, so the poll timer is alive to apply on completion.
      ``needs_apply`` is meaningless mid-run and is ignored.
    """
    if status in _AGENT_FAILED_STATUSES:
        return False
    if status == "Completed":
        return needs_apply
    return True
```

Single-sourced here (pure, testable) so all four scans share one decision.

### 2. `.aitask-scripts/brainstorm/brainstorm_app.py` — 4 scans + 4 polls

> Read `aidocs/tui_conventions.md` before editing (Textual TUI).

**Each `_scan_existing_<role>()`** (`patchers` ~3747, `explorers` ~4021,
`synthesizers` ~4160, `detailers` ~4081): replace the
`status != "Completed" → continue` filter with the shared decision.
Add `_agent_apply_scan_should_track` to the per-function import.

Detailer / patcher need the node id from the `_input.md` regex
(`_PATCHER_INPUT_META_RE`) for tracking — read it for in-flight agents too;
skip only if the regex fails. Pattern (detailer shown):

```python
status = (data or {}).get("status", "")
# ... read input_path, regex → target_node_id (skip if absent) ...
needs_apply = (
    _detailer_needs_apply(self.task_num, agent, target_node_id)
    if status == "Completed" else False
)
if not _agent_apply_scan_should_track(status, needs_apply):
    continue
self._detailer_targets[agent] = target_node_id
```

Explorer/synthesizer key on the agent name only — same shape, no input read,
`needs_apply = _<role>_needs_apply(self.task_num, agent) if status ==
"Completed" else False`.

**Each `_poll_<role>()`** (so a tracked in-flight agent that later *fails*
doesn't leak an idle timer): import `_AGENT_FAILED_STATUSES` and, before the
existing `status != "Completed"` skip, drop terminally-failed agents:

```python
if status in _AGENT_FAILED_STATUSES:
    self._detailer_targets.pop(agent, None)   # set: .discard(agent)
    continue
```

Update the four scan docstrings ("Scan ... for completed X agents ..." →
"... for X agents that are in-flight or completed-but-unapplied ...").

### 3. `tests/test_brainstorm_session.py` — unit-test the helper

Add a `unittest.TestCase` for `_agent_apply_scan_should_track`:

- in-flight statuses (`Waiting`, `Ready`, `Running`, `Paused`, `""`) → always
  tracked, regardless of `needs_apply`;
- `Completed` → tracked iff `needs_apply` is `True`;
- `Error`, `Aborted` → never tracked.

Import the helper alongside the existing `brainstorm_session` imports.

The full scan integration (fresh TUI loaded mid-run) is covered by manual
verification — the existing repo has no app-level tests for `_scan_existing_*`
and `set_interval` needs a running Textual app.

## Out of scope

- The runner's "all agents terminal → stop" behaviour is correct as designed.
- The initializer auto-apply uses a different mechanism (no `_scan_existing_*`);
  the comparator produces no node and has no apply. Neither is touched.

## Recovering session 635 (one-off, not part of the code change)

`detailer_001` is now `Completed`, so applying its already-finished output:

```bash
ait brainstorm apply-detailer 635 detailer_001 n004_synthesizer_001
```

(or simply relaunch `ait brainstorm 635` — the current scan recovers a
`Completed` detailer fine; only the mid-run case is broken).

## Verification

```bash
python3 tests/test_brainstorm_session.py
python3 tests/test_brainstorm_apply_detailer.py
python3 tests/test_brainstorm_apply_patcher.py
python3 tests/test_brainstorm_apply_explorer.py
python3 tests/test_brainstorm_apply_synthesizer.py
python3 -c "import sys; sys.path.insert(0,'.aitask-scripts'); import brainstorm.brainstorm_app"
```

Manual TUI smoke test: launch a `detail` op; while the detailer agent is
still `Running`, quit and relaunch `ait brainstorm <task>`; confirm the
relaunched TUI applies the plan when the agent completes (plan written to
`br_plans/<node>_plan.md`, node `plan_file` set, the op group flips to
`Completed`, "Detailer … applied" toast).

## Post-implementation

- Engine/TUI code only — no skill port (per CLAUDE.md).
- Run `/aitask-qa 821` for test-gap analysis after implementation.
- Step 9: profile 'fast' works on the current branch; commit code + plan
  separately, then `./.aitask-scripts/aitask_archive.sh 821`.
