---
priority: medium
effort: medium
depends: [739]
issue_type: bug
status: Done
labels: [verification, bug]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-27 08:10
updated_at: 2026-05-27 11:10
completed_at: 2026-05-27 11:10
---

## Failed verification item from t739

> Corrupt one explorer's `_output.md` (e.g. truncate the NODE_YAML block), press `ctrl+shift+x`, verify the apply banner shows the `apply-explorer` CLI hint.

### Source

- **Manual-verification task:** `aitasks/t787_manual_verification_brainstorm_apply_explorer_output_followu.md` (item #3)
- **Origin feature task:** t739
- **Origin archived plan:** `aiplans/archived/p739_brainstorm_apply_explorer_output.md`

### Commits that introduced the failing behavior

- 4727cba3 feature: Add apply_explorer_output() and TUI auto-apply for brainstorm explorer agents (t739)

### Files touched by those commits

- .aitask-scripts/aitask_brainstorm_apply_explorer.sh
- .aitask-scripts/brainstorm/brainstorm_app.py
- .aitask-scripts/brainstorm/brainstorm_session.py
- ait
- tests/test_brainstorm_apply_explorer.py

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t787 item #3.
