# Workflow Procedures

Reference procedures used by the task-workflow skill. These are invoked from
the main workflow steps and should be read on demand when referenced.

## Table of Contents

- [Task Abort Procedure](#task-abort-procedure) — Referenced from Step 6 checkpoint and Step 8
- [Issue Update Procedure](#issue-update-procedure) — Referenced from Step 9
- [Lock Release Procedure](#lock-release-procedure) — Referenced from Task Abort Procedure

---

## Task Abort Procedure

This procedure is referenced from Step 6 (plan checkpoint) and Step 8 (user review) wherever the user selects "Abort task". It handles lock release, status revert, email clearing, and worktree cleanup.

When abort is selected at any checkpoint after Step 4, execute these steps:

- **Ask about plan file (if one was created):**
  Use `AskUserQuestion`:
  - Question: "A plan file was created. What should happen to it?"
  - Header: "Plan file"
  - Options:
    - "Keep for future reference" (description: "Plan file remains in aiplans/")
    - "Delete the plan file" (description: "Remove the plan file")

  If "Delete":
  ```bash
  rm aiplans/<plan_file> 2>/dev/null || true
  ```

- **Ask for revert status:**
  Use `AskUserQuestion`:
  - Question: "What status should the task be set to?"
  - Header: "Status"
  - Options:
    - "Ready" (description: "Task available for others to pick up")
    - "Editing" (description: "Task needs modifications before ready")

- **Release task lock:** Execute the **Lock Release Procedure** (see below) for the task.

- **Revert task status and clear assignment:**
  ```bash
  ./aiscripts/aitask_update.sh --batch <task_num> --status <selected_status> --assigned-to ""
  ```

- **Commit the revert:**
  ```bash
  ./ait git add aitasks/ aiplans/
  ./ait git commit -m "ait: Abort t<N>: revert status to <status>"
  ```

- **Cleanup worktree/branch if created:**
  If a worktree was created in Step 5:
  ```bash
  git worktree remove aiwork/<task_name> --force 2>/dev/null || true
  rm -rf aiwork/<task_name> 2>/dev/null || true
  git branch -d aitask/<task_name> 2>/dev/null || true
  ```

- **Inform user:**
  "Task t<N> has been reverted to '<status>' and is available for others."

## Issue Update Procedure

This procedure is referenced from Step 9 wherever a task is being archived. It handles updating/closing a linked issue via `aitask_issue_update.sh` (platform-agnostic — the script handles GitHub, GitLab, etc.).

- Read the `issue` field from the task file's frontmatter (path specified by the caller)
- If the `issue` field is present and non-empty:
  - Use `AskUserQuestion`:
    - Question: "Task has a linked issue: <issue_url>. Update/close it?"
    - Header: "Issue"
    - Options:
      - "Close with notes" (description: "Post implementation notes + commits as comment and close")
      - "Comment only" (description: "Post implementation notes but leave open")
      - "Close silently" (description: "Close without posting a comment")
      - "Skip" (description: "Don't touch the issue")
  - If "Close with notes":
    ```bash
    ./aiscripts/aitask_issue_update.sh --close <task_num>
    ```
  - If "Comment only":
    ```bash
    ./aiscripts/aitask_issue_update.sh <task_num>
    ```
  - If "Close silently":
    ```bash
    ./aiscripts/aitask_issue_update.sh --close --no-comment <task_num>
    ```
  - If "Skip": do nothing
- If no `issue` field: skip silently

## Lock Release Procedure

This procedure is referenced from the Task Abort Procedure wherever a task lock may need to be released. (Step 9 archival lock releases are handled automatically by `aitask_archive.sh`.)

**When to execute:** After Step 4 has been reached (i.e., a lock may have been acquired). This applies to:
- Task Abort Procedure (task aborted after Step 4)
- Note: Step 9 lock releases are handled by `aitask_archive.sh` and do NOT need this procedure

**Procedure:**

- Release the task lock (best-effort, idempotent):
  ```bash
  ./aiscripts/aitask_lock.sh --unlock <task_num> 2>/dev/null || true
  ```
  This is safe to call even if no lock was acquired (e.g., lock branch not initialized, or lock acquisition was skipped due to infrastructure issues). It succeeds silently in all these cases.

- **For child tasks where the parent is also being archived** (all children complete): also release the parent lock:
  ```bash
  ./aiscripts/aitask_lock.sh --unlock <parent_task_num> 2>/dev/null || true
  ```
