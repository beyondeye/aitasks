---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: []
verifies: [t1823_1, t1823_2, t1823_3, t1823_4, t1823_5]
anchor: 1823
followup_kind: carry_over
created_at: 2026-09-18 17:26
updated_at: 2026-09-18 17:26
---

Carry-over of deferred manual-verification items from t1823_6. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [ ] [t1823_4] Rapid Esc (several presses) on the Discuss agent dialog, its model picker and its profile editor leaves `ait brainstorm <N>` running on the Browse tab; a rapid-Esc on the same dialogs in one other host TUI (e.g. board or codebrowser) also leaves that TUI up — DEFER 2026-09-18 17:05 brainstorm half PASSED (rapid Esc from Discuss dialog, model picker, profile editor → alive on Browse); other-host half (board p / codebrowser e) still to check by hand
