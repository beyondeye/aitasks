---
title: "/aitask-pick"
linkTitle: "/aitask-pick"
weight: 10
description: "Select and implement the next task — the central development workflow skill"
---

The central skill of the aitasks framework and the core of the development workflow. This is a full development workflow skill that manages the complete task lifecycle from selection through implementation, review, and archival.

**Usage:**
```
/aitask-pick            # Interactive task selection from prioritized list
/aitask-pick 10         # Directly select parent task t10
/aitask-pick 10_2       # Directly select child task t10_2
```

## Workflow Overview

1. **Profile selection** — Loads an execution profile from `aitasks/metadata/profiles/` to pre-answer workflow questions and reduce prompts. See [Execution Profiles](#execution-profiles) below
2. **Task selection** — Shows a prioritized list of tasks (sorted by priority, effort, blocked status) with pagination, or jumps directly to a task when a number argument is provided
3. **Child task handling** — When a parent task with children is selected, drills down to show child subtasks. Gathers context from archived sibling plan files so each child task benefits from previous siblings' implementation experience
4. **Status checks** — Detects edge cases: tasks marked Done but not yet archived, and orphaned parent tasks where all children are complete. Offers to archive them directly
5. **Assignment** — Tracks who is working on the task via email, sets status to "Implementing", commits and pushes the status change
6. **Environment setup** — Optionally creates a separate git branch and worktree (`aiwork/<task_name>/`) for isolated implementation, or works directly on the current branch
7. **Planning** — Enters Claude Code plan mode to explore the codebase and create an implementation plan. If a plan already exists, offers three options: use as-is, verify against current code, or create from scratch. Complex tasks can be decomposed into child subtasks during this phase
8. **Implementation** — Follows the approved plan, updating the plan file with progress and any deviations
9. **User review** — Presents a change summary for review. Supports an iterative "need more changes" loop where each round of feedback is logged in the plan file before re-presenting for approval
10. **Post-implementation** — Archives task and plan files, updates parent task metadata for child tasks, optionally updates/closes linked GitHub issues, and merges the branch if a worktree was used

## Key Capabilities

- **Direct task selection** — `/aitask-pick 10` selects a parent task; `/aitask-pick 10_2` selects a specific child task. Both formats skip the interactive selection step and show a brief summary for confirmation (skippable via profile)
- **Task decomposition** — During planning, if a task is assessed as high complexity, offers to break it into child subtasks. Each child task is created with detailed context (key files, reference patterns, implementation steps, verification) so it can be executed independently in a fresh context
- **Plan mode integration** — Uses Claude Code's built-in plan mode for codebase exploration and plan design. When an existing plan file is found, offers: "Use current plan" (skip planning), "Verify plan" (check against current code), or "Create from scratch". Plan approval via ExitPlanMode is always required
- **Review cycle** — After implementation, the user reviews changes before any commit. The "Need more changes" option creates numbered change request entries in the plan file, then loops back to review. Each iteration is tracked with timestamps
- **Issue update integration** — When archiving a task that has a linked `issue` field, offers to update the GitHub issue: close with implementation notes, comment only, close silently, or skip. Uses `ait issue-update` which auto-detects associated commits and extracts plan notes
- **Abort handling** — Available at multiple checkpoints (after planning, after implementation). Reverts task status, optionally deletes the plan file, cleans up worktree/branch if created, and commits the status change
- **Branch/worktree support** — Optionally creates an isolated git worktree at `aiwork/<task_name>/` on a new `aitask/<task_name>` branch. After implementation, merges back to the base branch and cleans up the worktree and branch

## Execution Profiles

The `/aitask-pick` skill asks several interactive questions before reaching implementation (email, local/remote, worktree, plan handling, etc.). Execution profiles let you pre-configure answers to these questions so you can go from task selection to implementation with minimal input.

Profiles are YAML files stored in `aitasks/metadata/profiles/`. Two profiles ship by default:

- **default** — All questions asked normally (empty profile, serves as template)
- **fast** — Skip confirmations, use first stored email, work locally on current branch, reuse existing plans

When you run `/aitask-pick`, the profile is selected first (Step 0a). If only one profile exists, it's auto-loaded. With multiple profiles, you're prompted to choose.

### Profile Settings

| Key | Type | Description |
|-----|------|-------------|
| `name` | string (required) | Display name shown during profile selection |
| `description` | string (required) | Description shown below profile name during selection |
| `skip_task_confirmation` | bool | `true` = auto-confirm task selection |
| `default_email` | string | `"first"` = use first email from emails.txt; or a literal email address |
| `run_location` | string | `"locally"` or `"remotely"` |
| `create_worktree` | bool | `true` = create worktree; `false` = work on current branch |
| `base_branch` | string | Branch name for worktree (e.g., `"main"`) |
| `plan_preference` | string | `"use_current"`, `"verify"`, or `"create_new"` |
| `post_plan_action` | string | `"start_implementation"` = skip post-plan prompt |
| `explore_auto_continue` | bool | `true` = auto-continue from explore to implementation (used by `/aitask-explore`) |

Omitting a key means the corresponding question is asked interactively. Plan approval (ExitPlanMode) is always mandatory and cannot be skipped.

### Creating a Custom Profile

```bash
cp aitasks/metadata/profiles/fast.yaml aitasks/metadata/profiles/my-profile.yaml
```

Edit the file to set your preferences:

```yaml
name: worktree
description: Like fast but creates a worktree on main for each task
skip_task_confirmation: true
default_email: first
run_location: locally
create_worktree: true
base_branch: main
plan_preference: use_current
post_plan_action: start_implementation
```

Profiles are preserved during `install.sh --force` upgrades (existing files are not overwritten).
