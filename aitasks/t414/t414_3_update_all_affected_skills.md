---
priority: medium
effort: low
depends: [t414_2]
issue_type: bug
status: Implementing
labels: [task_workflow]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-17 18:53
updated_at: 2026-03-22 22:04
---

## Goal

After t414_2 confirms the simplified procedure works in aitask-changelog, roll out the same pattern to all other skills that use the satisfaction feedback procedure.

## Context

The satisfaction-feedback.md changes from t414_1 apply automatically since all skills reference the same procedure file. However, some skills may have their own inline satisfaction feedback code or non-standard invocations that need updating.

## Skills to Audit

Check each of these for any custom/inline satisfaction feedback code that bypasses satisfaction-feedback.md:

1. **task-workflow** (Step 9b) — `.claude/skills/task-workflow/SKILL.md`
2. **aitask-explore** — `.claude/skills/aitask-explore/SKILL.md`
3. **aitask-explain** — `.claude/skills/aitask-explain/SKILL.md`
4. **aitask-wrap** — `.claude/skills/aitask-wrap/SKILL.md`
5. **aitask-refresh-code-models** — `.claude/skills/aitask-refresh-code-models/SKILL.md`
6. **aitask-reviewguide-classify** — `.claude/skills/aitask-reviewguide-classify/SKILL.md`
7. **aitask-reviewguide-merge** — `.claude/skills/aitask-reviewguide-merge/SKILL.md`
8. **aitask-reviewguide-import** — `.claude/skills/aitask-reviewguide-import/SKILL.md`
9. **aitask-web-merge** — `.claude/skills/aitask-web-merge/SKILL.md`

Also check the non-Claude-Code agent equivalents:
- `.gemini/skills/` — any satisfaction feedback references
- `.agents/skills/` — any satisfaction feedback references
- `.opencode/skills/` — any satisfaction feedback references

## Changes

- Fix any inline satisfaction feedback code that doesn't use the simplified procedure
- Ensure all skills reference satisfaction-feedback.md consistently (no custom invocations)

## Verification

Spot-check 2-3 skills by running them and confirming the satisfaction feedback step works on first attempt.
