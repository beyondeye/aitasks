---
priority: medium
effort: medium
depends: [t2074_3, t2074_9]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [t2074_3, t2074_9]
anchor: 2074
followup_kind: manual_verification
created_at: 2026-10-20 12:54
updated_at: 2026-10-20 17:01
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t2074_3] Fresh interactive `ait setup` in a temp repo, with and without `origin`: data worktree and symlinks are created, and `aitask_data_layout.sh` reports `REPO:branch` / `PATHS:ready`
- [ ] [t2074_3] Point the primary `aitasks` symlink at another existing directory, then run `ait setup`: it does not report "already configured", it repairs the link, and the old directory's contents are untouched
- [ ] [t2074_3] Delete `.aitask-data` while its registration remains, then run interactive `ait setup`: it asks for confirmation ("if you moved .aitask-data, answer no…"); after "yes" the layout reads `branch` / `ready`. The non-interactive run refuses with instructions
- [ ] [t2074_3] Delete `.aitask-data` and its registration, then run `ait setup`: it restores from the local branch with a plain `worktree add`. Repeat with only the remote branch present
- [ ] [t2074_3] Move `.aitask-data` aside while a staged change sits in its index, then run `ait setup`: it refuses and prints repair/inspect instructions; `git worktree repair <moved path>` re-links it, and the staged change is still there
- [ ] [t2074_3] Run setup repair while an unrelated linked worktree has been moved aside: that worktree's registration and staged index survive, and `git worktree repair` still re-links it
- [ ] [t2074_9] Put `.aitask-data` on a different branch (or point it at a foreign repo or clone): `./ait git status`, `./ait ls` and `./ait update` refuse, each naming its recovery
- [ ] [t2074_9] In an unlinked crew worktree: `./ait git status` works, while `./ait ls` and a task write refuse with the `--link-worktree` instruction, and no real `aitasks/` dir appears
- [ ] [t2074_9] Mid-bisect in the data worktree: `./ait git bisect reset` works
- [ ] [t2074_9] On a broken layout, `./ait ls --help` and `aitask_query_files.sh --help` still print help
- [ ] [t2074_9] Board on a broken branch layout refuses at startup with the recovery text. Switch the data worktree's branch while the board is open: the next edit, revert or delete refuses
- [ ] [t2074_9] A legacy project (real `aitasks/` on the code branch) still works exactly as before: setup decline, `./ait git`, `./ait ls`, writes, and the board
