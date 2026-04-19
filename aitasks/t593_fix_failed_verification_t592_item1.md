---
priority: medium
effort: medium
depends: [583_2]
issue_type: bug
status: Ready
labels: [verification, bug]
created_at: 2026-04-19 12:44
updated_at: 2026-04-19 12:44
---

## Failed verification item from t583_2

> sanity check alpha (traceability retest)

### Source

- **Manual-verification task:** `aitasks/t592_smoke_mv_trace.md` (item #1)
- **Origin feature task:** t583_2
- **Origin archived plan:** `aiplans/archived/p583/p583_2_verifies_frontmatter_field_three_layer.md`

### Commits that introduced the failing behavior

- b17f8c54 feature: Add verifies frontmatter field (t583_2)

### Files touched by those commits

- .aitask-scripts/aitask_create.sh
- .aitask-scripts/aitask_fold_mark.sh
- .aitask-scripts/aitask_update.sh
- .aitask-scripts/board/aitask_board.py
- tests/test_verifies_field.sh

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t592 item #1.
