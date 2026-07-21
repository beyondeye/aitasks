---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Done
labels: []
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1193]
assigned_to: dario-e@beyond-eye.com
anchor: 1199
created_at: 2026-07-21 11:43
updated_at: 2026-07-21 17:51
completed_at: 2026-07-21 17:51
---

Carry-over of deferred manual-verification items from t1199. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [skip] Run `bash tests/test_install_create_data_dirs.sh` on macOS — SKIP 2026-07-21 17:51 no macOS/BSD host available; portability audit accepted as substitute evidence (no bash-4 or GNU-only constructs; 40/40 on Linux). Not dropped — moved to low-priority follow-up t1206, which carries the item and the audit findings
- [x] Real branch-mode recovery: on an actual branch-mode project, `rm -rf .aitask-data`, then run `ait upgrade`. Expect the hard error naming `git worktree prune && git worktree add .aitask-data aitask-data`, and `aitasks`/`aiplans` still symlinks (no real directory created in their place). — PASS 2026-07-21 17:32 auto: reproduced on a real ait-setup branch-mode project (scratch): rm -rf .aitask-data, then install.sh --force --dir (the exact command ait upgrade runs post-download) emitted the hard error naming "git worktree prune && git worktree add .aitask-data aitask-data"; aitasks/aiplans still symlinks, no real dirs created. Negative control: literal ait upgrade 0.27.0 (pre-fix installer) aborted with the opaque mkdir cannot create directory / File exists. The named recovery command restored the install (rc=0). Caveat: the fixed installer is unreleased (installed v0.28.0 = latest), so ait upgrade could not download it.
