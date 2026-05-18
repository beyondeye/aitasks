# PR Close/Decline Procedure

This procedure is referenced from Step 9 wherever a task with a linked pull request is being archived. It handles closing/declining a linked PR via `aitask_pr_close.sh` (platform-agnostic — the script handles GitHub, GitLab, etc.).

When the archive script outputs `PR:<task_num>:<pr_url>` or `PARENT_PR:<task_num>:<pr_url>`:

- Use `AskUserQuestion`:
  - Question: "Task t<task_num> has a linked PR: <pr_url>. What should happen to it?"
  - Header: "PR"
  - Options:
    - "Close/decline with notes" (description: "Post implementation notes + commits as comment and close/decline")
    - "Comment only" (description: "Post implementation notes but leave open")
    - "Close/decline silently" (description: "Close/decline without posting a comment")
    - "Skip" (description: "Don't touch the PR")
- If "Close/decline with notes":
  ```bash
  ./.aitask-scripts/aitask_pr_close.sh --close <task_num>
  ```
- If "Comment only":
  ```bash
  ./.aitask-scripts/aitask_pr_close.sh <task_num>
  ```
- If "Close/decline silently":
  ```bash
  ./.aitask-scripts/aitask_pr_close.sh --close --no-comment <task_num>
  ```
- If "Skip": do nothing
