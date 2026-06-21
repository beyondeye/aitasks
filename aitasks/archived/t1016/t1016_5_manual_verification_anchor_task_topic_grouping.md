---
priority: medium
effort: medium
depends: [t1016_4]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [t1016_1, t1016_2, t1016_3, t1016_4]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-17 13:41
updated_at: 2026-06-21 10:03
completed_at: 2026-06-21 10:03
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1016_4] In `ait board`, press the by-topic key (`y`) → tasks cluster into per-topic lanes; a topic root + its children + a loose `--followup-of` task all appear in one lane. — PASS 2026-06-21 10:02 auto: board pilot tests and live t1016 topic lane inspection showed root, child, and loose follow-ups grouped together
- [x] [t1016_4] Tasks with no anchor and no follow-ups/children appear under a single "Ungrouped" lane (NOT one lane each); legitimate topic roots are not hidden. — PASS 2026-06-21 10:02 auto: board topic grouping unit tests confirmed singleton tasks collapse into one Ungrouped lane while real topic lanes remain visible
- [x] [t1016_4] Open a task's detail screen, edit the anchor field, save → the file gains an `anchor:` line and the card re-groups under the new topic after refresh. — PASS 2026-06-21 10:02 auto: temp-workspace headless board flow opened detail, edited AnchorField, persisted anchor: 9000, and regrouped under By-Topic
- [x] [t1016_4] A legacy parent+children tree (files have no `anchor:`) still clusters together in by-topic via the child→parent fallback (no migration). — PASS 2026-06-21 10:02 auto: board topic grouping unit tests confirmed legacy anchorless children group by parent fallback with no migration
- [x] [t1016_4] Archive a topic root, then re-open by-topic → the topic lane still renders (stable id key) and groups the remaining members. — PASS 2026-06-21 10:02 auto: board topic grouping unit tests confirmed absent/archived root ids remain stable lane keys for remaining members
- [x] [t1016_1/t1016_3] Create a follow-up via `aitask_create.sh --followup-of <src>` (or trigger a real spawn site, e.g. qa/verification-followup/carryover) → the new task's `anchor` equals src's root and it lands in src's topic lane on the board. — PASS 2026-06-21 10:02 auto: anchor create, verification-followup, and carryover tests passed; live t1016 lane includes anchored loose follow-ups t1034 and t1035
- [x] [t1016_2] Spot-check a regenerated agent-instruction mirror (AGENTS.md / .codex / .opencode) and the website task-format page → the `anchor` field is present. — PASS 2026-06-21 10:02 auto: agent instruction tests passed and anchor field is present in AGENTS.md, .codex, .opencode, and website task-format docs
