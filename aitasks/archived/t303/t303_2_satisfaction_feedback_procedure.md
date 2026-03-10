---
priority: medium
effort: medium
depends: [1]
issue_type: feature
status: Done
labels: [codeagent, ait_settings]
assigned_to: dario-e@beyond-eye.com
implemented_with: opencode/zen_gpt_5_4
created_at: 2026-03-08 11:10
updated_at: 2026-03-10 22:24
completed_at: 2026-03-10 22:24
---

## Context

This is child task 2 of t303. It creates the reusable "Satisfaction Feedback Procedure" and refactors model detection into a shared sub-procedure in `.claude/skills/task-workflow/procedures.md`.

Currently, model detection logic is embedded in the Agent Attribution Procedure. It needs to be extracted so both Agent Attribution and the new Satisfaction Feedback can use it without duplication.

## Key Files to Modify

- `.claude/skills/task-workflow/procedures.md` — add Model Self-Detection Sub-Procedure, add Satisfaction Feedback Procedure, refactor Agent Attribution
- `.claude/skills/task-workflow/SKILL.md` — update procedures reference list

## Reference Files for Patterns

- `.claude/skills/task-workflow/procedures.md` — current Agent Attribution Procedure (lines 167-191)
- `.claude/skills/task-workflow/SKILL.md` — procedures list (lines 482-492)
- `aitasks/metadata/profiles/fast.yaml` — profile key reference

## Implementation Plan

### 1. Add Model Self-Detection Sub-Procedure

Extract from the current Agent Attribution Procedure:
```markdown
## Model Self-Detection Sub-Procedure

**Input:** none (reads from environment and system context)
**Output:** agent string in format `<agent>/<model>` (e.g., `claudecode/opus4_6`)

1. Check `AITASK_AGENT_STRING` env var — if set, return it directly
2. Self-detect:
   - Identify agent CLI: `claudecode`, `geminicli`, `codex`, `opencode`
   - Get current model ID from system context
   - Read `aitasks/metadata/models_<agent>.json`
   - Find entry where `cli_id` matches
   - Extract `name` field
   - Construct: `<agent>/<name>`
   - Fallback: `<agent>/<model_id>`
3. Return the constructed agent string
```

### 2. Refactor Agent Attribution Procedure

Change it to reference the sub-procedure:
```markdown
## Agent Attribution Procedure

1. Execute **Model Self-Detection Sub-Procedure** to get `agent_string`
2. Write to frontmatter:
   ./.aitask-scripts/aitask_update.sh --batch <task_num> --implemented-with "<agent_string>" --silent
```

### 3. Add Satisfaction Feedback Procedure

```markdown
## Satisfaction Feedback Procedure

**Input:** `skill_name` (string, e.g., `pick`, `explore`, `explain`)

1. **Profile check:** If the active profile has `skip_satisfaction_feedback` set to `true`, skip this procedure entirely. Display: "Profile '<name>': skipping satisfaction feedback"

2. Execute **Model Self-Detection Sub-Procedure** to get `agent_string`
   - If detection fails (no agent identified), skip silently

3. Use `AskUserQuestion`:
   - Question: "How well did this skill work? (Rate 1-5, helps improve model selection)"
   - Header: "Feedback"
   - Options:
     - "5 - Excellent" (description: "Completed perfectly, no issues")
     - "4 - Good" (description: "Completed with minor issues")
     - "3 - Acceptable" (description: "Completed but with notable issues")
     - "1-2 - Poor" (description: "Significant problems or failures")
   - Note: 4 options (AskUserQuestion max), mapping: 5→5, 4→4, 3→3, "1-2"→2

4. If user selects a rating (not "Skip"/Other):
   ```bash
   ./.aitask-scripts/aitask_verified_update.sh --agent-string "<agent_string>" --skill "<skill_name>" --score <rating> --silent
   ```
   Parse output: `UPDATED:<agent>/<model>:<skill>:<new_score>` → display: "Updated <skill> verified score for <agent>/<model>: <new_score>"

5. If user skips, proceed without updating
```

### 4. Update SKILL.md procedures list

Add to the procedures list:
```markdown
- **Model Self-Detection Sub-Procedure** — Detect current code agent and model. Referenced from Agent Attribution and Satisfaction Feedback.
- **Satisfaction Feedback Procedure** — Collect user rating and update verified scores. Referenced from Step 9b and standalone skills.
```

### 5. New execution profile key

Document in the procedure: `skip_satisfaction_feedback` (boolean, default: `false`). Fast profile keeps `false`, remote profile will be set to `true` (in t303_5).

## Verification Steps

- Review procedures.md for consistency and completeness
- Verify Agent Attribution still works correctly after refactor
- Verify Satisfaction Feedback references correct script and flags
- Verify profile check logic matches existing profile check patterns in other procedures
