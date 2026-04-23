---
priority: medium
effort: medium
depends: [617]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [617]
created_at: 2026-04-21 13:40
updated_at: 2026-04-21 13:41
boardidx: 30
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t617

## Verification Checklist

- [ ] Pass path: select "Pass" on item 1; item 1 annotated `pass`, loop advances to item 2.
- [ ] Fail path: select "Fail"; follow-up bug task created via aitask_verification_followup.sh; item 1 annotated `fail`.
- [ ] Skip path: select "Skip (with reason)"; follow-up reason AskUserQuestion appears; reason saved via `set <idx> skip --note`.
- [ ] Defer path: select "Defer"; item 1 annotated `defer`, loop advances.
- [ ] Abort via direct keyword: type `abort` in Other on item 1; no `set` call, loop ends, user sees "Task t<id> paused at item 1."; re-pick resumes item 1 unchanged.
- [ ] Abort via phrased intent: type `stop for today`, `I need to pause`, `quit and resume tomorrow`, `Abort!`; each hits the Abort branch.
- [ ] Question via Other: type `what does this item mean?`; skill answers in conversation, re-prompts same item, no state change.
- [ ] Instruction via Other: type `run the tests first`; skill performs the action, re-prompts same item, no state change.
- [ ] Defer post-loop path: after setting at least one Defer, complete remaining items; section-3 post-loop "Archive with carry-over / Stop without archiving" prompt fires unchanged.
