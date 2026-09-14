---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [tmux, codeagent, session_persistence]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-10 14:57
updated_at: 2026-09-14 13:56
---

## Origin

Spawned from t1773 during Step 8b review (plan §9.2).

## Upstream defect

- `.aitask-scripts/lib/agent_restore.py:288-304` — `_launch_into_new_window()`
  requires `discover_aitasks_sessions()` to find a tmux session with a pane whose
  cwd walks up to the record's project root. When none exists it returns
  `no_session_for_root:<root>` and the restore rolls back.

## Diagnostic context

t1773 fixed the routing so an orphaned frozen record (window closed, or tmux
server restarted) restores into a new window instead of respawning a dead pane.
That works whenever *some* session for the project exists — the ordinary case,
since Restore runs via `run-shell -b` from a TUI pane that sits in the project.
After a server restart with no project session yet (restoring from a different
project, or from a bare `~` shell) the restore still fails. It is fail-safe and
retryable — the record stays `frozen`, the capture survives — but it cannot
succeed. t1773 made the error name the root; the recovery is this task.

## Suggested fix

Decide between (a) falling back to the invoking pane's session with
`cwd = record root`, and (b) creating a dedicated session for the root. Cover it
with an end-to-end server-restart-with-no-project-session live test alongside
acceptance case 6b.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-14T10:56:27Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-14T11:39:19Z status=pass attempt=1 type=human
