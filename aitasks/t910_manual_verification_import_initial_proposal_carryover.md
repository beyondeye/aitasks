---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: []
verifies: [t573_1, t573_2, t573_3, t573_4]
created_at: 2026-06-02 12:30
updated_at: 2026-06-02 12:30
boardcol: manual_verifications
boardidx: 110
---

Carry-over of deferred manual-verification items from t573_5. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [ ] [t573_3] Imported source file mtime and md5 are unchanged after the full flow. — DEFER 2026-06-02 12:24 user: deferred for later (not verified this session)
- [ ] [t573_3] Simulated initializer failure (malformed _output.md) surfaces as an error-severity notification; the placeholder n000_init is retained and the TUI remains usable. — DEFER 2026-06-02 12:25 user: deferred for later (not verified this session)
- [ ] [t573_3] Running outside tmux (unset TMUX) still reaches Completed via the headless fallback. — DEFER 2026-06-02 12:28 user: deferred for later (not verified this session)
