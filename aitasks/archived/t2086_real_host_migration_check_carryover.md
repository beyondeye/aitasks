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
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: carry_over
created_at: 2026-10-21 08:22
updated_at: 2026-10-21 11:14
completed_at: 2026-10-21 11:14
---

Carry-over of deferred manual-verification items from t1931. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [x] macOS: run `bash tests/test_aitasks_home.sh` and confirm ALL TESTS PASSED (BSD `stat -f`, `mv -n`, `sort -z`, `ln -s`, and `find -print0` paths). — PASS 2026-10-21 11:12 auto: macOS (Darwin 24.6) bash tests/test_aitasks_home.sh → 236 passed, 0 failed, ALL TESTS PASSED, exit 0; H8 cross-device skipped (no /dev/shm), not counted
- [x] macOS: repeat the real-host migration and the TUI checks above. — PASS 2026-10-21 11:14 auto: macOS real home (4 tenants) backed up to ~/.aitask.bak; ait engine home --migrate → HOME_MIGRATED:4, exit 0, ~/.aitask -> ~/.aitasks; board boots on PyPy (~/.aitask/pypy_venv), monitor boots on venv (private tmux socket); both venv/bin/python and bin/python3 print 1; ait setup v0.38.0 in a scratch project exit 0, no HOME_LEGACY:, deps reinstalled into both venvs via symlink; rerun → HOME_SKIPPED:already-migrated, ~/.aitasks fingerprint unchanged
