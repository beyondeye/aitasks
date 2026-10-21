---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: []
anchor: 1852
followup_kind: carry_over
created_at: 2026-10-21 08:22
updated_at: 2026-10-21 08:22
---

Carry-over of deferred manual-verification items from t1931. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [ ] macOS: run `bash tests/test_aitasks_home.sh` and confirm ALL TESTS PASSED (BSD `stat -f`, `mv -n`, `sort -z`, `ln -s`, and `find -print0` paths). — DEFER 2026-10-20 19:42 auto: needs a macOS host; this host is Linux
- [ ] macOS: repeat the real-host migration and the TUI checks above. — DEFER 2026-10-20 19:42 auto: needs a macOS host; this host is Linux
