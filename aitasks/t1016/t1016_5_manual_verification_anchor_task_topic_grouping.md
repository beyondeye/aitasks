---
priority: medium
effort: medium
depends: [t1016_4]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t1016_1, t1016_2, t1016_3, t1016_4]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-17 13:41
updated_at: 2026-06-21 09:58
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1016_4] In `ait board`, press the by-topic key (`y`) → tasks cluster into per-topic lanes; a topic root + its children + a loose `--followup-of` task all appear in one lane.
- [ ] [t1016_4] Tasks with no anchor and no follow-ups/children appear under a single "Ungrouped" lane (NOT one lane each); legitimate topic roots are not hidden.
- [ ] [t1016_4] Open a task's detail screen, edit the anchor field, save → the file gains an `anchor:` line and the card re-groups under the new topic after refresh.
- [ ] [t1016_4] A legacy parent+children tree (files have no `anchor:`) still clusters together in by-topic via the child→parent fallback (no migration).
- [ ] [t1016_4] Archive a topic root, then re-open by-topic → the topic lane still renders (stable id key) and groups the remaining members.
- [ ] [t1016_1/t1016_3] Create a follow-up via `aitask_create.sh --followup-of <src>` (or trigger a real spawn site, e.g. qa/verification-followup/carryover) → the new task's `anchor` equals src's root and it lands in src's topic lane on the board.
- [ ] [t1016_2] Spot-check a regenerated agent-instruction mirror (AGENTS.md / .codex / .opencode) and the website task-format page → the `anchor` field is present.
