---
priority: medium
effort: medium
depends: [t259_2, t259_3]
issue_type: feature
status: Ready
labels: [aitask_review]
created_at: 2026-02-26 18:45
updated_at: 2026-02-26 18:46
---

## Context

This task creates the aitask-review-batched Claude Code skill and integrates all batch review components. The skill provides the interactive workflow for launching batch reviews from Claude Code, while the ait dispatcher gets updated with all new commands.

Depends on: t259_2 (batch driver core), t259_3 (session orchestration)

## Key Files to Modify

- .claude/skills/aitask-review-batched/SKILL.md (new) — Claude Code skill definition
- ait — update help text with all new commands

## Reference Files for Patterns

- .claude/skills/aitask-review/SKILL.md — pattern for review skill workflow
- .claude/skills/user-file-select/SKILL.md — reusable file selection skill
- aitasks/metadata/profiles/fast.yaml — profile key patterns

## Implementation Plan

### Step 1: Create skill definition

.claude/skills/aitask-review-batched/SKILL.md:

Workflow:
1. Profile selection (same as aitask-review Step 0a)
2. Target selection: use user-file-select skill or accept paths argument
   - Support directories and individual files
   - Support external paths (outside project repo)
3. Review guide selection: run aitask_review_detect_env.sh, present ranked guides
4. Batch parameter configuration:
   - Max parallel sessions (default 3)
   - Per-session timeout (default 600s)
   - Max files per session (default 5)
   - Model (default sonnet)
   - Profile overrides for all of the above
5. Launch batch driver:
   ./aiscripts/aitask_review_batch_run.sh --batch --targets "<paths>" --source-root "<root>" --guides "<guides>" --max-parallel <n> --timeout <t> --max-files-per-session <n> --model <m>
6. Monitor output, display progress
7. On completion: inform user to run ait reviewbrowser, show summary

### Step 2: Profile integration

Add profile keys:
- review_batch_max_parallel: int (default 3)
- review_batch_timeout: int (default 600)
- review_batch_model: string (default "sonnet")
- review_batch_max_files: int (default 5)

### Step 3: Update ait help text

Add new commands section to ait show_usage():
  Review:
    review-batch-run   Run batch code review
    reviewbrowser      Launch review findings browser TUI
    review-runs        List/manage review run directories
    review-cleanup     Clean up stale review runs

### Step 4: Add aireviews/ to .gitignore

### Step 5: Update seed/ if needed

Check if seed/ templates need new profile keys or metadata files.

## Verification Steps

- Verify skill loads correctly in Claude Code (check .claude/settings.local.json if needed)
- Test skill workflow end-to-end with a small directory
- Verify ait help shows new commands
- Verify aireviews/ is gitignored
