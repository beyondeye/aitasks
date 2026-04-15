---
Task: t557_minimonitor_lifecycle_on_codeagent_restart.md
Base branch: main
plan_verified: []
---

# Plan: Minimonitor lifecycle on codeagent restart (t557)

## Context

t556 added a "restart task" action to the monitor TUI. While implementing it,
the minimonitor (companion pane that shows live status alongside each agent)
lifecycle was found to be under-specified:

- `maybe_spawn_minimonitor` (`agent_launch_utils.py:213`) splits the agent
  window with a monitor pane. It only guards against *double-spawn* inside a
  window, assuming one-agent-per-window.
- Agent kill paths only call `TmuxMonitor.kill_pane`, which leaves the
  companion minimonitor pane alive. The window survives with nothing but the
  minimonitor — an orphan.
- `maybe_spawn_minimonitor` resolves a window by **first-matching name**. If
  an orphan window from a previous agent run still exists, a newly launched
  agent window that reuses the name (e.g. `agent-pick-42`) gets no
  minimonitor — the new one is attached to the stale first match.
- t556 side-stepped this in the *restart* path by calling `kill_window`
  unconditionally, but that is too aggressive if two agents ever share a
  window (split launch via `AgentCommandScreen`).

This change documents a concrete lifecycle rule and implements it with a
small helper in `TmuxMonitor`, fixing the three agent kill paths and making
the window-name lookup robust against transient duplicates.

## Failure modes (confirmed by code reading)

1. **Orphaned minimonitor after kill (`k` binding).**
   `_on_kill_confirmed` (`monitor_app.py:1373`) calls `kill_pane(pane_id)`.
   The companion minimonitor pane in the same window is untouched, so an
   empty window survives with just the minimonitor still running. It is
   invisible in the monitor's agent list (companions are filtered out by
   `_parse_list_panes` / `_is_companion_process`), but keeps holding a
   window slot.

2. **Orphaned minimonitor on "next sibling" (`n` binding, Done/parent case).**
   `_on_next_sibling_result` (`monitor_app.py:1444`) has the same problem. It
   kills the old agent pane and then launches a new window with a different
   name. The minimonitor for the old window becomes a permanent orphan.

3. **Name ambiguity compounding (1) and (2).**
   Once any orphan survives, any future launch reusing a dup name
   (e.g. restarting the parent task later) falls back to the stale first
   match in `maybe_spawn_minimonitor`. t556 worked around this for the
   restart case with a pre-launch `kill_window`, but (1) and (2) still
   seed duplicates for unrelated future launches.

4. **Multi-agent window too-aggressive restart.**
   `_on_restart_confirmed` (`monitor_app.py:1546`) calls `kill_window(pane_id)`
   unconditionally. When `AgentCommandScreen` is used with "existing window +
   split" (see `_build_tmux_config`, `agent_command_screen.py:730`), the
   resulting `TmuxLaunchConfig(new_session=False, new_window=False)` actually
   places a second agent pane in an already-populated agent window. A restart
   on either agent then nukes the whole window, destroying the sibling too.

## Lifecycle rule

> When the last agent pane in a window dies, the whole window dies with it
> (which automatically cleans up the companion minimonitor). If other agent
> panes remain, kill only the requested pane and leave the existing
> minimonitor alone.

The rule is enforced by the caller that is killing the agent — not by a
background sweep in `TmuxMonitor` — because the caller already has the
`pane_id` and knows it is about to disappear. Enforcing it here is cheap
(one `list-panes` per kill), synchronous, and keeps the invariant local.

## Implementation

### Critical files

- `.aitask-scripts/monitor/tmux_monitor.py` — add the helper
- `.aitask-scripts/lib/agent_launch_utils.py` — make `maybe_spawn_minimonitor` robust
- `.aitask-scripts/monitor/monitor_app.py` — three call sites

### Change 1 — `TmuxMonitor.kill_agent_pane_smart` (new)

Add a new method after `kill_window` in `tmux_monitor.py:443`:

```python
def kill_agent_pane_smart(self, pane_id: str) -> tuple[bool, bool]:
    """Kill an agent pane, collapsing the window if it was the last agent.

    Returns (ok, killed_window). If no agent panes remain in the window after
    removing this pane, the whole window is killed (which also cleans up any
    companion minimonitor pane). Otherwise only the requested pane is killed,
    preserving the minimonitor for surviving siblings.
    """
    pane = self._pane_cache.get(pane_id)
    if pane is None:
        return self.kill_pane(pane_id), False

    # Count *other* agent panes (non-companion) currently in the window.
    window_target = f"{self.session}:{pane.window_index}"
    others = 0
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-t", window_target,
             "-F", "#{pane_id}\t#{pane_pid}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) != 2:
                    continue
                other_id, pid_str = parts
                if other_id == pane_id:
                    continue
                try:
                    pid = int(pid_str)
                except ValueError:
                    continue
                if not _is_companion_process(pid):
                    others += 1
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # Fall back to a plain pane kill; we lose the companion cleanup but
        # at least the agent goes away.
        return self.kill_pane(pane_id), False

    if others == 0:
        return self.kill_window(pane_id), True
    return self.kill_pane(pane_id), False
```

Reuses the existing `kill_pane` / `kill_window` primitives and the existing
`_is_companion_process` helper from the same module. No new
dependencies. The fallback path on `list-panes` failure degrades gracefully
to the current behaviour.

### Change 2 — `maybe_spawn_minimonitor`: prefer last-match window

Fix the first-match lookup in `agent_launch_utils.py:258-263`:

```python
        win_index = None
        for line in result.stdout.strip().splitlines():
            if ":" in line:
                idx, name = line.split(":", 1)
                if name == window_name:
                    win_index = idx  # keep looping — pick the *last* match
        if win_index is None:
            return False
```

`tmux list-windows` prints windows in order of their window index; `new-window`
appends to the end. Iterating and keeping the last match yields the most
recently created window with that name, which is the one the caller just
launched. This is a defensive belt-and-braces fix — Change 3 below eliminates
most cases where a duplicate name can even exist, but Change 2 keeps the code
correct if an orphan ever slips through (e.g. external tmux activity).

### Change 3 — Call-site updates in `monitor_app.py`

Three sites currently kill agent panes. Replace each with the smart helper:

1. **`_on_kill_confirmed` (line 1373)** — `k` binding.
   - Before: `if self._monitor.kill_pane(pane_id):`
   - After:  `ok, _ = self._monitor.kill_agent_pane_smart(pane_id); if ok:`

2. **`_on_next_sibling_result` (line 1444)** — `n` binding, Done/parent case.
   - Before: `self._monitor.kill_pane(pane_id)`
   - After:  `self._monitor.kill_agent_pane_smart(pane_id)`
   - This is what makes sibling pick clean up the orphan minimonitor from
     the previous agent. The discard of the return value is intentional — the
     existing code does not check it either.

3. **`_on_restart_confirmed` (line 1546)** — `R` binding.
   - Before: `if self._monitor and self._monitor.kill_window(pane_id):`
   - After:  `if self._monitor:
                 ok, _ = self._monitor.kill_agent_pane_smart(pane_id)
                 if ok:`
   - Rationale: single-agent case (by far the common one) still ends in
     `kill_window`, matching t556 behaviour. Multi-agent case now correctly
     leaves siblings alone.
   - The comment block at lines 1540-1545 explains why the old window must
     be torn down before the new launch. Update it to describe the smart
     behaviour and mention that Change 2 covers the residual multi-agent
     case where the new window shares a name with the still-alive old one.

## Out of scope

- **Proactive orphan sweep.** `TmuxMonitor.capture_all` / `discover_panes`
  could detect orphan minimonitor-only windows on each refresh and cull them.
  Not done here — enforcing the rule at kill time is both sufficient for the
  identified failure modes and easier to reason about. Add only if orphans
  turn out to be reachable by a path other than these three kill sites.
- **Agent launch returning a window handle.** A cleaner long-term fix to
  Change 2 is to have `launch_in_tmux` return the created window index/ID
  and pass it to `maybe_spawn_minimonitor` directly. That touches ~10
  callers across board/codebrowser/tui_switcher/agentcrew; the
  last-match fallback gets us the same correctness for this task with a
  one-liner change.

## Verification

All verification is by code inspection + manual tmux exercise. The monitor
app has no test suite; adding one for this change is out of scope.

1. **Syntax / import sanity:**
   ```bash
   python -m py_compile .aitask-scripts/monitor/tmux_monitor.py \
                        .aitask-scripts/monitor/monitor_app.py \
                        .aitask-scripts/lib/agent_launch_utils.py
   ```

2. **Existing tests:**
   ```bash
   for t in tests/test_*.sh; do bash "$t" || echo "FAIL: $t"; done
   ```
   None of the existing bash tests touch the monitor; this is just a
   regression guard.

3. **Manual repro (kill / orphan path):**
   - Start a tmux session with `ait monitor` and launch an agent via `n`
     (next sibling) or the board. Confirm the companion minimonitor pane
     appears.
   - Press `k` on the agent pane and confirm.
   - Run `tmux list-windows -t aitasks` — the old `agent-*` window should
     be gone (previously the window survived holding only the minimonitor).

4. **Manual repro (restart path, single-agent):**
   - Launch an agent, wait for it to go idle, press `R`.
   - Confirm the old window is killed, the new agent window is created, and
     exactly one minimonitor pane attaches to it (previously under rare
     duplicate-name conditions the minimonitor attached to the old window).

5. **Manual repro (multi-agent window, restart):**
   - Via the board, launch an agent with `AgentCommandScreen` targeting an
     existing agent window (split mode).
   - Press `R` on one of the agents.
   - Confirm only the restarted agent's pane dies; the sibling agent and the
     minimonitor remain.

## Final Implementation Notes

- **Actual work done:** Implemented the plan as written. Added
  `TmuxMonitor.kill_agent_pane_smart` in `tmux_monitor.py` (new method right
  after `kill_window`). It looks up the pane in `_pane_cache`, runs
  `tmux list-panes -t <session>:<window_index>`, counts sibling panes whose
  pid is not a companion process, and dispatches to `kill_window` (zero
  siblings) or `kill_pane` (one or more siblings). Changed the window lookup
  in `maybe_spawn_minimonitor` (`agent_launch_utils.py`) to keep iterating
  after the first name match so it returns the *last* window of that name,
  which is the most recently created one. Updated the three `monitor_app.py`
  call sites: `_on_kill_confirmed` (`k`), the Done/archived/parent branch of
  `_on_next_sibling_result` (`n`), and the `on_pick_result` closure inside
  `_on_restart_confirmed` (`R`). The restart path's comment block was
  rewritten to describe the smart behaviour and mention that last-match
  lookup covers the transient duplicate-name window.
- **Deviations from plan:** None in behaviour. Two minor shape changes from
  the plan snippet:
  - `kill_agent_pane_smart` uses an early `return` on the `list-panes` rc
    check instead of dropping into the loop; semantics are identical (the
    plan snippet gated the loop on `returncode == 0`).
  - `_on_restart_confirmed` was originally a single `if self._monitor and
    self._monitor.kill_window(pane_id):` line inside a closure. The smart
    helper returns a tuple, so the rewrite is a nested `if self._monitor:` +
    `ok, _ = ...; if ok:` — behaviourally the same as the one-liner in the
    plan, just nested one more level than the plan example showed.
- **Issues encountered:** None. `python -m py_compile` passed on the three
  files; the full `tests/test_*.sh` sweep shows 52 pass / 21 fail with the
  same 21 failures present on an unchanged working tree (`git stash` +
  re-run), so no regressions were introduced by this task. The 21 failures
  are pre-existing infrastructure issues (missing `archive_utils.sh` copy in
  isolated test setups, unrelated scripts) outside this task's scope.
- **Key decisions:** Kept the caller-side enforcement of the lifecycle rule
  as originally planned rather than adding an orphan sweep in `TmuxMonitor`.
  Left the "return last match" fix in `maybe_spawn_minimonitor` as the
  one-line defensive belt even though the call-site fixes now prevent most
  duplicate-name situations — the cost is zero and it keeps the companion
  attachment correct if orphans ever appear via an external path.
