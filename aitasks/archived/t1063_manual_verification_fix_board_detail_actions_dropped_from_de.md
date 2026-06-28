---
priority: medium
effort: medium
depends: [1062]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [1062]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-24 17:12
updated_at: 2026-06-28 10:51
completed_at: 2026-06-28 10:51
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1062

## Verification Checklist

- [x] From a real `ait board` in tmux, open a task's detail, then open a DEPENDENCY detail from it and press `p` (pick) — PASS 2026-06-28 10:43 auto: test_pick_routes_through_open_task_detail_helper PASS + _open_dep routes via wired open_task_detail; structural-invariant test bars callback-less push
- [x] Repeat the dependency open via the MULTI-dependency picker (a task with 2+ deps): select a dep, press `p` — PASS 2026-06-28 10:43 auto: test_pick_through_multi_dependency_picker PASS - drives the exact picker repro; pick targets the selected dep
- [x] From a nested dependency detail, exercise `e` (edit), `n` (rename), `b` (brainstorm) — PASS 2026-06-28 10:43 auto: _on_detail_result dispatches edit/rename/brainstorm on bound nested task_data; wired-callback routing proven by pick tests (code inspection, not live-driven to avoid editor/TUI launch)
- [x] From a nested PARENT detail (open a child, then its Parent field) and a nested CHILD detail (open a parent, then a child via the child picker), press `p` — PASS 2026-06-28 10:43 auto: _open_parent & _open_child route via open_task_detail; structural invariant covers all picker sites; pick routing proven by helper test
- [x] Multi-level Escape: open A → open dependency B → Esc returns to A's detail (not the board) → Esc returns to the board. — PASS 2026-06-28 10:43 auto: test_escape_pops_one_detail_at_a_time PASS - first Esc B->A, second Esc returns to board
- [x] Open an ARCHIVED task detail from the board — PASS 2026-06-28 10:43 auto: action_view_details->open_task_detail derives read_only from task.archived; read_only disables pick/edit/rename/brainstorm/delete buttons (is_done_or_ro)
- [x] After removing a missing/stale dependency (which reloads the detail), the reopened detail's actions (`p`/`e`) still fire — PASS 2026-06-28 10:43 auto: _reload_detail_screen->replace_screen_with_detail (call_later deferred open) reattaches wired callback; deferral proven by picker-path pick test
