# Remote Drift Check Procedure

Detects whether `origin/<base-branch>` has commits the local `<base-branch>` is missing, with stronger emphasis when the missing commits touch files referenced in the plan. Invoked from `planning.md` Checkpoint after the user (or profile) chooses to start implementation, before control returns to `SKILL.md` Step 7.

## Input

| Variable | Type | Description |
|----------|------|-------------|
| `base_branch` | string | Base branch from the plan metadata header (e.g., `main`) |
| `plan_file` | string | Path to the externalized plan file (e.g., `aiplans/p708_*.md`) |
| `active_profile` | object/null | Loaded execution profile (or null) |
| `task_id` | string | Task identifier (used in the "Stop and re-verify" branch) |
| `task_num` | string | Numeric task id for `aitask_update.sh` (parent number for child tasks) |

## Procedure

1. **Profile check.** If the active profile has `remote_drift_check: skip`, return immediately with no display.

2. **Run the helper:**

   ```bash
   ./.aitask-scripts/aitask_remote_drift_check.sh "<base_branch>" "<plan_file>"
   ```

3. **Parse stdout** (line-oriented `KEY:value` protocol):

   - `LEGACY_MODE_SKIP` / `NO_REMOTE` / `FETCH_FAILED` / `UP_TO_DATE` → return; no display.
   - `AHEAD:<n>` followed by `NO_OVERLAP`:
     - If profile is `strong-only`: return; no display.
     - Else (default `warn`): display "Remote `<base_branch>` is ahead by `<n>` commit(s); none touch files in your plan." Then proceed to AskUserQuestion below.
   - `AHEAD:<n>` followed by one or more `OVERLAP:<file>` lines (always treated as strong, regardless of `warn` or `strong-only`):
     - Display: "Remote `<base_branch>` is ahead by `<n>` commit(s) and changes the following file(s) your plan also targets:" then list each overlapping file on its own line.
     - Proceed to AskUserQuestion below.

4. **AskUserQuestion:**

   - Question: "How would you like to proceed?"
   - Header: "Remote drift"
   - Options:
     - "Stop and re-verify plan" (description: "Release the lock, revert task to Ready, and end the workflow — pull `<base_branch>` then re-pick the task")
     - "Continue anyway" (description: "Proceed to implementation; you may need to handle conflicts at merge time")
     - "Abort task" (description: "Discard the task and revert status")

5. **Branches:**

   - **"Stop and re-verify plan":** Run the same release-and-revert sequence as the planning-checkpoint "Approve and stop here" branch (see `planning.md` Checkpoint, "Approve and stop here"):

     1. Ensure the plan file is committed (idempotent):
        ```bash
        ./ait git add aiplans/<plan_file>
        ./ait git commit -m "ait: Add plan for t<task_id>" 2>/dev/null || true
        ```
     2. Release the task lock via the **Lock Release Procedure** (`lock-release.md`).
     3. Revert the task status to `Ready` and clear `assigned_to`:
        ```bash
        ./.aitask-scripts/aitask_update.sh --batch <task_num> --status Ready --assigned-to ""
        ```
     4. Commit and push the status revert:
        ```bash
        ./ait git add aitasks/
        ./ait git commit -m "ait: Revert t<task_num> to Ready (remote drift)" 2>/dev/null || true
        ./ait git push
        ```
     5. Display: "Plan saved. Task t\<task_id\> reverted to Ready due to remote drift on `<base_branch>`. Pull the latest base, then re-pick with `/aitask-pick <task_id>` in a fresh context."

     End the workflow. Do NOT proceed to Step 7.

   - **"Continue anyway":** Return so the caller can proceed to Step 7.

   - **"Abort task":** Execute the **Task Abort Procedure** (`task-abort.md`).

## Notes

- Always best-effort. Network failures, missing remotes, and legacy-mode setups all return silently without prompting.
- Idempotent: safe to call multiple times if the workflow re-enters the checkpoint via "Revise plan".
- Worktree mode: the helper runs from the repo root (the working directory at workflow entry); the worktree directory is irrelevant for the drift comparison because the helper compares `<base-branch>..origin/<base-branch>`, not the worktree's `aitask/<task_name>` branch.
- For child tasks, `<task_num>` in the "Stop and re-verify" branch refers to the **child** task id (e.g., `16_2`). The parent's status remains `Ready` (it has pending children) — only the active child is reverted.
