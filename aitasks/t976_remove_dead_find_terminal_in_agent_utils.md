---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: refactor
status: Implementing
labels: [codebrowser, codeagent]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-11 12:47
updated_at: 2026-06-11 13:07
---

## Origin

Spawned from t974 during Step 8b review.

## Upstream defect

`.aitask-scripts/codebrowser/agent_utils.py:9 — find_terminal() is dead code`
(both codebrowser consumers now import `find_terminal` from
`agent_launch_utils`; the `agent_utils` copy has no remaining importers).

## Diagnostic context

While fixing t974 (detaching TUI-spawned agents), every terminal-spawn site
was traced. `codebrowser/codebrowser_app.py` and `codebrowser/history_screen.py`
both import `find_terminal` (aliased `_find_terminal`) from
`agent_launch_utils`, not from the local `agent_utils`. A grep confirmed
`codebrowser/agent_utils.py::find_terminal` has no importers anywhere — it is a
stale duplicate of `agent_launch_utils.find_terminal`.

## Suggested fix

Remove `find_terminal()` from `.aitask-scripts/codebrowser/agent_utils.py`
(keep `resolve_agent_binary`, which is still imported). Verify no importers
remain (`grep -rn "agent_utils import.*find_terminal\|agent_utils.find_terminal"
.aitask-scripts/`) before deleting.
