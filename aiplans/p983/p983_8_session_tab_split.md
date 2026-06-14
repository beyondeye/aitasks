---
Task: t983_8_session_tab_split.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_*_*.md
Archived Sibling Plans: aiplans/archived/p983/p983_*_*.md
Worktree: aiwork/t983_8_session_tab_split
Branch: aitask/t983_8_session_tab_split
Base branch: main
---

# p983_8 — Session tab

Child of t983. Session-lifecycle ops are not node-contextual, so they leave the
wizard for a dedicated **Session** tab. Depends on the t983_6 wizard re-host
owning the op-select dispatch.

## Goal
Give pause/resume/finalize/archive/delete their own `tab_session` (`s`), keeping
execution (`_execute_session_op`,
`.aitask-scripts/brainstorm/brainstorm_app.py:7415`) + confirm modals
(`DeleteSessionModal`).

## Steps
1. Build `tab_session` with a list of the 5 session ops + descriptions (reuse the
   `_OPERATION_HELP` session-op text).
2. Route selection → `_execute_session_op`; keep `DeleteSessionModal` for delete.
3. Remove session ops from the wizard op_select list.
4. Reload session data after each op as today.

## Verification
- Pilot: `tests/test_brainstorm_session_tab.py` — op list renders; dispatch
  invokes `_execute_session_op`; delete shows `DeleteSessionModal`.
- Suite `tests/test_brainstorm*.py` green.
- Manual: `s` → Session tab → each lifecycle op with confirm.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_8`.
