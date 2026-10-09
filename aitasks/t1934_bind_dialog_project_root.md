---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [monitor, minimonitor, tmux]
gates: [risk_evaluated]
anchor: 1922
followup_kind: risk_mitigation
created_at: 2026-10-09 15:34
updated_at: 2026-10-09 15:34
---

## Origin

Risk-mitigation ("after") follow-up for t1922, created at Step 8d after implementation landed.

## Risk addressed

mid-dialog root change (review concern 2)

- Mid-dialog root changes are still possible for unregistered sessions whose vote flips · severity: low · → mitigation: bind_dialog_project_root

## Goal

Bind the session root when monitor/minimonitor dialogs open (p, n, R, E, column create/move) and revalidate before every launch/kill/write; one root for no-followed-pane p.

Context from t1922 (see `aiplans/archived/p1922_*.md` once archived):

- t1922 made a session's `@aitask_project_root` stamp authoritative, so for a
  STAMPED session the root cannot change between dialog stages. For an
  unstamped session (pre-upgrade, or created by hand) discovery uses a pane
  vote, which can flip between ticks.
- **minimonitor `p`:** `action_pick_task_by_number`
  (`.aitask-scripts/monitor/minimonitor_app.py`) captures
  `target_root = self._root_for_snap(snap)` when the number modal opens, but
  `_on_pick_number_entered` resolves `get_task_info(target_id, sess)` through
  the session map AT CALLBACK TIME. If the mapping moves from A to B while the
  modal is open, the dialog shows B's task while `_launch_pick` launches in A.
  There is also no final revalidation in the confirm callback
  (`_on_pick_confirmed`).
- **minimonitor `p` without a followed pane:** `target_root = self._project_root`
  while `get_task_info(…, self._session)` resolves through the session map;
  the two can disagree (one repo's task described, another's launched).
- **monitor `R`:** `action_restart_task` shows details resolved through
  `TaskInfoCache`, but `_on_restart_confirmed` re-resolves the launch root via a
  SYNC `get_session_to_project_mapping()` AFTER approval
  (`MonitorApp._root_for_snap` reads the mapping live, not the tick map).
  Bind the root shown to the root launched.
- Same shape for `n` (both apps; monitor `_launch_pick_for_sibling` kills
  before launching), `E` (AgentCommandScreen callback → `spawn_shadow`), and the
  column picker's `_create_and_move` / `_apply_column_move` (`--root`).

Expected shape: bind one canonical root when the first dialog opens, carry it
into every callback, and before any launch/kill/board write re-resolve the
session's current root and refuse (notify, do nothing) when it no longer equals
the bound one. Consider switching `MonitorApp._root_for_snap` to the tick map
(`_session_root_map`) as minimonitor already does (t1598), so all copies agree.

Tests: a regression where the root changes between dialog stages and the task
number exists in both projects — at the number stage and at the confirm stage —
asserting no launch/kill/board write happens (spies), plus the no-followed-pane
agreement case.
