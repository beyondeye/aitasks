---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui, minimonitor]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-28 11:19
updated_at: 2026-07-28 17:58
---

## Problem

In the ait **minimonitor** TUI, the `i` keyboard shortcut shows Task Info for the
currently selected code agent. After the refactor that moved the code agent
*associated with* (owning) the minimonitor session to be rendered **outside** the
selectable list — pinned at the top and non-selectable — there is no longer any
way to see task info for that owned agent. The only workaround is to switch to a
different code-agent window and select the agent from there.

## Root cause

All paths in `.aitask-scripts/monitor/minimonitor_app.py`:

- The `i` binding (`:185`) invokes `action_show_task_info` (`:1462`).
- `action_show_task_info` resolves its target **only** through
  `_get_focused_pane_id()` (`:822`), which returns a pane id **only** when the
  focused Textual widget is a `MiniPaneCard`:
  ```python
  def _get_focused_pane_id(self) -> str | None:
      focused = self.focused
      if isinstance(focused, MiniPaneCard):
          return focused.pane_id
      return None
  ```
- The refactor split the UI into two containers in `compose` (`:247`):
  `#mini-own-agent` (the pinned owned agent) and `#mini-pane-list` (selectable
  cards). The owned agent is built by `_maybe_build_own_agent_panel` (`:654`) as
  plain **non-focusable `Static`** widgets, and `_rebuild_pane_list` (`:676`)
  **explicitly excludes** the owned pane from the selectable list (`:692`):
  ```python
  own_pane_id = own_snap.pane.pane_id if own_snap else None
  agents = [s for s in self._snapshots.values()
            if s.pane.category == PaneCategory.AGENT
            and s.pane.pane_id != own_pane_id]
  ```
- Therefore `self.focused` can never be the owned agent's widget →
  `_get_focused_pane_id()` never returns the owned pane id → `i` has no path to
  it. The **data is available** regardless: the owned snapshot still lives in
  `self._snapshots` and is resolvable via `_find_own_agent_snapshot()` (`:476`).

## Suggested fix

Mirror the fallback pattern already used by other handlers in the same file —
`action_kill_own_agent` (`:863`) and the next-sibling handler (`:909`) both fall
back to `_find_own_agent_snapshot()` when no card is focused. In
`action_show_task_info`, when `_get_focused_pane_id()` returns `None`, fall back
to `_find_own_agent_snapshot()` and use that snapshot's pane to resolve and show
task info (via `TaskInfoCache.get_task_id_for_pane` / `get_task_info`, then
`push_screen(TaskDetailDialog(info))` as it does today). Confirm the desired
precedence (focused card first, then owned agent) and that the "Focus an agent
pane first" warning only fires when neither is resolvable.

## Verification

- Launch a minimonitor session whose owning agent is pinned at the top and no
  card is focused; press `i` → the `TaskDetailDialog` for the owned agent opens.
- With a selectable card focused, `i` still shows that card's task info
  (unchanged precedence).
- With neither resolvable, the existing warning still fires.

## Reference

- `.aitask-scripts/monitor/minimonitor_app.py`: `action_show_task_info` (:1462),
  `_get_focused_pane_id` (:822), `_maybe_build_own_agent_panel` (:654),
  `_rebuild_pane_list` (:676, exclusion at :692), `_find_own_agent_snapshot`
  (:476), fallback exemplars `action_kill_own_agent` (:863) / next-sibling (:909).
- Task info plumbing: `.aitask-scripts/monitor/monitor_core.py`
  `get_task_id_for_pane` (:2530), `get_task_info` (:2547);
  `TaskDetailDialog` in `.aitask-scripts/monitor/monitor_shared.py` (:142).
