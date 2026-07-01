---
priority: medium
effort: medium
depends: [1039]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1039]
created_at: 2026-06-22 17:26
updated_at: 2026-06-22 17:26
boardidx: 70
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1039

## Verification Checklist

- [ ] [t1039] In a live `ait brainstorm <task>` session through the real ghostty->tmux->Textual stack: on the (B)rowse and (S)ession tabs, `ctrl+r Retry initializer apply` does NOT appear in the footer (not even dimmed/greyed).
- [ ] [t1039] On the (R)unning tab, `ctrl+r Retry initializer apply` IS visible in the footer and is enabled (its owning surface).
- [ ] [t1039] The sibling contextual keys do not leak dimmed either: `A Node action` / `f Defer module` show only on Browse with a node selected; `enter Open detail` shows only where a node detail is openable.
