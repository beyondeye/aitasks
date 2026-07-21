---
priority: medium
effort: medium
depends: [1193]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1193]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-21 11:07
updated_at: 2026-07-21 11:36
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1193

## Verification Checklist

- [defer] Run `bash tests/test_install_create_data_dirs.sh` on macOS — DEFER 2026-07-21 11:36 auto: requires a macOS/BSD host; Linux cannot execute the BSD compatibility test
- [defer] Real branch-mode recovery: on an actual branch-mode project, `rm -rf .aitask-data`, then run `ait upgrade`. Expect the hard error naming `git worktree prune && git worktree add .aitask-data aitask-data`, and `aitasks`/`aiplans` still symlinks (no real directory created in their place). — DEFER 2026-07-21 11:36 auto: isolated branch-mode guard emitted the expected recovery command and preserved symlink; literal ait upgrade requires an installed branch-mode project
- [x] Fresh install into a non-git directory containing a dangling canonical `aitasks -> .aitask-data/aitasks` symlink. Expect the "Replacing dangling symlink" warning, a completed install, and NO `fatal: not a git repository` noise in the output. — PASS 2026-07-21 11:36 auto: genuine v0.28.0 tarball installed in fresh non-git temp dir; warning emitted, exit 0, no git noise
- [x] Install a genuine release tarball (not hand-built) into a fresh dir and confirm the guard is a no-op — PASS 2026-07-21 11:36 auto: v0.28.0 release tarball (840 entries) contains no aitasks/aiplans symlink entries
