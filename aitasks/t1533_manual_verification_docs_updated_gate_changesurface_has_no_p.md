---
priority: medium
effort: medium
depends: [1263]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1263]
anchor: 635
followup_kind: manual_verification
created_at: 2026-08-16 18:53
updated_at: 2026-08-16 18:53
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1263

## Verification Checklist

- [ ] Run the docs_updated gate on a task in a checkout that also holds another session's dirty files; confirm SKILL.md §2b lists the unattributable (UNKNOWN:) paths with the reason for each and asks before proposing any doc edit
- [ ] Confirm §4 presents the TASK:-attributed file list alongside the proposed doc changes, so a concurrent edit to a plan-named file is visible before doc edits land
- [ ] Confirm an autonomous / non-interactive profile excludes UNKNOWN: paths without prompting, and records the exclusion in the gate sidecar log
- [ ] Confirm the sidecar log records the BASELINE: and PLANSCOPE: header values plus per-class counts, so a pass/skip verdict is auditable after the fact
- [ ] Confirm a real ait-driven fresh claim writes .aitask-gates/<id>/change_baseline, and that a reclaim of the same task leaves that file untouched
- [ ] Confirm the gate no longer proposes doc edits derived from another task's files — the original t635_27 symptom that motivated t1263
