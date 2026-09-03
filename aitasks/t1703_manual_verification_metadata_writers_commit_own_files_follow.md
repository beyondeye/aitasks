---
priority: medium
effort: medium
depends: [1677]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1677]
anchor: 1599
followup_kind: manual_verification
created_at: 2026-09-03 12:21
updated_at: 2026-09-03 12:21
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1677

## Verification Checklist

- [ ] Edit a project-layer value in `ait settings` and save: the file is committed by that action and `./ait git status --porcelain` is clean afterwards.
- [ ] Save a board **settings** (user-layer) change in `ait settings`: nothing is committed and no toast claims otherwise.
- [ ] Create a new **project** profile in `ait settings`: the file ends up tracked and committed; repeat for a **user** profile and confirm it is created, gitignored, and NOT committed.
- [ ] Delete a project profile in `ait settings`: the deletion is committed AND the profile disappears from the UI immediately, without a reload.
- [ ] Import a config bundle in `ait settings` that both creates a new project config and overwrites a pre-existing untracked one: only the created file is committed; the overwritten one is reported refused, not silently dropped.
- [ ] Add / rename / delete / merge / reorder board columns in `ait board`: each gesture commits `board_config.json` and leaves the worktree clean.
- [ ] Start `ait board` in a project with no `board_config.json`: the file is created but NOT committed at startup.
- [ ] Run the chatlink wizard to a completed save: the summary states the config's git position and, on success, names the commit.
- [ ] With a failing pre-commit hook installed, repeat a Settings save, a board column edit and a wizard save: each reports the failure, the edit survives on disk, and the remedy command shown actually clears it when pasted (including `--allow-new` for a newly created file).
- [ ] Run `ait sync` after a committed config edit: it no longer reports the file as ownerless and does not defer.
- [ ] Navigate plans in the diffviewer: history lands in `diffviewer_history.local.json` and the tracked `diffviewer_history.json` is never rewritten.
- [ ] Run `ait setup` on a repo missing chatlink_config.yaml while another session holds a dirty `board_config.json`: only the file setup wrote is committed.
