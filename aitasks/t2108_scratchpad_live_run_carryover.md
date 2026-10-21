---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: []
anchor: 1681
followup_kind: carry_over
created_at: 2026-10-21 15:13
updated_at: 2026-10-21 15:13
---

Carry-over of deferred manual-verification items from t2098. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [ ] From a terminal NOT inside tmux, with the -L ait server stopped, run `bash tests/test_scratchpad_spawn_live.sh` from the repo root — exits 0 with no FAIL: lines — DEFER 2026-10-21 14:49
- [ ] Run it again from a directory outside the repo (`cd ~ && bash <repo>/tests/test_scratchpad_spawn_live.sh`) — same result, proving the test no longer depends on the invoking cwd — DEFER 2026-10-21 14:52
- [ ] After the runs, `git status` in the repo shows nothing new (no stray fixture writes) — DEFER 2026-10-21 14:52
