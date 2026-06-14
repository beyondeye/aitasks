---
Task: t986_1_multi_agent_window_substrate.md
Parent Task: aitasks/t986_shadow_agent.md
Sibling Tasks: aitasks/t986/t986_2_*.md, aitasks/t986/t986_3_*.md, aitasks/t986/t986_4_*.md, aitasks/t986/t986_5_*.md, aitasks/t986/t986_6_*.md
Archived Sibling Plans: aiplans/archived/p986/p986_*_*.md
Worktree: aiwork/t986_1_multi_agent_window_substrate
Branch: aitask/t986_1_multi_agent_window_substrate
Base branch: main
---

# Plan: t986_1 — Multi-agent-per-window substrate + shadow helper-pane exclusion

## Context

Foundation for the shadow agent (t986). The shadow is a *second* coding agent in
the shadowed agent's tmux window. The tmux gateway + capture are pane-keyed
(safe); six monitor app-layer sites assume one agent per window. Re-key monitor
state on `pane_id` and classify the `shadow` pane as a helper so it is excluded
from agent lists. **Coordinate with t719** (same `monitor_core.py`).

## Implementation steps

1. **Extract pure units** (no Textual import): pane→task-id mapping and
   per-window agent-pane counting, so they can be unit-tested in isolation.
2. **Re-key `TaskInfoCache`** (`monitor/monitor_core.py` ~1381, ~1398-1450) on
   `pane_id` (or `(window_index, pane_index)`); thread pane id through the
   display, sibling, and kill paths.
3. **`kill_agent_pane_smart()`** (1278-1318): only `kill_window()` when ALL agent
   panes in the window are gone; otherwise `kill_pane()`.
4. **Companion classification** (`_is_companion_process()` 152-170,
   `classify_pane()` ~877-944): recognize the `shadow` pane (window name
   `agent-shadow-*` and/or shadow op in cmdline) and exclude it from agent
   snapshots — exactly as minimonitor/monitor panes are excluded today.
5. **`minimonitor_app.py:_find_sibling_pane_id()`** (674-697): resolve the
   intended agent pane by id (from `_find_own_agent_snapshot()` ~403-422), not
   `other_panes[0]`.
6. **Launch path** (`lib/agent_launch_utils.py`): refocus the just-launched pane,
   not `.0` (754-758); account for a shadow pane in `maybe_spawn_minimonitor()`
   3-pane skip (728-740).
7. **Cleanup** (`aitask_companion_cleanup.sh`): per-pane `pane-died` accounting so
   killing one agent in a shared window does not despawn the companion while
   another agent lives.
8. Keep all raw tmux behind the gateway.

## Verification

- pane_id-keyed task map resolves the correct task per pane (not per window).
- Two agents in one tmux window: killing one leaves the other alive with correct task-ids.
- `_find_sibling_pane_id()` returns the intended agent pane, not the first non-companion pane.
- A `shadow`-classified pane is absent from monitor and minimonitor agent lists.
- `bash tests/test_no_raw_tmux.sh` stays green; `shellcheck aitask_companion_cleanup.sh` clean.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9.
