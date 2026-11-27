---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [doc_quality, workflow, skills]
gates: [risk_evaluated]
anchor: 2258
created_at: 2026-11-27 11:21
updated_at: 2026-11-27 11:21
---

## Origin

Deferred from t2369 (decision taken with the user during its planning): the shadow concern-picker preamble was left out of t2369, which made task-workflow Step 8 authoritative for documentation feedback instead.

## Problem

When concerns are forwarded from a shadow agent to a coding agent, the payload starts with `DEFAULT_PREAMBLE` (`.aitask-scripts/monitor/concern_parser.py`, used by `build_clipboard_payload`): "I have some concerns: please verify them and if valid please address them". During t2258_10 the user added by hand an instruction to treat the concerns as findings and to write fixes under the documentation guide.

Since t2369, Step 8's `doc-review.md` (`## Applying feedback to documentation`) applies those rules to forwarded concerns and typed feedback alike, so this is a convenience, not a correctness fix.

## Goal

When the receiving task or the forwarded concerns are known to concern documentation, add this instruction to the payload automatically, keeping the payload editable and ordinary forwarding unchanged:

"Treat these as review findings to investigate. Verify factual claims against the implementation, then express confirmed fixes using the repo's rules for each page's type and reader level. Put details on the page that owns them. Re-review the final changed pages before asking to commit."

## Open question

How a forward is known to concern documentation. Options considered in t2369's planning: wording that only applies when a fix touches documentation (no detection, every payload longer); detecting documentation paths in the selected concerns' region or body; reading the followed task. Decide this first.

## Starting points

- `.aitask-scripts/monitor/concern_parser.py` (`DEFAULT_PREAMBLE`, `build_clipboard_payload`)
- `.aitask-scripts/monitor/monitor_shared.py`, `minimonitor_app.py`, `monitor_app.py` (callers)
- `tests/test_concern_parser.py`, `tests/test_monitor_concern_action.py`, `tests/test_minimonitor_concern_action.py`
- `.claude/skills/task-workflow/doc-review.md`
