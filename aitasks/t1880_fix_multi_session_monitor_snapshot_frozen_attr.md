---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [framework, skills, documentation]
gates: [risk_evaluated]
anchor: 1869
followup_kind: upstream_defect
created_at: 2026-09-25 07:29
updated_at: 2026-09-25 07:29
---

## Origin

Spawned from t1874 during Step 8b review.

## Upstream defect

- `tests/test_multi_session_monitor.sh:46 — the SimpleNamespace snapshot fixture lacks the `frozen` attribute that monitor_app._format_agent_card_text (monitor_app.py:1756) reads since t1705_7 (fcf144025), so the test crashes with AttributeError on HEAD independent of t1874`

## Diagnostic context

While verifying t1874 (list-panes -s session-scope targets),
`bash tests/test_multi_session_monitor.sh` exited 1 with:

    File ".aitask-scripts/monitor/monitor_app.py", line 1756, in _format_agent_card_text
        if snap.frozen:
    AttributeError: 'types.SimpleNamespace' object has no attribute 'frozen'

The same failure reproduced in an isolated copy of the tree with t1874's four
source files and the test restored to their HEAD versions, so it predates
t1874. `git log -L` places the `if snap.frozen:` read in fcf144025
("Render frozen agents and widen the P filter to cover them", t1705_7); the
test's hand-built `SimpleNamespace` snapshot was never given the new field.

## Suggested fix

Give the fixture snapshot `frozen=False` (and audit it for any other
TmuxPaneInfo / snapshot fields `_format_agent_card_text` now reads), or build
it from the real snapshot type so new fields default instead of crashing.
Then check that the test's other blocks still pass.
