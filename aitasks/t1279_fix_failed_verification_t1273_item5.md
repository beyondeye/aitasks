---
priority: medium
effort: medium
depends: [1268]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1210
created_at: 2026-07-28 01:18
updated_at: 2026-07-28 01:18
---

## Failed verification item from t1268

> Press `R` twice in quick succession — the second press is a no-op, and `R Agent Refresh` disappears from the footer while the launch is pending

### Source

- **Manual-verification task:** `aitasks/t1273_manual_verification_bytrail_refresh_semantics_followup.md` (item #5)
- **Origin feature task:** t1268
- **Origin archived plan:** `aiplans/archived/p1268_bytrail_refresh_semantics_and_key_footer_contract.md`

### Commits that introduced the failing behavior

- ceb07381d bug: Fix By-Trail refresh semantics and key/footer contract (t1268)

### Files touched by those commits

- .aitask-scripts/board/aitask_board.py
- tests/test_board_bytrail_view.py

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1273 item #5.
