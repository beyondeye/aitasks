---
priority: medium
effort: high
depends: []
issue_type: enhancement
status: Ready
labels: [aitask_monitor, aitask_monitormini, tmux]
gates: [risk_evaluated]
anchor: 1382
created_at: 2026-08-03 16:18
updated_at: 2026-08-03 16:18
boardidx: 17408
---

## Context

**t1382** fixed the symptoms of renaming a tmux agent window off the `agent-`
prefix (the window vanished from minimonitor; `ait monitor` showed a duplicate
card including the companion pane) but deliberately kept **prefix-based**
classification. This task is the durable fix that was deferred there, requested
explicitly at planning time.

Today two distinct facts are both derived from the window *name*:

- **Agent-ness** — `TmuxMonitor.classify_pane` (`monitor/monitor_core.py`)
  matches `DEFAULT_AGENT_PREFIXES = ["agent-"]`.
- **Task binding** — `_TASK_ID_RE = ^agent-(?:pick|qa|resume)-(\d+(?:_\d+)?)$`
  (`monitor/monitor_core.py`), consumed by `TaskInfoCache.get_task_id` /
  `get_task_id_for_pane`.

A user rename destroys both at once, and the task binding is **unrecoverable**
from the name — which is why t1382 stopped at visibility.

The framework already has the pattern to fix this: the shadow companion stamps
the pane-scoped tmux user option `@aitask_shadow_target` at spawn time
(`SHADOW_TARGET_OPTION`, stamped in `launch_shadow_companion`,
`monitor/monitor_core.py`), and `aidocs/framework/shadow_agent.md` documents it
as the **authoritative** classifier — surviving renames, splits, and window
moves. Agent identity should work the same way.

## Goal

Stamp agent identity and task binding on the pane at spawn time
(`@aitask_agent`, `@aitask_task_id` or similar), read them in discovery, and
fall back to prefix/regex matching only for unstamped panes.

## Scope — this is wider than the monitor package

The `agent-` prefix is load-bearing in several unrelated places. Any change to
the classification model must account for all of them, or the monitor will
disagree with the rest of the framework:

- `.aitask-scripts/lib/tui_switcher.py` — `_AGENT_PREFIXES`
- `.aitask-scripts/lib/framework_version.py` — `COMPANION_PREFIXES`
- `.aitask-scripts/lib/agent_launch_utils.py` — the local `companion_prefixes`
  list, and `maybe_spawn_minimonitor`'s overcrowding count
- `.aitask-scripts/monitor/monitor_app.py` — `action_open_log` guards on
  `window_name.startswith("agent-")`
- `.aitask-scripts/aitask_companion_cleanup.sh` — marker-driven already, but
  worth re-reading against any new marker

## Design questions to settle during planning

1. **Where is the stamp written?** Every agent launch routes through
   `agent_launch_utils.launch_in_tmux`, but so do TUI and companion launches —
   the seam does not know what it is launching. Either thread an explicit
   parameter from each caller (board, monitor, minimonitor, tui_switcher,
   codebrowser, syncer, history_screen, agentcrew) or stamp at the call sites.
   The shadow precedent stamps at the call site, after resolving `pane_id` via
   `resolve_pane_id_by_pid`.
2. **Stamp failure policy.** `launch_shadow_companion` retries once and then
   **kills** the pane, because an unstamped shadow is indistinguishable from a
   real agent forever. An unstamped *agent* degrades gracefully to prefix
   matching, so killing is wrong here — decide and document the weaker policy.
3. **Legacy/unstamped panes.** Agents already running when this ships carry no
   stamp, and so do agents launched by anything outside the framework. The
   prefix path must remain as a fallback; decide whether that is permanent or
   has a removal criterion.
4. **Does `classify_pane` stay pure?** It takes `window_name` only and is called
   from two places. A stamp-aware version needs the pane's option value, which
   changes its signature and its testability.
5. **Scope of the task-id stamp.** Only `agent-(pick|qa|resume)-<id>` windows
   carry a task id today; `agent-explore-*` / `agent-raw-*` deliberately resolve
   to `None`. Preserve that distinction.

## Acceptance criteria

- [ ] A renamed agent window keeps its AGENT classification and its task binding
- [ ] Unstamped panes still classify via the prefix, with a test for both paths
- [ ] The prefix consumers listed under Scope are surveyed and either updated or
      explicitly recorded as out of scope with a reason
- [ ] Stamp-failure policy is implemented and documented
- [ ] `aidocs/framework/shadow_agent.md` (or a sibling doc) documents the new
      option(s) alongside `@aitask_shadow_target`

## Reference

- Archived plan for **t1382** — records the direction decision and why the cheap
  fix was taken first
- `aidocs/framework/shadow_agent.md` — the stamp-at-spawn precedent
- `aidocs/framework/tmux_gateway.md` — per-pane state is keyed by `pane_id`
