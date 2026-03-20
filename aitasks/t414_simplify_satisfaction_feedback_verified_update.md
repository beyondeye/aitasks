---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [task_workflow]
children_to_implement: [t414_2, t414_3]
created_at: 2026-03-17 18:52
updated_at: 2026-03-18 09:42
boardcol: now
boardidx: 70
---

## Problem

The Satisfaction Feedback Procedure (`.claude/skills/task-workflow/satisfaction-feedback.md`) requires agents to follow a 3-file chain to record a satisfaction score:
1. satisfaction-feedback.md → references model-self-detection.md
2. model-self-detection.md → instructs agent to call `aitask_resolve_detected_agent.sh`
3. Then call `aitask_verified_update.sh` with the resolved agent string

In context-heavy skills like aitask-changelog (which reads many task descriptions and plans), agents often fail to follow this chain — hallucinating script names or guessing wrong argument formats. This was observed in a real execution where the agent tried 7 times before succeeding.

## Root Cause

Too many indirections for a simple "record a score" operation. The agent must read 2 procedure files, call 2 scripts, and parse intermediate output. Context-heavy skills are especially vulnerable because by the time satisfaction feedback runs (end of workflow), the context is saturated.

## Solution

1. Add `--agent` and `--cli-id` flags to `aitask_verified_update.sh` as alternatives to `--agent-string`. When these flags are provided, the script internally calls `aitask_resolve_detected_agent.sh` to resolve the agent string.

2. Simplify `satisfaction-feedback.md` by inlining the self-detection instructions and using the new flags. Eliminate the reference to `model-self-detection.md`. The agent's job becomes: self-identify (from in-context info) → call one script.

3. Update all 10 callers: task-workflow (Step 9b), aitask-explore, aitask-explain, aitask-changelog, aitask-wrap, aitask-refresh-code-models, aitask-reviewguide-classify, aitask-reviewguide-merge, aitask-reviewguide-import, aitask-web-merge.

## Related

- t401 (More Robust Self-Detection) — created `aitask_resolve_detected_agent.sh`, which this task builds upon
- t303 (Automatic Update of Model Verified Score) — created the original procedure and script
