---
priority: medium
effort: medium
depends: [1644]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1644]
assigned_to: dario-e@beyond-eye.com
anchor: 1210
followup_kind: manual_verification
created_at: 2026-08-31 19:24
updated_at: 2026-08-31 19:31
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1644

## Verification Checklist

- [ ] Run `/aitask-trail --show art:trail-gates-framework-landing` and confirm the print ends with the depth, the overview and the board pointer, and carries NO wave/relation recap (the show flow already rendered the document in full immediately above).
- [ ] Run `/aitask-trail --refresh` on a deep trail carrying mixed-provenance relations (`art:trail-gates-framework-landing` has `verifies` 4 fact / 1 advisory and `informs` 16 fact / 1 advisory) and confirm each mixed type splits into two separately labelled `<type> · <provenance>:` groups.
- [ ] On that same 56-relation trail, confirm all five relation types (hard_depends, advisory_precedes, coordinates_with, verifies, informs) get endpoint groups, and that the relations block stays around 30 lines rather than one line per edge.
- [ ] Create or refresh a trail at lite depth and confirm the relations line reads exactly `Relations: none recorded at this depth (lite trails omit them).` — not `Relations (0):` and not an empty heading.
- [ ] Confirm entry and relation task refs print verbatim (`aitasks#635_27`), never shortened to `635_27`, including for any cross-repo member.
- [ ] In `ait board`, press `z`, then `s`, then `v`, then `Enter` on a member card, and confirm each key does what the run summary's board pointer line claims it does.
