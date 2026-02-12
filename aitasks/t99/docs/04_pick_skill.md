<!-- SECTION: Claude Code Integration — Pick Skill -->
<!-- PLACEMENT: replaces existing "### /aitask-pick [number]" section in Claude Code Integration -->

### /aitask-pick [number]

Full development workflow skill — manages the complete task lifecycle from selection through implementation, review, and archival.

**Usage:**
```
/aitask-pick            # Interactive task selection from prioritized list
/aitask-pick 10         # Directly select parent task t10
/aitask-pick 10_2       # Directly select child task t10_2
```

**Workflow overview:**

1. **Profile selection** — Loads an execution profile from `aitasks/metadata/profiles/` to pre-answer workflow questions and reduce prompts. See the **Execution Profiles** section below for configuration details
2. **Task selection** — Shows a prioritized list of tasks (sorted by priority, effort, blocked status) with pagination, or jumps directly to a task when a number argument is provided
3. **Child task handling** — When a parent task with children is selected, drills down to show child subtasks. Gathers context from archived sibling plan files so each child task benefits from previous siblings' implementation experience
4. **Status checks** — Detects edge cases: tasks marked Done but not yet archived, and orphaned parent tasks where all children are complete. Offers to archive them directly
5. **Assignment** — Tracks who is working on the task via email, sets status to "Implementing", commits and pushes the status change
6. **Environment setup** — Optionally creates a separate git branch and worktree (`aiwork/<task_name>/`) for isolated implementation, or works directly on the current branch
7. **Planning** — Enters Claude Code plan mode to explore the codebase and create an implementation plan. If a plan already exists, offers three options: use as-is, verify against current code, or create from scratch. Complex tasks can be decomposed into child subtasks during this phase
8. **Implementation** — Follows the approved plan, updating the plan file with progress and any deviations
9. **User review** — Presents a change summary for review. Supports an iterative "need more changes" loop where each round of feedback is logged in the plan file before re-presenting for approval
10. **Post-implementation** — Archives task and plan files, updates parent task metadata for child tasks, optionally updates/closes linked GitHub issues, and merges the branch if a worktree was used

**Key capabilities:**

- **Direct task selection** — `/aitask-pick 10` selects a parent task; `/aitask-pick 10_2` selects a specific child task. Both formats skip the interactive selection step and show a brief summary for confirmation (skippable via profile)
- **Task decomposition** — During planning, if a task is assessed as high complexity, offers to break it into child subtasks. Each child task is created with detailed context (key files, reference patterns, implementation steps, verification) so it can be executed independently in a fresh context
- **Plan mode integration** — Uses Claude Code's built-in plan mode for codebase exploration and plan design. When an existing plan file is found, offers: "Use current plan" (skip planning), "Verify plan" (check against current code), or "Create from scratch". Plan approval via ExitPlanMode is always required
- **Review cycle** — After implementation, the user reviews changes before any commit. The "Need more changes" option creates numbered change request entries in the plan file, then loops back to review. Each iteration is tracked with timestamps
- **Issue update integration** — When archiving a task that has a linked `issue` field, offers to update the GitHub issue: close with implementation notes, comment only, close silently, or skip. Uses `ait issue-update` which auto-detects associated commits and extracts plan notes
- **Abort handling** — Available at multiple checkpoints (after planning, after implementation). Reverts task status, optionally deletes the plan file, cleans up worktree/branch if created, and commits the status change
- **Branch/worktree support** — Optionally creates an isolated git worktree at `aiwork/<task_name>/` on a new `aitask/<task_name>` branch. After implementation, merges back to the base branch and cleans up the worktree and branch

Execution profiles can pre-configure most workflow questions (email, local/remote, worktree, plan handling) to minimize prompts. See the **Execution Profiles** section for details.
