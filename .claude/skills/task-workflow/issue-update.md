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
  - **Exit 3 / `RELEASE_LEDGER_FAILED:<reason>`**: the issue update succeeded;
    only its release-ledger entry was not recorded. **Do not re-run the
    command** — that would post the comment again. Run the `--record-only`
    command the script printed on stderr (it makes no platform call). If stderr
    says no retry will succeed, report it and continue.
- If no `issue` field: skip silently

## Related Issues

This section handles `RELATED_ISSUE:` and `PARENT_RELATED_ISSUE:` output lines from the archive script. These come from the `related_issues:` YAML array — URLs of source issues that were merged into the task via `--merge-issues`.

- For each `RELATED_ISSUE:<task_num>:<issue_url>` or `PARENT_RELATED_ISSUE:<task_num>:<issue_url>` line:
  - Use `AskUserQuestion`:
    - Question: "Task has a related issue (from merged import): <issue_url>. Update/close it?"
    - Header: "Issue"
    - Options:
      - "Close with notes" (description: "Post implementation notes + commits as comment and close")
      - "Comment only" (description: "Post implementation notes but leave open")
      - "Close silently" (description: "Close without posting a comment")
      - "Skip" (description: "Don't touch the issue")
  - If "Close with notes":
    ```bash
    ./.aitask-scripts/aitask_issue_update.sh --issue-url "<issue_url>" --close <task_num>
    ```
  - If "Comment only":
    ```bash
    ./.aitask-scripts/aitask_issue_update.sh --issue-url "<issue_url>" <task_num>
    ```
  - If "Close silently":
    ```bash
    ./.aitask-scripts/aitask_issue_update.sh --issue-url "<issue_url>" --close --no-comment <task_num>
    ```
  - If "Skip": do nothing
  - Exit 3 (`RELEASE_LEDGER_FAILED:`) is handled as above: never re-run the command.
  - Note: Uses `--issue-url` because the URL comes from `related_issues:`, not the primary `issue:` field
