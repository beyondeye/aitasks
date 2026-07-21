---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Implementing
labels: []
verifies: [1193]
assigned_to: dario-e@beyond-eye.com
anchor: 1199
created_at: 2026-07-21 11:43
updated_at: 2026-07-21 17:27
---

Carry-over of deferred manual-verification items from t1199. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [ ] Run `bash tests/test_install_create_data_dirs.sh` on macOS — DEFER 2026-07-21 11:36 auto: requires a macOS/BSD host; Linux cannot execute the BSD compatibility test
- [ ] Real branch-mode recovery: on an actual branch-mode project, `rm -rf .aitask-data`, then run `ait upgrade`. Expect the hard error naming `git worktree prune && git worktree add .aitask-data aitask-data`, and `aitasks`/`aiplans` still symlinks (no real directory created in their place). — DEFER 2026-07-21 11:36 auto: isolated branch-mode guard emitted the expected recovery command and preserved symlink; literal ait upgrade requires an installed branch-mode project
