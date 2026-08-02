---
priority: medium
effort: medium
depends: [1312]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1312]
created_at: 2026-07-29 18:38
updated_at: 2026-07-29 18:38
boardidx: 690
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1312

## Verification Checklist

- [ ] Run /aitask-explore under the `fast` profile with an intent yielding one NEW label and one NEAR-duplicate of an existing one; confirm the Step 3a prompt fires and carries the classification (existing / near / new) INSIDE the question text, not as same-turn prose before the widget.
- [ ] Confirm the "Use the suggested existing labels" option appears ONLY when at least one NEAR: candidate exists, and that choosing it substitutes the existing label instead of minting a separator variant.
- [ ] Confirm "Edit labels" (the Other free-text option) is honoured verbatim, and the typed list is still sanitized at creation time.
- [ ] On the task created by that run: `git show --name-only HEAD` contains BOTH the task file and aitasks/metadata/labels.txt, and the new label is present in labels.txt.
- [ ] Re-run the same flow with `/aitask-explore --profile remote`: confirm NO label AskUserQuestion is emitted at all, and that labels not already in the vocabulary are reported as dropped rather than silently discarded.
- [ ] Open `ait settings`: confirm `explore_label_confirm` appears under the "Exploration" group with the three enum values (ask / auto / existing_only) and its help text, and that changing and saving it round-trips into the profile YAML.
- [ ] Run `ait update <id>` interactively and mint a new label via the fzf ">> Add new label" entry: confirm the label is selected for the task and that labels.txt is committed together with the task file (worktree clean afterwards), accepting the known cosmetic deviation that the new label does not reappear in the same session's picker.
