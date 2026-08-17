---
priority: medium
effort: medium
depends: [t1555_3]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1555_1, 1555_2, 1555_3]
anchor: 1538
followup_kind: manual_verification
created_at: 2026-08-17 19:00
updated_at: 2026-08-17 19:00
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1555_1] On a real repo, run `aitask_verification_stale.sh check` against a task whose curated file was genuinely modified since its baseline, and confirm DECISION:ASK_STALE with a CHANGED: line naming the correct culprit task id
- [ ] [t1555_1] Delete a curated file for real, then confirm DECISION:ASK_STALE with a DELETED: line naming the culprit commit — and confirm a history-only reading would have missed it (git log -- <path> still returns commits for the deleted path)
- [ ] [t1555_1] Confirm the negative control live: a task whose curated files are untouched reports DECISION:FRESH (a detector that cannot say FRESH is the failure mode the design exists to avoid)
- [ ] [t1555_2] Land a real task through Step 8c end to end and confirm the candidate shortlist is offered, that narrowing drops incidental hub files, and that both file_references: and verification_baseline: are written to the new task
- [ ] [t1555_2] Confirm that on a non-promptable profile no fields are written, no prompt appears, and the flow does not stall
- [ ] [t1555_3] Pick the seeded manual-verification task in a real terminal after modifying one curated file, and confirm the pre-check prompt appears BEFORE the autonomous-verification offer (step 1.5), not after
- [ ] [t1555_3] Answer "Proceed unchanged", then re-pick the same task and confirm the prompt does NOT re-fire (the baseline advanced)
- [ ] [t1555_3] Answer "Amend the checklist", abandon the edit midway, and confirm the task file is unchanged — neither the items nor the baseline advanced
- [ ] [t1555_1] Hand-edit a curated `file_references:` entry to a bogus path, then pick the task and confirm the pre-check RAISES a prompt naming that path (never a silent FRESH) — a bad scope entry must not reach the verification loop unnoticed
