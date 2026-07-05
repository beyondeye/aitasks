---
priority: medium
effort: medium
depends: [1119]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1119
created_at: 2026-07-05 10:43
updated_at: 2026-07-05 10:43
---

## Failed verification item from t1119

> Launch a completed task's agent + shadow; ask "review the implementation" and confirm the emitted ===AITASK-CONCERNS=== block forwards via minimonitor's 'c' picker showing the REAL concerns (not the doc's placeholder example

### Source

- **Manual-verification task:** `aitasks/t1121_manual_verification_shadow_implementation_challenge_subproce.md` (item #1)
- **Origin feature task:** t1119
- **Origin archived plan:** `aiplans/archived/p1119_shadow_implementation_challenge_subprocedure.md`

### Commits that introduced the failing behavior

- e77b33f84 enhancement: Add shadow implementation-challenge sub-procedure (t1119)

### Files touched by those commits

- .aitask-scripts/aitask_shadow_capture.sh
- .aitask-scripts/monitor/concern_parser.py
- .claude/skills/aitask-shadow/SKILL.md
- .claude/skills/aitask-shadow/concern-format.md
- .claude/skills/aitask-shadow/impl-challenge.md
- .claude/skills/aitask-shadow/plan-assumptions.md
- .claude/skills/aitask-shadow/plan-challenge.md
- .claude/skills/aitask-shadow/plan-diagnose-errors.md
- aidocs/framework/shadow_agent.md
- tests/test_concern_parser.py
- website/content/docs/tuis/minimonitor/how-to.md
- website/content/docs/workflows/_index.md
- website/content/docs/workflows/shadow-agent.md

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1121 item #1.
