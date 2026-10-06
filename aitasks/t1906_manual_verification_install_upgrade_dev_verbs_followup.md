---
priority: medium
effort: medium
depends: [1852_5]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1852_5]
anchor: 1852
followup_kind: manual_verification
created_at: 2026-10-06 23:07
updated_at: 2026-10-06 23:07
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1852_5

## Verification Checklist

- [ ] On a quiet host (stop the dedicated `-L ait` tmux server: `tmux -L ait kill-server`, after saving work), from a terminal NOT inside tmux, run `bash tests/test_frozen_agents_acceptance.sh` and confirm it exits 0 (it was deferred from t1852_5's install_regression_sweep)
- [ ] In that run's output, confirm the install.sh --local-tarball step prints `TESTMAP_BINARY:skipped` (offline install: no engine fetch) and no network call is attempted
