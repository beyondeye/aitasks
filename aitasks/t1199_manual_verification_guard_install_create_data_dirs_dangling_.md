---
priority: medium
effort: medium
depends: [1193]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1193]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-21 11:07
updated_at: 2026-07-21 11:12
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1193

## Verification Checklist

- [ ] Run `bash tests/test_install_create_data_dirs.sh` on macOS — the guard uses plain `readlink` (no `-f`) and `grep -qE`, both BSD-safe by inspection but never executed on a BSD box. Expect 40 passed, 0 failed.
- [ ] Real branch-mode recovery: on an actual branch-mode project, `rm -rf .aitask-data`, then run `ait upgrade`. Expect the hard error naming `git worktree prune && git worktree add .aitask-data aitask-data`, and `aitasks`/`aiplans` still symlinks (no real directory created in their place).
- [ ] Fresh install into a non-git directory containing a dangling canonical `aitasks -> .aitask-data/aitasks` symlink. Expect the "Replacing dangling symlink" warning, a completed install, and NO `fatal: not a git repository` noise in the output.
- [ ] Install a genuine release tarball (not hand-built) into a fresh dir and confirm the guard is a no-op — the `aitasks`/`aiplans` symlinks are gitignored, so a real `git archive` release should never carry them.
