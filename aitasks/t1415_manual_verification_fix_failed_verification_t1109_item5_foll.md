---
priority: medium
effort: medium
depends: [1409]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1409]
created_at: 2026-08-04 18:34
updated_at: 2026-08-04 18:34
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1409

## Verification Checklist

- [ ] Sign a gate with `ait gate pass <id> review_approved`, change a code file, then confirm `ait gates run <id>` re-pends with the `stale signature` note and `ait gate status <id>` shows pending — the live headless-lane flow end to end.
- [ ] Confirm `aitask_archive.sh` actually refuses in that state (`GATE_PENDING:review_approved`, exit 2) — the guard's real caller, which the unit tests exercise only via `archive-ready`.
- [ ] Confirm re-signing with `ait gate pass` after the code change re-opens archival, and the task then archives normally.
- [ ] Confirm the attended lane is unaffected: run a normal `fast`-profile task through Step 8 review and Step 9 archival with no `.aitask-gates/` witness present, and verify nothing re-pends.
- [ ] Confirm the board's gate badge / `ait ls` behavior for a task with a stale signature matches the documented ledger-only split (badge may read ready; archival still blocks).
