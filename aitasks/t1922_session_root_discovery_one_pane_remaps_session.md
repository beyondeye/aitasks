---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [monitor, minimonitor, tmux]
gates: [risk_evaluated]
created_at: 2026-10-08 17:14
updated_at: 2026-10-08 17:14
---

## Problem

A single pane whose working directory wanders into another aitasks repo
remaps the **whole tmux session** to that repo. Every monitor/minimonitor row
for the session then resolves its task against the wrong project: no task
title on `agent-pick-<id>` rows, and no COMPLETED/DONE glyph for archived
tasks.

Observed 2026-10-08 in session `aitasks`:
- The tmux global env holds `AITASKS_PROJECT_aitasks=/home/ddt/Work/aitasks`,
  set by `ait ide`.
- Pane `1:1` (window `aitasks`, a `claude` process) had
  `pane_current_path=/home/ddt/Work/thinking_app`. Every other pane in the
  session was in `/home/ddt/Work/aitasks`.
- `discover_aitasks_sessions_checked()` returned
  `AitasksSession(session='aitasks', project_root=/home/ddt/Work/thinking_app, ...)`.
- As a result, minimonitor rows for t1888 (archived), t1914 and the others
  showed no title and no DONE glyph.
- Sessions `thinking_back` and `thinkingapp` were unaffected because none of
  their panes moved.
- Resolving the same tasks directly with
  `TaskInfoCache(Path('/home/ddt/Work/aitasks'))` works:
  t1888 → Done/archived, t1914 → Implementing. The task data is fine; only
  the session→root mapping is wrong.

## Cause

`.aitask-scripts/lib/agent_launch_utils.py`:
- `_collect_live_roots` (~L1289) tries `_project_root_from_pane_paths` first.
  It returns the **first** pane cwd that walks up to an aitasks project
  (~L1112).
- The explicit `AITASKS_PROJECT_<session>` registry value is consulted only
  when **no** pane resolves.

So one pane listed first, for example a Claude Code session whose process cwd
followed a cross-repo `cd`, overrides both the explicit registration and the
majority of panes.

## Goal

Make the session→project-root mapping robust to one wandering pane:
- **Prefer an explicit `AITASKS_PROJECT_<session>` value** over the pane-cwd
  guess when it names a valid project root (marker file present).
- Fall back to pane cwds only when the variable is absent or invalid.
- When pane cwds disagree and no explicit value exists, do not let pane order
  decide. Use a deterministic rule such as a majority vote, the agent panes'
  roots, or the session's first window. Planning chooses the rule and records
  why.

**Blast radius.** `_collect_live_roots` feeds every consumer:
- `discover_aitasks_sessions`, `_checked` (used by
  `aitask_project_resolve.sh candidates`, t1869) and `_async`;
- monitor/minimonitor `get_session_to_project_mapping_async`;
- the TUI switcher, applink and stats.

Check each consumer's expectation and keep the `_checked` completeness
contract.

## Tests

Add a regression test over the pluggable `run` / `read_registry` seam of
`_collect_live_roots`. A session has one pane in repo B and the rest in repo
A, and the registry names repo A: the result must be A. Also cover:
- no registry value with mixed panes;
- a registry value pointing at a path with no marker file;
- all panes agreeing.

## Workaround

`cd` the wandering pane back into its own repo, or close it. The monitor picks
up the fix on its next refresh.
