---
priority: medium
effort: medium
depends: [1274]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1274]
created_at: 2026-07-28 12:55
updated_at: 2026-07-28 12:55
boardidx: 64512
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1274

## Verification Checklist

- [ ] In a real minimonitor companion pane, with a shadow that produced an implementation review containing at least one informational and one non-informational concern: press 'c' and confirm the picker shows a "Needs addressing" and an "Informational" section, with the informational rows dimmed.
- [ ] Confirm 'a' (select all) ticks only the actionable rows and leaves informational ones unticked, while 'A' (copy all) still copies every concern.
- [ ] Confirm each row shows BOTH its region title and body text at the real companion-pane width, including a region longer than ~20 characters (e.g. authoring-conv.md:103) that previously rendered as a bare priority badge.
- [ ] Paste the forwarded clipboard payload into the followed agent and confirm each concern still carries its "Disposition: ..." and "Verified: ..." trailer verbatim, even though the picker row hid them.
- [ ] Confirm the auto-offer toast names the split, e.g. "Shadow raised 2 concern(s) (+1 informational) - press 'c' to pick".
- [ ] Confirm a plan-review block (whose producers emit no disposition trailer) shows NO section headers and behaves exactly as before.
- [ ] Confirm a concern emitted with no region renders "(no region)" rather than a blank title.
- [ ] With a shadow block whose marker lines are all malformed, confirm minimonitor warns that the block could not be parsed instead of reporting "No concerns detected", on both the 'c' hotkey and the auto-offer.
