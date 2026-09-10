---
priority: medium
effort: low
depends: [1771]
issue_type: manual_verification
status: Ready
labels: [shadow, verification, manual]
verifies: [1771]
anchor: 1771
followup_kind: risk_mitigation
created_at: 2026-09-10 12:16
updated_at: 2026-09-10 12:16
---

## Origin

Risk-mitigation ("after") follow-up for t1771, created at Step 8d after implementation landed.

## Manual Verification Task

This task is handled by the manual-verification module: run `/aitask-pick <id>` and the workflow will dispatch to the interactive checklist runner. Each item below must reach a terminal state (Pass / Fail / Skip) before the task can be archived; Defer is allowed but creates a carry-over task.

**Related to:** t1771

## Risk addressed

all three goal-achievement risks of t1771's plan:

- The deliverable is **agent-behavioural**: whether a running shadow actually routes `>i3` to Advanced without prompting, and never volunteers the task summary. Every test in the plan pins *rendered prose*, which is a proxy, not proof — a correct-looking rendered instruction can still be mis-followed. · severity: medium
- The Step 0 greeting is generated at runtime from Step 3, so "the greeting lists every capability with its code" is only checkable by running a shadow; Test 2s proves the codes and the rule text are *present to be derived from*, no more. · severity: medium
- `>t`'s degrade paths (no task id; `PLAN_FILE:NOT_FOUND`) are instructions, not code, and are the states a real session hits most often. · severity: low

## Goal

Launch a shadow from minimonitor (`e`) against a live agent working a task under the `fast` profile (`shadow_impl_review_tier: advanced`) and drive the eight checklist items below by typing the shortcodes into the shadow pane. Each item is a behaviour a rendered-text assertion cannot prove. For the plan-mode item, pick a followed agent that is still inside `EnterPlanMode` (its plan exists only as `~/.claude/plans/<name>.md`). For the tier item use `>i1` or `>i4`, not `>i3` — `fast` already configures advanced, so `>i3` would pass even if the digit were ignored.

Source: `.claude/skills/aitask-shadow/SKILL.md.j2` (Step 0, Step 3 "Shortcodes"), `impl-challenge.md` ("Tier selection"), `task-summarize.md`; landed in commit e16f9a27c.
