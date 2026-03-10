---
priority: medium
effort: medium
depends: [2]
issue_type: feature
status: Implementing
labels: [codeagent, ait_settings]
assigned_to: dario-e@beyond-eye.com
implemented_with: opencode/zen_gpt_5_4
created_at: 2026-03-08 11:21
updated_at: 2026-03-10 23:27
---

## Context

This is child task 4 of t303. It adds the Satisfaction Feedback Procedure call to standalone skills that do meaningful AI work but don't go through task-workflow.

## Key Files to Modify

- `.claude/skills/aitask-explain/SKILL.md` — add feedback when user selects "Done" (skill_name: `explain`)
- `.claude/skills/aitask-changelog/SKILL.md` — add feedback after commit (skill_name: `changelog`)
- `.claude/skills/aitask-refresh-code-models/SKILL.md` — add feedback after commit (skill_name: `refresh-code-models`)
- `.claude/skills/aitask-reviewguide-classify/SKILL.md` — add feedback after completion (skill_name: `reviewguide-classify`)
- `.claude/skills/aitask-reviewguide-merge/SKILL.md` — add feedback after completion (skill_name: `reviewguide-merge`)
- `.claude/skills/aitask-reviewguide-import/SKILL.md` — add feedback after completion (skill_name: `reviewguide-import`)

## Reference Files for Patterns

- `.claude/skills/task-workflow/procedures.md` — Satisfaction Feedback Procedure (created in t303_2)

## Implementation Plan

### For each skill, add a final step

Add to the end of each skill's workflow:

```markdown
### Step N: Satisfaction Feedback

Execute the **Satisfaction Feedback Procedure** (see `.claude/skills/task-workflow/procedures.md`) with `skill_name` = `"<skill-name>"`.
```

### Placement details

1. **aitask-explain** — After the user selects "Done" in the Q&A loop, before the skill ends
2. **aitask-changelog** — After the changelog commit step
3. **aitask-refresh-code-models** — After the model JSON commit step
4. **aitask-reviewguide-classify** — After Step 7 (single mode) or Step 13 (batch summary). In batch mode, ask only once at the end, not per-file
5. **aitask-reviewguide-merge** — After Step 7 (single mode) or Step 13 (batch summary). Ask once at end
6. **aitask-reviewguide-import** — After Step 6 (single mode) or Step 7.4 (batch summary). Ask once at end

### Skills explicitly excluded (with rationale)

- `aitask-create` / `aitask-create2` — Simple task creation, not AI-quality-sensitive
- `aitask-stats` — Pure script delegation, no AI reasoning
- `ait-git` / `user-file-select` / `task-workflow` — Infrastructure, not user-invocable
- `aitask-pickrem` / `aitask-pickweb` — No interactive prompts available

## Verification Steps

- Each modified skill has the feedback step in the correct position
- Batch-mode skills ask for feedback only once at the end (not per-item)
- The `skill_name` values match the expected keys in the verifiedstats schema
- Walk through aitask-explain flow: explain a file → select Done → feedback prompt appears
