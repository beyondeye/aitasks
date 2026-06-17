---
priority: medium
effort: medium
depends: [t983_7]
issue_type: refactor
status: Implementing
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-14 11:40
updated_at: 2026-06-17 10:53
---

## Context
Child of t983. Session-lifecycle ops (pause, resume, finalize, archive, delete)
are NOT node-contextual, so they get their own **Session** tab instead of living
in the wizard. Today they run through the wizard op_select→confirm path
(`_execute_session_op`, `.aitask-scripts/brainstorm/brainstorm_app.py:7415`);
`delete` uses `DeleteSessionModal`. Depends on the wizard re-host (t983_6) owning
the wizard so the op-select dispatch can be split cleanly.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — add `tab_session` with the
  session-op list + descriptions; move the session-op dispatch out of the wizard
  op_select path; keep `_execute_session_op` (:7415) execution + confirm modals
  (`DeleteSessionModal`).
- `tests/test_brainstorm_session_tab.py` — NEW.

## Reference Files for Patterns
- `_execute_session_op` (:7415) — the execution to keep.
- `DeleteSessionModal` — the delete confirm gate.
- `_OPERATION_HELP` session-op entries (pause/resume/finalize/archive/delete) —
  reuse their descriptions in the Session tab list.
- Status-tab list/row rendering as a layout reference.

## Implementation Plan
1. Build `tab_session` (`s`) with a list of the 5 session ops + descriptions.
2. Route selection → `_execute_session_op`; keep `DeleteSessionModal` for delete.
3. Remove session ops from the wizard op_select list (they no longer belong to
   the contextual wizard).
4. Reload session data after each op as today.

## Verification
- Pilot: `tests/test_brainstorm_session_tab.py` — op list renders, dispatch
  invokes `_execute_session_op`, delete shows `DeleteSessionModal`.
- Suite: `tests/test_brainstorm*.py` green.
- Manual: `s` → Session tab → pause/resume/finalize/archive/delete with confirm.
