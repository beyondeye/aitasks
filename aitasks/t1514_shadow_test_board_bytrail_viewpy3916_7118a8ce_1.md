---
priority: low
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [shadow-concern]
anchor: 1210
followup_kind: review_finding
created_at: 2026-08-13 21:35
updated_at: 2026-08-13 21:35
---

Spun off from a shadow review concern on t1505_1.

- [low | test_board_bytrail_view.py:3916] test_banner_is_unchanged_when_no_hint_is_present claims to compare the no-depth banner against the pre-t1505_1 ladder, but at line 3935 its “reference” is produced by the same current app._trail_banner() under test and then compared to the current _refresh_subtitle() call path. Any future regression that changes _trail_banner's no- depth output changes both values, so the test still passes and does not protect the all-existing-trails compatibility contract the plan explicitly calls out. Use independent expected strings or a test-local copy of the old ladder for the width cases instead. Disposition: follow-up. Verified: CONFIRMED.
