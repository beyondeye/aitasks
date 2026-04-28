---
priority: medium
effort: medium
depends: [637]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [637]
created_at: 2026-04-24 07:39
updated_at: 2026-04-24 07:39
boardidx: 180
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t637

## Verification Checklist

- [ ] In ../aitasks-mobile (or another project with .aitask-scripts/VERSION tracked), hand-edit aitasks/metadata/project_config.yaml to add a distinctive key (e.g. tmux.default_session: aitasks_mob_smoke), then run `ait install` and confirm the key survives the update while any brand-new seed keys are added.
- [ ] Confirm .aitask-scripts/.gitignore exists after install and `git check-ignore .aitask-scripts/board/__pycache__` returns exit 0 in the target project.
- [ ] Confirm `git log -1 --oneline` in the target project shows `ait: Update aitasks framework to v0.17.4` with the new version stamp.
- [ ] Negative test: in a scratch repo where .aitask-scripts/VERSION is NOT git-tracked, run install and confirm no commit is created and the info line "VERSION is not git-tracked — skipping" appears.
- [ ] Customize aitasks/metadata/profiles/fast.yaml (e.g. set `create_worktree: true`), run install, confirm the customization survives and any new profile keys shipped in the seed are merged in.
- [ ] Edit a tracked review guide under aireviewguides/ (e.g. append a paragraph), run install, confirm the edit is preserved (review guides must never be overwritten on update).
- [ ] Confirm one-time __pycache__ cleanup: in a project with previously-tracked __pycache__ paths, run install and verify the next commit removes them from the index (git ls-files still returns nothing for those paths).
