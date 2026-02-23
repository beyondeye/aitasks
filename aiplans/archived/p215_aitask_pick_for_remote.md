---
Task: t215_aitask_pick_for_remote.md
Branch: (current branch, no worktree)
---

# Plan: aitask-pick-remote skill (t215)

## Context

Claude Code Web's `AskUserQuestion` doesn't work properly. The current `aitask-pick` + `task-workflow` skills use 24 `AskUserQuestion` calls throughout the workflow. A separate self-contained skill is needed for remote/web development that replaces ALL interactive prompts with profile-driven configuration.

## Approach

Create a new `aitask-pick-remote` skill with its own complete workflow (no reference to `task-workflow`). Also simplify `task-workflow` by removing the "remotely" execution path since remote dev now has its own dedicated skill.

## Files to Create

### 1. `.claude/skills/aitask-pick-remote/SKILL.md`
Self-contained skill with zero `AskUserQuestion` calls. Combines the relevant parts of aitask-pick and task-workflow into a streamlined remote workflow.

**Key design decisions:**
- Task ID is a **required** argument (no browsing/selection)
- Profile is auto-selected (prefer one named "remote", else first available; abort if none exist)
- Parent tasks with children → error, require specific child ID
- No worktree/branch management — always current branch
- `EnterPlanMode`/`ExitPlanMode` are kept (they are NOT `AskUserQuestion`)
- Complexity assessment always chooses "single_task" (can't create children without interaction)
- Step 8 auto-commits (no review loop — no human review before commit)
- **Testing emphasis**: Since there is no user review step, the skill encourages comprehensive automated testing for code changes (not for config/documentation tasks). Tests should be run before auto-commit when applicable.
- No merge step (no separate branch)
- Issue handling driven by profile's `issue_action` field
- Abort procedure triggered only by errors, uses profile defaults

**Workflow steps:**
1. Parse args & load profile (auto-select, no prompt)
2. Resolve task file (error if parent has children)
3. Sync with remote (best-effort)
4. Task status checks (Done/orphan handled by `done_task_action`/`orphan_parent_action`)
5. Claim task (`default_email` from profile)
6. Environment: always current branch, no worktree (just a display message)
7. Plan handling (`plan_preference` + `post_plan_action` from profile) — planning step MUST include comprehensive automated test plan
8. Implement — run automated tests when applicable (code changes)
9. Auto-commit (`review_action` from profile, consolidate plan, commit) — abort if code tests fail
10. Archive + push (`issue_action` from profile, no merge step)

### 2. `aitasks/metadata/profiles/remote.yaml`
```yaml
name: remote
description: Fully autonomous workflow for Claude Code Web - no interactive prompts
skip_task_confirmation: true
default_email: first
plan_preference: use_current
post_plan_action: start_implementation
done_task_action: archive
orphan_parent_action: archive
complexity_action: single_task
review_action: commit
issue_action: close_with_notes
abort_plan_action: keep
abort_revert_status: Ready
```

## Files to Modify

### 3. `.claude/skills/task-workflow/SKILL.md`
- **Step 5**: Remove `run_location` profile check and "Are you running locally or remotely?" `AskUserQuestion`. Go straight to worktree question (profile `create_worktree` or ask). Change `**If No or running remotely:**` → `**If No:**`
- **Profile Schema Reference table**: Remove `run_location` row. Add note that remote-specific fields are in `aitask-pick-remote`
- **Execution Profiles notes**: Add reference to `aitask-pick-remote` for remote dev

### 4. `aitasks/metadata/profiles/fast.yaml`
- Remove `run_location: locally` line (field no longer exists in task-workflow schema)

## Extended Profile Schema (new fields for remote skill)

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `done_task_action` | string | `archive` | `"archive"` or `"skip"` — Step 3 Done task check |
| `orphan_parent_action` | string | `archive` | `"archive"` or `"skip"` — Step 3 orphan parent check |
| `complexity_action` | string | `single_task` | Always `"single_task"` for remote (no child creation) |
| `review_action` | string | `commit` | `"commit"` — Step 8 auto-commit |
| `issue_action` | string | `close_with_notes` | `"skip"`, `"close_with_notes"`, `"comment_only"`, `"close_silent"` |
| `abort_plan_action` | string | `keep` | `"keep"` or `"delete"` — plan file on abort |
| `abort_revert_status` | string | `Ready` | `"Ready"` or `"Editing"` — status on abort |

Existing fields reused as-is: `name`, `description`, `skip_task_confirmation`, `default_email`, `plan_preference`, `post_plan_action`.

## All 24 AskUserQuestion Calls Mapped

| # | Original Location | Remote Replacement |
|---|---|---|
| 1 | aitask-pick 0a: Profile selection | Auto-select (prefer "remote" name) |
| 2 | aitask-pick 0b: Task confirmation | Hardcoded skip |
| 3 | aitask-pick 1: Label filtering | Eliminated (task ID required) |
| 4 | aitask-pick 2c: Task selection | Eliminated (task ID required) |
| 5 | aitask-pick 2d: Child selection | Eliminated (child ID required) |
| 6 | task-workflow 3: Done task | Profile: `done_task_action` |
| 7 | task-workflow 3: Orphan parent | Profile: `orphan_parent_action` |
| 8 | task-workflow 3b: Profile re-select | Error + abort (profile required) |
| 9 | task-workflow 4: Email | Profile: `default_email` |
| 10 | task-workflow 5: Local/remote | Eliminated (always current branch) |
| 11 | task-workflow 5: Worktree | Eliminated (always current branch) |
| 12 | task-workflow 5: Base branch | Eliminated (always current branch) |
| 13 | task-workflow 6.0: Existing plan | Profile: `plan_preference` |
| 14 | task-workflow 6.1: Complexity | Profile: `complexity_action` |
| 15 | task-workflow 6 checkpoint | Profile: `post_plan_action` |
| 16 | task-workflow 8: Review/commit | Profile: `review_action` |
| 17 | task-workflow 9: Merge confirm | Eliminated (no separate branch) |
| 18-20 | task-workflow 9: Issue handling | Profile: `issue_action` |
| 21 | task-workflow Abort: Plan file | Profile: `abort_plan_action` |
| 22 | task-workflow Abort: Revert status | Profile: `abort_revert_status` |
| 23 | task-workflow 4: New email input | Eliminated (profile has email) |
| 24 | task-workflow 8: Change requests | Eliminated (auto-commit) |

## Testing Emphasis (for the SKILL.md content)

Since there is no human review before commit in the remote workflow, the skill should encourage comprehensive automated testing **when reasonably applicable** (i.e., when the task involves code changes, not for config edits or documentation-only tasks).

In the new skill's **Step 6 (Planning)**, add:
- When the task involves code changes, the implementation plan should include a "Verification" section with automated tests where reasonable
- The plan should specify: what tests to write/run, expected outcomes
- For non-code tasks (documentation, config, skill files), a simple verification step (e.g., lint check, dry-run) is sufficient

In the new skill's **Step 7 (Implement)**, add:
- After implementation, run relevant automated tests if the task involves code changes
- If tests fail, attempt to fix before proceeding to Step 8
- If no tests are applicable (documentation, config tasks), proceed directly

In the new skill's **Step 8 (Auto-Commit)**, add:
- If code tests were run and failed, and fixes were unsuccessful, trigger abort instead of committing broken code

## Verification

- Read through the new SKILL.md and confirm zero `AskUserQuestion` references
- Read through modified task-workflow and confirm `run_location` is removed from Step 5 and schema table
- Verify `fast.yaml` no longer has `run_location`
- Verify `remote.yaml` has all extended fields with sensible defaults
- Dry-run the mental workflow: `/aitask-pick-remote 215` with remote profile → should proceed through all steps without any interactive prompt

## Final Implementation Notes

- **Actual work done:** Created the new `aitask-pick-remote` skill with a self-contained 10-step workflow, zero `AskUserQuestion` calls, and 7 new remote-specific profile fields. Created `remote.yaml` profile with sensible defaults. Simplified `task-workflow` Step 5 by removing the `run_location` profile check and local/remote question. Removed `run_location` from `fast.yaml`.
- **Deviations from plan:** None — all 4 files were created/modified as planned.
- **Key decisions:**
  - The remote skill is fully self-contained (does not reference `task-workflow`), preventing confusion from mixed interactive/non-interactive flows
  - Parent tasks with children are rejected with an error requiring a specific child ID, since interactive child selection is impossible without `AskUserQuestion`
  - Testing is emphasized for code changes but explicitly noted as optional for config/documentation tasks
  - `EnterPlanMode`/`ExitPlanMode` are retained as the only interactive elements (they are not `AskUserQuestion`)
- **Verification results:**
  - 0 `AskUserQuestion` references in new skill
  - 0 `run_location` references in task-workflow
  - 0 `run_location` references in fast.yaml
  - remote.yaml has all 7 extended fields with defaults
