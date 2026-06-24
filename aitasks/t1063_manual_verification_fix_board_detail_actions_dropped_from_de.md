---
priority: medium
effort: medium
depends: [1062]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1062]
created_at: 2026-06-24 17:12
updated_at: 2026-06-24 17:12
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1062

## Verification Checklist

- [ ] From a real `ait board` in tmux, open a task's detail, then open a DEPENDENCY detail from it and press `p` (pick) — pick launches for the dependency, not the parent.
- [ ] Repeat the dependency open via the MULTI-dependency picker (a task with 2+ deps): select a dep, press `p` — pick launches for that dep (the reported 968→929_3 repro).
- [ ] From a nested dependency detail, exercise `e` (edit), `n` (rename), `b` (brainstorm) — each acts on the nested task (editor/rename/brainstorm opens for it), not the parent.
- [ ] From a nested PARENT detail (open a child, then its Parent field) and a nested CHILD detail (open a parent, then a child via the child picker), press `p` — acts on the nested task.
- [ ] Multi-level Escape: open A → open dependency B → Esc returns to A's detail (not the board) → Esc returns to the board.
- [ ] Open an ARCHIVED task detail from the board — it is now read-only (action buttons disabled), matching nested archived opens.
- [ ] After removing a missing/stale dependency (which reloads the detail), the reopened detail's actions (`p`/`e`) still fire — confirms the deferred-reopen callback wiring.
