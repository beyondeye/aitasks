# Issue Update Procedure

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
    ./.aitask-scripts/aitask_issue_update.sh --close <task_num>
    ```
  - If "Comment only":
    ```bash
    ./.aitask-scripts/aitask_issue_update.sh <task_num>
    ```
  - If "Close silently":
    ```bash
    ./.aitask-scripts/aitask_issue_update.sh --close --no-comment <task_num>
    ```
  - If "Skip": do nothing
- If no `issue` field: skip silently
