---
priority: medium
effort: medium
depends: [1377_6]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1243
created_at: 2026-08-07 13:08
updated_at: 2026-08-07 13:08
---

## Failed verification item from t1377_6

> [t1377_6] Read the updated board and minimonitor doc pages against the shipped behaviour and confirm no statement is stale

### Source

- **Manual-verification task:** `aitasks/t1377/t1377_7_manual_verification_column_features.md` (item #20)
- **Origin feature task:** t1377_6
- **Origin archived plan:** `aiplans/archived/p1377/p1377_6_column_features_documentation.md`

### Commits that introduced the failing behavior

- e8e782300 documentation: Document the board column dialog, merge and minimonitor move (t1377_6)

### Files touched by those commits

- website/content/docs/tuis/board/how-to.md
- website/content/docs/tuis/board/reference.md
- website/content/docs/tuis/minimonitor/how-to.md

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1377_7 item #20.
