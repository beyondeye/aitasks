---
Task: t303_4_docs_profiles_model_refresh_compat.md
Parent Task: aitasks/t303_automatic_update_of_model_verified_score.md
Sibling Tasks: aitasks/t303/t303_1_*.md, aitasks/t303/t303_2_*.md, aitasks/t303/t303_3_*.md, aitasks/t303/t303_5_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Plan: t303_4 — Docs, Profiles + Model Refresh Compatibility

## Steps

### 1. Update remote.yaml profile
Add `skip_satisfaction_feedback: true`.

### 2. Update profiles.md schema docs
Add `skip_satisfaction_feedback` key to the profile schema table.

### 3. Update aitask-refresh-code-models SKILL.md
Step 6: preserve `verifiedstats` for existing models, init `{}` for new models.

### 4. Update aitask_codeagent.sh
`cmd_list_models()`: show verifiedstats summary in output.

### 5. Update aitask_opencode_models.sh
Preserve `verifiedstats` during model refresh via jq.

## Verification

- remote.yaml has the new key
- `ait codeagent list-models` shows stats
- refresh-code-models preserves verifiedstats

## Step 9 Reference
Post-implementation: archive via task-workflow Step 9.
