# Workflow Procedures

Reference procedures used by the task-workflow skill. These are invoked from
the main workflow steps and should be read on demand when referenced.

## Table of Contents

- [Task Abort Procedure](#task-abort-procedure) — Referenced from Step 6 checkpoint and Step 8
- [Issue Update Procedure](#issue-update-procedure) — Referenced from Step 9
- [PR Close/Decline Procedure](#pr-closedecline-procedure) — Referenced from Step 9
- [Contributor Attribution Procedure](#contributor-attribution-procedure) — Referenced from Step 8
- [Code-Agent Commit Attribution Procedure](#code-agent-commit-attribution-procedure) — Referenced from Step 8
- [Model Self-Detection Sub-Procedure](#model-self-detection-sub-procedure) — Referenced from Agent Attribution and Satisfaction Feedback
- [Agent Attribution Procedure](#agent-attribution-procedure) — Referenced from Step 7, aitask-wrap, aitask-pickrem, aitask-pickweb
- [Satisfaction Feedback Procedure](#satisfaction-feedback-procedure) — Referenced from Step 9b and standalone skills
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
  ./.aitask-scripts/aitask_update.sh --batch <task_num> --status <selected_status> --assigned-to ""
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

## PR Close/Decline Procedure

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

## Contributor Attribution Procedure

This procedure is referenced from Step 8 wherever code changes are being committed. It checks whether the task carries imported contributor metadata and, if so, formats the commit message to credit the original contributor.

**When to execute:** Before the code commit in Step 8 ("If Commit changes"), to determine whether the final commit message needs a contributor trailer block.

**Procedure:**

- Read the task file's frontmatter and check for `contributor`, `contributor_email`, `pull_request`, and `issue` fields.

- **If both `contributor` and `contributor_email` are present**, the final code commit message MUST include a contributor attribution block.
  - **If `pull_request` is present**, use:
    ```text
    Based on PR: <pull_request_url>

    Co-Authored-By: <contributor> <<contributor_email>>
    ```
  - **Otherwise** (for example, contributor metadata imported from an issue), use:
    ```text
    Co-Authored-By: <contributor> <<contributor_email>>
    ```
  Example for PR-imported work:
  ```text
  Based on PR: https://github.com/owner/repo/pull/15

  Co-Authored-By: octocat <12345+octocat@users.noreply.github.com>
  ```
  Example for issue-imported work:
  ```text
  Co-Authored-By: contributor-name <contributor@example.com>
  ```
  This block is composed into the final commit message together with any code-agent trailer from the **Code-Agent Commit Attribution Procedure** below.

- **If only `contributor` is present without `contributor_email`:** Skip the `Co-Authored-By` trailer (platforms require a valid email for attribution linking). Use the normal subject line, plus the code-agent trailer if available.

- **If neither field is present:** No contributor attribution block is needed. Use the normal subject line, plus the code-agent trailer if available.

### Multi-Contributor Attribution (Merged Issues)

When a task has both `contributor`/`contributor_email` (primary) and a `contributors:` list (secondary contributors from merged issues), the commit message includes:

- **Primary contributor:** `Co-Authored-By` trailer (as above, unchanged)
- **Secondary contributors:** Listed in the commit body text, between the subject line and the `Co-Authored-By` trailers:
  ```text
  Also based on contributions from: bob (#38), charlie (#15)
  ```

**Procedure for reading `contributors:`:**

- Read the task file's frontmatter. If `contributors:` is present, it is a YAML list of objects:
  ```yaml
  contributors:
    - name: bob
      email: bob@example.com
      issue: https://github.com/owner/repo/issues/38
  ```
- Extract each contributor's name and issue number (from the URL).
- Format as: `Also based on contributions from: <name1> (#<issue_num1>), <name2> (#<issue_num2>)`
- Place this line after the subject, before the `Co-Authored-By` trailer.

**Example with primary + secondary contributors and code-agent:**

```bash
git commit -m "$(cat <<'EOF'
feature: Add dark mode and theme support (t42)

Also based on contributions from: bob (#38), charlie (#15)

Co-Authored-By: primary-author <primary@example.com>
Co-Authored-By: Codex/GPT5.4 <codex@aitasks.io>
EOF
)"
```

- The `related_issues:` frontmatter field is informational only (no commit message impact). It records all source issue URLs for traceability.

**Notes:**
- `Co-Authored-By` is preferred over `--author` — the contributor inspired the work but the current implementer wrote this specific code
- The `contributor_email` can be pre-computed during PR import or extracted by `ait issue-import` from `aitask-contribute` metadata — no API call is needed at commit time
- Both GitHub and GitLab display `Co-Authored-By` contributors in the commit UI and count them as contributions

## Code-Agent Commit Attribution Procedure

This procedure is referenced from Step 8 wherever code changes are being committed. It resolves a `Co-Authored-By` trailer for the code agent recorded in `implemented_with`.

**When to execute:** After the Contributor Attribution Procedure and before the final `git commit`, so the contributor trailer and code-agent trailer can be composed into one commit message.

**Procedure:**

- Read the task file's frontmatter and check `implemented_with`.

- **If `implemented_with` is empty or missing:** Skip agent commit attribution.

- **If `implemented_with` is present:**
  - Resolve the trailer with:
    ```bash
    ait codeagent coauthor "<implemented_with>"
    ```
  - Parse the machine-readable output:
    - `AGENT_COAUTHOR_NAME:<display_name>`
    - `AGENT_COAUTHOR_EMAIL:<email>`
    - `AGENT_COAUTHOR_TRAILER:<full trailer>`

- **If the resolver succeeds:** Append `AGENT_COAUTHOR_TRAILER` after any contributor trailer block. **IMPORTANT:** The resolver trailer is the sole coauthor attribution for the implementing agent. Do NOT add any additional native or hardcoded coauthor trailers (e.g., Claude Code's default `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`). The resolver output replaces any such defaults.

- **If the resolver fails** (unsupported agent, invalid agent string, missing config, or other command error): skip only the code-agent trailer and continue with the commit flow. Do NOT drop or alter an existing contributor attribution block because agent attribution failed.

**Final commit composition:**

- Always keep the subject line as:
  ```text
  <issue_type>: <description> (t<task_id>)
  ```
- If contributor attribution exists, append the imported contributor block:
  - PR-imported task:
    ```text
    Based on PR: <pull_request_url>

    Co-Authored-By: <contributor> <<contributor_email>>
    ```
  - Issue-imported task (or any task with contributor metadata but no `pull_request` URL):
    ```text
    Co-Authored-By: <contributor> <<contributor_email>>
    ```
- If code-agent attribution exists, append its trailer after any contributor trailer:
  ```text
  Co-Authored-By: <agent display name> <<agent email>>
  ```

**Example with both contributor and code-agent attribution:**

```bash
git commit -m "$(cat <<'EOF'
feature: Add dark mode support (t42)

Based on PR: https://github.com/owner/repo/pull/15

Co-Authored-By: octocat <12345+octocat@users.noreply.github.com>
Co-Authored-By: Codex/GPT5.4 <codex@aitasks.io>
EOF
)"
```

## Model Self-Detection Sub-Procedure

This shared sub-procedure resolves the current code agent and model into an
agent string like `claudecode/opus4_6`. It is referenced by the Agent
Attribution Procedure and the Satisfaction Feedback Procedure.

**Input:** none (reads environment, agent runtime context, and model config files)

**Output:** `agent_string` in format `<agent>/<model>`

**Procedure:**

1. **Check `AITASK_AGENT_STRING` env var** — if set (by the codeagent wrapper), use its value directly as the agent string and return. This value is authoritative and should correspond to a real entry in `aitasks/metadata/models_<agent>.json`.

2. **If not set, self-detect:**
   - Identify which code agent CLI you are running in. The agent name MUST be one of these exact strings: `claudecode`, `geminicli`, `codex`, `opencode`. **IMPORTANT:** Use `claudecode` (not `claude`), `geminicli` (not `gemini`). These are the only valid agent identifiers.
   - **Obtain your current model ID** using the agent-specific method:
     - **Claude Code:** Read the "exact model ID" from the system message (e.g., `claude-opus-4-6`).
     - **Codex CLI:** Do NOT guess your model ID — Codex models cannot reliably self-identify from system context. Instead, run: `grep '^model' ~/.codex/config.toml | sed 's/^model[[:space:]]*=[[:space:]]*//' | tr -d '"'` to read the configured model (e.g., `gpt-5.4`). This returns the startup/default model. **Limitation:** If the model was changed mid-session via `/model`, this gives the configured default, not the current runtime model.
     - **Gemini CLI:** Read the model ID from system context, or run: `jq -r '.model // empty' ~/.gemini/settings.json 2>/dev/null` as fallback.
     - **OpenCode:** Read the model ID from system context.
    - Read the corresponding model config file: `aitasks/metadata/models_<agent>.json`
    - Find the model entry whose `cli_id` matches your model ID exactly
    - For OpenCode only, if no exact match exists, try an explicit documented alias match before falling back. Do not silently remap to a different provider/model entry based only on a similar base model name.
    - Extract the `name` field from that entry (e.g., `opus4_6`)
   - Construct the agent string as `<agent>/<name>` (e.g., `claudecode/opus4_6`)
   - If no matching entry is found, use `<agent>/<model_id>` as fallback (e.g., `claudecode/claude-opus-4-6`) — the raw model ID from the system context

## Agent Attribution Procedure

This procedure records which code agent and LLM model is executing the task by setting the `implemented_with` field in the task's frontmatter. It is referenced from Step 7 (task-workflow), aitask-wrap (Step 4a), aitask-pickrem (Step 8), and aitask-pickweb (Step 6).

**When to execute:** At the start of implementation, after plan mode has been exited. This timing is critical because some code agents (e.g., Codex CLI) run initial workflow steps in plan mode, which is read-only and cannot write metadata.

**Procedure:**

1. Execute the **Model Self-Detection Sub-Procedure** to get `agent_string`.

2. **Write to frontmatter:**
   ```bash
   ./.aitask-scripts/aitask_update.sh --batch <task_num> --implemented-with "<agent_string>" --silent
   ```

**Variant for aitask-pickweb:** Since pickweb does not call `aitask_update.sh` (no cross-branch operations), store the agent string in the completion marker JSON instead (add an `"implemented_with"` field). The `aitask-web-merge` skill will apply it during archival.

## Satisfaction Feedback Procedure

This procedure collects a quick user rating after a skill completes and updates
rolling verified scores for the current code agent/model.

**Input:** `skill_name` (string, for example `pick`, `explore`, `explain`)

**Procedure:**

1. **Profile check:** If the active profile exists and `enableFeedbackQuestions` is set to `false`, skip this procedure entirely. Display: `Profile '<name>': feedback questions disabled`.

   **Default behavior:** If `enableFeedbackQuestions` is omitted, treat it as `true` and continue normally.

2. Execute the **Model Self-Detection Sub-Procedure** to get `agent_string`.
   - If detection fails or no supported agent/model can be identified, skip silently.

3. Use `AskUserQuestion`:
   - Question: `How well did this skill work? (Rate 1-5, helps improve model selection)`
   - Header: `Feedback`
   - Options:
     - `5 - Excellent` (description: `Completed perfectly, no issues`)
     - `4 - Good` (description: `Completed with minor issues`)
     - `3 - Acceptable` (description: `Completed but with notable issues`)
     - `1-2 - Poor` (description: `Significant problems or failures`)

   **Score mapping:** `5 -> 5`, `4 -> 4`, `3 -> 3`, `1-2 -> 2`

4. If the user selected a rating, update verified stats:
   ```bash
   ./.aitask-scripts/aitask_verified_update.sh --agent-string "<agent_string>" --skill "<skill_name>" --score <rating> --silent
   ```
   Parse the structured result:
   - `UPDATED:<agent>/<model>:<skill>:<new_score>` — Display: `Updated <skill> verified score for <agent>/<model>: <new_score>`

5. If the user skips or dismisses the question, continue without updating.

## Lock Release Procedure

This procedure is referenced from the Task Abort Procedure wherever a task lock may need to be released. (Step 9 archival lock releases are handled automatically by `aitask_archive.sh`.)

**When to execute:** After Step 4 has been reached (i.e., a lock may have been acquired). This applies to:
- Task Abort Procedure (task aborted after Step 4)
- Note: Step 9 lock releases are handled by `aitask_archive.sh` and do NOT need this procedure

**Procedure:**

- Release the task lock (best-effort, idempotent):
  ```bash
  ./.aitask-scripts/aitask_lock.sh --unlock <task_num> 2>/dev/null || true
  ```
  This is safe to call even if no lock was acquired (e.g., lock branch not initialized, or lock acquisition was skipped due to infrastructure issues). It succeeds silently in all these cases.

- **For child tasks where the parent is also being archived** (all children complete): also release the parent lock:
  ```bash
  ./.aitask-scripts/aitask_lock.sh --unlock <parent_task_num> 2>/dev/null || true
  ```
