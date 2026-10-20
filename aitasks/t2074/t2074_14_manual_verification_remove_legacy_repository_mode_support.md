---
priority: medium
effort: medium
depends: [t2074_13]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [2074_3, 2074_9, 2074_10]
anchor: 2074
followup_kind: manual_verification
created_at: 2026-10-20 12:54
updated_at: 2026-10-20 12:54
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t2074_3] Run every test named in the task file.
- [ ] [t2074_3] Run `shellcheck .aitask-scripts/aitask_setup.sh install.sh`.
- [ ] [t2074_3] By hand: a fresh `ait setup` in temp repos, with and without `origin`.
- [ ] [t2074_9] Run every bash test individually and the full Python suite (last line must
- [ ] [t2074_9] Run `aitask_skill_verify.sh` and the render goldens.
- [ ] [t2074_9] Run `shellcheck`.
- [ ] [t2074_9] By hand, in a temp legacy repo: confirm the refusal, then convert it with
- [ ] [t2074_3] Interactive (TTY) `ait setup` in a fresh temp repo: there is no data-branch opt-out prompt; it ends with the `.aitask-data` worktree plus symlinks, and `aitask_data_layout.sh` reports branch/ready
- [ ] [t2074_3] Interactive `ait setup` in a real legacy project: one migration confirmation; answering "n" exits non-zero and `diff -r` shows nothing changed; answering "y" converts with the data byte-identical
- [ ] [t2074_3] Point the primary `aitasks` symlink at another existing directory, then run `ait setup`: the link is repaired, and the old directory's contents are untouched
- [ ] [t2074_3] `ait upgrade` in a legacy project prints the conversion notice and does not migrate
- [ ] [t2074_9] In a legacy temp repo, `./ait ls`, `./ait git status` and `./ait update` each print the state-specific refusal naming `ait setup`
- [ ] [t2074_9] In an unlinked crew worktree, `./ait git status` works, while a task write refuses with the `--link-worktree` instruction and creates no real `aitasks/` directory
- [ ] [t2074_9] Run `/aitask-pickrem` in a fresh clone of a legacy repo: Step 0a stops with the Stopped banner (NEEDS_CONVERSION)
- [ ] [t2074_10] Open `ait board` on a broken-layout fixture: it shows a refusal with the recovery text, and no git command runs against the code repo
- [ ] [t2074_10] The `ait syncer` row for a broken or unconverted layout shows the reworded status and recovery
