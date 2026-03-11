---
priority: medium
effort: low
depends: [1, 2]
issue_type: feature
status: Done
labels: [codeagent, ait_settings]
assigned_to: dario-e@beyond-eye.com
implemented_with: opencode/zen_gpt_5_4
created_at: 2026-03-08 11:21
updated_at: 2026-03-11 08:51
completed_at: 2026-03-11 08:51
---

## Context

This is child task 5 of t303. It updates documentation, execution profiles, and ensures model refresh scripts preserve the new `verifiedstats` field.

## Key Files to Modify

- `aitasks/metadata/profiles/remote.yaml` — add `skip_satisfaction_feedback: true`
- `.claude/skills/task-workflow/profiles.md` — document `skip_satisfaction_feedback` key in profile schema
- `.claude/skills/aitask-refresh-code-models/SKILL.md` — update Step 6 to preserve `verifiedstats` during refresh, init empty `{}` for new models
- `.aitask-scripts/aitask_codeagent.sh` — update `cmd_list_models` to show verifiedstats summary
- `.aitask-scripts/aitask_opencode_models.sh` — preserve `verifiedstats` during model refresh

## Reference Files for Patterns

- `aitasks/metadata/profiles/fast.yaml` — profile key format
- `aitasks/metadata/profiles/remote.yaml` — profile to update
- `.claude/skills/task-workflow/profiles.md` — profile schema documentation
- `.aitask-scripts/aitask_codeagent.sh` — `cmd_list_models()` function

## Implementation Plan

### 1. Update remote.yaml profile

Add:
```yaml
skip_satisfaction_feedback: true
```

### 2. Document profile key in profiles.md

Add to the profile schema table:
```markdown
| `skip_satisfaction_feedback` | boolean | `false` | Skip the satisfaction feedback question at the end of skills | Satisfaction Feedback Procedure |
```

### 3. Update aitask-refresh-code-models

In Step 6 (Update JSON Files), add instructions to:
- Preserve `verifiedstats` for existing/updated models (same as existing `verified` preservation)
- Initialize `verifiedstats: {}` for new models

### 4. Update aitask_codeagent.sh

In `cmd_list_models()`, enhance the output to include verifiedstats summary. After showing verified scores, add a line showing stats:
```
  Stats: pick(5 runs, avg 80), explore(3 runs, avg 73)
```

### 5. Update aitask_opencode_models.sh

Ensure `verifiedstats` is preserved when models are refreshed (same jq pattern as existing field preservation).

## Verification Steps

- `cat aitasks/metadata/profiles/remote.yaml` shows `skip_satisfaction_feedback: true`
- `ait codeagent list-models` shows verifiedstats info
- `aitask-refresh-code-models` preserves verifiedstats for unchanged models
- Profile schema docs include the new key
