---
title: "/aitask-pick"
linkTitle: "/aitask-pick"
weight: 10
description: "Select and implement the next task — the central development skill"
---

The central skill of the aitasks framework. This is a full development lifecycle skill that manages the complete task lifecycle from selection through implementation, review, and archival.

**Usage:**
```
/aitask-pick            # Interactive task selection from prioritized list
/aitask-pick 10         # Directly select parent task t10
/aitask-pick 10_2       # Directly select child task t10_2
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.
>
> **Codex CLI note:** In Codex wrappers, after implementation, most of the times you will need to explicitly tell the agent to continue the workflow because `request_user_input` is only available in plan mode. Example prompts: `Good, now finish the workflow` or `Good, now continue`.

## Step-by-Step

1. **Profile selection** — Loads an execution profile from `aitasks/metadata/profiles/` to pre-answer skill questions and reduce prompts. See [Execution Profiles](execution-profiles/) for the profile schema and examples
2. **Task selection** — Shows a prioritized list of tasks (sorted by priority, effort, blocked status) with pagination, or jumps directly to a task when a number argument is provided
3. **Child task handling** — When a parent task with children is selected, drills down to show child subtasks. Gathers context from archived sibling plan files so each child task benefits from previous siblings' implementation experience
4. **Task status checks** — Detects edge cases: tasks marked Done but not yet archived, and orphaned parent tasks where all children are complete. Offers to archive them directly
5. **Assignment** — Tracks who is working on the task via email, sets status to "Implementing", commits and pushes the status change
6. **Environment setup** — Optionally creates a separate git branch and worktree (`aiwork/<task_name>/`) for isolated implementation, or works directly on the current branch
7. **Planning** — Enters the agent planning flow to explore the codebase and create an implementation plan. If a plan already exists, offers three options: use as-is, verify against current code, or create from scratch. Complex tasks can be decomposed into child subtasks during this phase
8. **Implementation** — Follows the approved plan, updating the plan file with progress and any deviations
9. **User review** — Presents a change summary for review. Supports an iterative "need more changes" loop where each round of feedback is logged in the plan file before re-presenting for approval. When code is committed, the workflow can compose both imported-contributor attribution and a code-agent `Co-Authored-By` trailer from `implemented_with`
10. **Post-implementation** — Archives task and plan files, updates parent task metadata for child tasks, optionally updates/closes linked issues (GitHub/GitLab/Bitbucket), and merges the branch if a worktree was used. In Codex wrappers, after implementation, most of the times you will need to explicitly continue to this phase (for example: `Good, now finish the workflow` or `Good, now continue`)

> **Test coverage analysis** has been moved to the standalone [`/aitask-qa`](../aitask-qa/) skill. Run `/aitask-qa <task_id>` after implementation to analyze test gaps and create follow-up test tasks.

## Key Capabilities

- **Direct task selection** — `/aitask-pick 10` selects a parent task; `/aitask-pick 10_2` selects a specific child task. Both formats skip the interactive selection step and show a brief summary for confirmation (skippable via profile)
- **Task decomposition** — During planning, if a task is assessed as high complexity, offers to break it into child subtasks. Each child task is created with detailed context (key files, reference patterns, implementation steps, verification) so it can be executed independently in a fresh context
- **Plan mode integration** — Uses the active agent's planning flow for codebase exploration and plan design. When an existing plan file is found, offers: "Use current plan" (skip planning), "Verify plan" (check against current code), or "Create from scratch". Plan approval is always required
- **Review cycle** — After implementation, the user reviews changes before any commit. The "Need more changes" option creates numbered change request entries in the plan file, then loops back to review. Each iteration is tracked with timestamps
- **Issue update integration** — When archiving a task that has a linked `issue` field, offers to update the linked issue: close with implementation notes, comment only, close silently, or skip. Uses `ait issue-update` which auto-detects associated commits and extracts plan notes
- **Abort handling** — Available at multiple checkpoints (after planning, after implementation). Reverts task status, optionally deletes the plan file, cleans up worktree/branch if created, and commits the status change
- **Branch/worktree support** — Optionally creates an isolated git worktree at `aiwork/<task_name>/` on a new `aitask/<task_name>` branch. After implementation, merges back to the base branch and cleans up the worktree and branch

## Execution Profiles

The profile schema, shipped examples, and customization guidance now live on a dedicated page for better discoverability: [Execution Profiles](execution-profiles/).

Use that page for:

- The full standard profile-key reference used by `/aitask-pick`
- QA profile keys (`qa_mode`, `qa_run_tests`, `qa_tier`) for the [`/aitask-qa`](../aitask-qa/) skill
- The `enableFeedbackQuestions` flag for satisfaction prompts
- Example `fast`/custom profile YAML
- Notes about how profiles are reused by related skills such as `/aitask-explore`

## Build Verification

The skill can optionally verify the build after implementation. See [Build Verification](build-verification/) for configuration details.

## Commit Attribution

The review/commit step can combine imported contributor credit with a resolver-based code-agent coauthor trailer. See [Commit Attribution](commit-attribution/) for the exact commit format and configuration.

## Verified Scores

After completion, skills can prompt for a satisfaction rating (1--5) that feeds into verified model scores. These scores help choose the best model for each operation. See [Verified Scores](../verified-scores/) for how ratings are collected, stored, and displayed.

## Workflows

For workflow guides covering specific use cases, see [Task Decomposition](../../workflows/task-decomposition/) and [Parallel Development](../../workflows/parallel-development/).

## Related

- [`/aitask-qa`](../aitask-qa/) — Post-implementation QA analysis and test plan generation
- [`/aitask-review`](../aitask-review/) — Run code review guides over the codebase and create tasks from findings
- [`/aitask-revert`](../aitask-revert/) — Revert changes from a completed task if an implementation needs to be undone
