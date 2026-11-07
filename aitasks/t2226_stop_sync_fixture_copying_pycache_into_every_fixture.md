---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [sitrep]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
followup_kind: upstream_defect
created_at: 2026-11-07 19:32
updated_at: 2026-11-07 22:28
---

## Origin
Spawned from t2215 during Step 8b review.

## Upstream defect
- `tests/lib/sync_fixture.sh:96` — `cp -r "$PROJECT_DIR/.aitask-scripts" ./.aitask-scripts` copies the gitignored `__pycache__` dirs (~11 MB in a working checkout: 24 MB vs 13 MB clean) into every fixture. `tests/test_sync_deferral_and_quarantine.sh` then writes ~2 GB to `/tmp` from a real checkout (~1 GB from a clean tree) and exhausts the per-user tmpfs quota (`/tmp` is mounted with `usrquota`). That truncates logs at 4096 bytes and fails sync tests under parallel load.
- `tests/test_goengines_build.sh:54` — `out="$("$BUILD" --version 9.9.9-test … 2>/dev/null)"` under `set -euo pipefail`. A toolchain failure makes the test exit 1 with no output at all (no FAIL line, no Results line), so the cause is invisible.

## Diagnostic context
From t2215's post-phase sweep (archived plan `aiplans/archived/p2215_*`):
- Under `xargs -P4`, every failure of `test_task_push`, `test_sync_guarded_merge`, `test_sync_rebase_gate`, `test_sync_fetch_exclusion`, `test_verified_update` and `test_sync_deferral_and_quarantine` had `Disk quota exceeded` in its log. All passed alone, except `test_sync_deferral_and_quarantine`, which failed alone from the real checkout twice.
- Measured peak `/tmp` growth for `test_sync_deferral_and_quarantine.sh`: 2060 MB from the real checkout and 1065 MB from a clean worktree. After copying the same ignored `__pycache__` dirs into the clean worktree it grew by 2030 MB, hit the quota, and truncated at the same test (Test 37). The ignored caches are the whole difference.
- The quota is per user and shared with every concurrent session, so the available headroom changes from run to run.
- `test_goengines_build.sh` failed with rc 1 and an empty log on this machine because of a local Go toolchain mismatch (`compile: version "go1.27.3" does not match go tool version "go1.27.3-X:nodwarf5"`). The mismatch itself is environmental; the defect is that the test hides it.

## Suggested fix
- sync_fixture: copy the scripts without the caches, e.g. `git -C "$PROJECT_DIR" ls-files -z .aitask-scripts | …` / `tar --exclude=__pycache__`, or `cp -r` followed by pruning `__pycache__` (and `*.pyc`). Check the other fixture helpers that `cp -r "$PROJECT_DIR/.aitask-scripts"` for the same issue (grep `tests/lib/` and `tests/`). Add a regression check that a fixture's `.aitask-scripts` has no `__pycache__`.
- test_goengines_build: let the build's stderr through, or capture it and print it on failure, so a broken toolchain shows up as a named FAIL rather than a silent rc 1.
