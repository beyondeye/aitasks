---
Task: t303_4_docs_profiles_model_refresh_compat.md
Parent Task: aitasks/t303_automatic_update_of_model_verified_score.md
Sibling Tasks: aitasks/t303/t303_1_*.md, aitasks/t303/t303_2_*.md, aitasks/t303/t303_3_*.md, aitasks/t303/t303_5_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Plan: t303_4 — Docs, Profiles + Model Refresh Compatibility

## Verified Current State

- `aitasks/metadata/profiles/remote.yaml` already uses `enableFeedbackQuestions: false`
- `.claude/skills/task-workflow/profiles.md` already documents `enableFeedbackQuestions`
- Remaining gap is `verifiedstats` compatibility across refresh docs and OpenCode model handling, plus exposing those stats in `ait codeagent list-models`

## Files To Modify

### 1. `.claude/skills/aitask-refresh-code-models/SKILL.md`
- Update Step 4 new-model example to include `verifiedstats: {}`
- Update Step 6 so it explicitly says existing `verifiedstats` must be preserved for unchanged and updated models
- Document that new models initialize both `verified` and `verifiedstats`
- Update field-order guidance to mention `status` and `verifiedstats` where applicable so the doc matches current metadata shape

### 2. `.aitask-scripts/aitask_codeagent.sh`
- Extend `cmd_list_models()` output formatting beyond the current single `VERIFIED:` summary
- Keep the existing verified-score line
- Add a second rendered summary derived from `.verifiedstats`, formatted per skill as `skill(runs N, avg M)`
- Omit the stats text when a model has no `verifiedstats` entries

### 3. `.aitask-scripts/aitask_opencode_models.sh`
- Update new-model creation so discovered models initialize `verifiedstats: {}`
- Update `merge_with_existing()` so it preserves both `.verified` and `.verifiedstats` from matching existing models
- Leave unavailable-model handling unchanged except for retaining any existing stats on those carried-forward records

## Implementation Steps

### Step 1: Refresh-skill documentation
Edit `.claude/skills/aitask-refresh-code-models/SKILL.md` so its JSON examples and preservation rules reflect the current metadata contract used by `aitask_verified_update.sh` and `models_opencode.json`.

### Step 2: Model listing stats output
Edit `.aitask-scripts/aitask_codeagent.sh` in `cmd_list_models()` to emit both:
- verified score summary from `.verified`
- optional stats summary from `.verifiedstats`

Expected display shape:
```text
MODEL:zen_gpt_5_4 CLI_ID:opencode/gpt-5.4 STATUS:active NOTES:... VERIFIED:task-pick=0,explain=0,batch-review=0,pick=100
STATS:pick(runs 3, avg 100)
```

Models with empty stats should continue to print the model line only.

### Step 3: OpenCode model refresh preservation
Edit `.aitask-scripts/aitask_opencode_models.sh` so refreshes do not drop `verifiedstats` for existing models and so new discovered models start with an empty stats object.

### Step 4: Verify behavior
- Inspect diffs for the three updated files
- Run `bash .aitask-scripts/aitask_opencode_models.sh --help` only if needed to confirm no syntax regression surface was introduced
- Run a targeted command to check list output formatting, ideally `./ait codeagent list-models opencode` if available in this repo setup

## Risks / Notes

- The child task description still mentions an older `skip_satisfaction_feedback` direction, but sibling task work already replaced that design with `enableFeedbackQuestions`; implementation should follow the current repository state
- `cmd_list_models()` uses `jq -r` string formatting, so the stats line should be generated in a way that remains compatible with empty or missing objects

## Step 9 Reference
Post-implementation: archive via task-workflow Step 9.

## Final Implementation Notes

- **Actual work done:** Updated `.claude/skills/aitask-refresh-code-models/SKILL.md` so new-model examples and Step 6 preservation rules include `verifiedstats`, extended `.aitask-scripts/aitask_codeagent.sh` so `cmd_list_models()` emits an optional `STATS:` line from aggregated feedback history, and updated `.aitask-scripts/aitask_opencode_models.sh` so discovered models initialize `verifiedstats: {}` and existing stats survive refresh merges.
- **Deviations from plan:** Did not change `aitasks/metadata/profiles/remote.yaml` or `.claude/skills/task-workflow/profiles.md` because sibling work had already replaced the older `skip_satisfaction_feedback` design with the current `enableFeedbackQuestions` field and those files were already correct.
- **Issues encountered:** The task description and original child-task plan still referenced the superseded `skip_satisfaction_feedback` key, so the active implementation plan was rewritten before coding to align with the current repository state.
- **Key decisions:** Kept the new stats output as a second line only when `.verifiedstats` contains entries, preserving the existing one-line output for models without feedback history. The displayed average is recomputed from `score_sum / runs` and rounded to match the rest of the verified-score presentation.
- **Notes for sibling tasks:** Later model-refresh work should treat `verified` and `verifiedstats` as a pair: `verified` is the derived display score, while `verifiedstats` is the source-of-truth history that must be preserved across refreshes. If future agents gain their own refresh helpers, mirror the same initialization/preservation behavior there.
