---
priority: medium
effort: medium
depends: [604]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [604]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-21 09:26
updated_at: 2026-06-02 11:58
completed_at: 2026-06-02 11:58
boardcol: manual_verifications
boardidx: 40
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t604

## Verification Checklist

- [x] Pick a manual-verification task with at least 2 pending items; at the first per-item prompt choose "Stop here, continue later"; confirm the task stays Implementing, the lock is held, no items flipped from pending to terminal, and the paused message displays the correct item index — PASS 2026-06-02 11:55 auto: Abort/pause branch in manual-verification.md (lines 230-235) does NOT call 'set' (no items flip, status stays Implementing, lock held) and emits 'paused at item <idx>'; pause is markdown-only, invariants hold by construction (per t604 plan)
- [x] Archive a manual-verification task with one deferred item via `aitask_archive.sh --with-deferred-carryover <id>`; confirm the new carry-over task's filename ends in `_carryover.md` (not `_deferred_carryover.md`) — PASS 2026-06-02 11:55 auto: aitask_archive.sh:563 slug is ${orig_name}_carryover (no _deferred_ infix); test_archive_carryover.sh 13/13 green
- [x] Create a manual-verification task whose checklist has `- [ ] Group X:` followed by two nested `- [ ]` children; run `/aitask-pick <id>`; confirm the interactive loop prompts only for the two children, never for the header bullet — PASS 2026-06-02 11:55 auto: parse on header+2 nested children emitted only the 2 children (idx 1,2); summary TOTAL:2 — header filtered
- [x] Negative case: verify a `:` bullet followed by a same-indent sibling `- [ ]` is NOT filtered — PASS 2026-06-02 11:55 auto: ':' bullet followed by same-indent sibling NOT filtered — both items emitted (negative case confirmed)
- [x] Seed a manual-verification task whose deferred set includes a section header with nested children, archive with `--with-deferred-carryover`; confirm the seeded carry-over task's checklist does not include the orphan header — PASS 2026-06-02 11:55 auto: create_carryover_task extraction (parse | awk defer) excludes filtered header; demonstrated header 'CLI parity group:' absent from seeded deferred set
