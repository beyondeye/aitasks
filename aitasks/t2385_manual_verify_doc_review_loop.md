---
priority: medium
effort: medium
depends: [2369]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [2369]
premise_baseline: 251595ebb3deb534c2d40600297359c03aad28ae @ 2026-11-27 11:21
anchor: 2258
followup_kind: manual_verification
created_at: 2026-11-27 11:21
updated_at: 2026-11-27 11:21
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t2369

## Verification Checklist

- [ ] On a real task that changes a documentation page, type feedback about that page at the Step 8 review prompt ("Need more changes"); check the agent verifies it against the code first, fixes the page that owns the detail, reports a resolution per item, and re-reviews the changed pages before the next prompt
- [ ] On the same kind of task, forward a concern from a shadow agent (minimonitor c); check the agent handles it the same way as typed feedback
- [ ] While the review prompt is open, edit one of the task's documentation pages by hand, then choose "Commit changes"; check nothing is committed and the review prompt returns with a refreshed documentation review
- [ ] Choose "Commit changes" with nothing changed; check the code commit is made behind the guard (GUARD:clean in the output) and the plan commit follows
- [ ] On a task with a passed docs_updated gate, edit an applied page and reach Step 8; check that page is reviewed again and the untouched pages only get the claim check
- [ ] Run a task that changes no documentation; check the review prompt shows no documentation block and no extra question
- [ ] Check the review prompt's question text starts with the per-page level/prose/reader/claims summary and lists each unresolved finding with its disposition
