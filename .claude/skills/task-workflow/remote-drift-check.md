# Remote Drift Check Procedure

Detects whether `origin/<branch>` has commits the local `<branch>` is missing, with stronger emphasis when the missing commits touch files referenced in the plan. Runs for the **base branch**, and — when the merge target differs from it — for the **output branch** too, since a base that has not moved does not imply the merge target has not. Invoked from `planning.md` Checkpoint after the user (or profile) chooses to start implementation, before control returns to `SKILL.md` Step 7.

## Input

| Variable | Type | Description |
|----------|------|-------------|
| `base_branch` | string | Base branch from the plan metadata header (e.g., `main`) |
| `output_branch` | string | Merge target, resolved from the plan header by the **same** two-rung rule `SKILL.md` Step 9 uses: the `Output branch:` field when present, otherwise `main`. Never `base_branch` — resolving it differently here would check a branch the workflow is not going to merge into |
| `plan_file` | string | Path to the externalized plan file (e.g., `aiplans/p708_*.md`) |
| `active_profile` | object/null | Loaded execution profile (or null) |
| `task_id` | string | Task identifier (used in the "Stop and re-verify" branch) |
| `task_num` | string | Numeric task id for `aitask_update.sh` (parent number for child tasks) |

## Procedure

{# ---------- remote_drift_check ---------- #}{% if profile.remote_drift_check is defined and profile.remote_drift_check == "skip" %}
1. **Profile '{{ profile.name }}' sets `remote_drift_check: skip`** — return immediately to the caller with no display.
{% else %}{# remote_drift_check: key absent or value != "skip" #}
1. **Profile check.** If the active profile has `remote_drift_check: skip`, return immediately with no display.
{% endif %}{# ---------- end remote_drift_check ---------- #}

2. **Run the helper — the base pass, then conditionally the output pass:**

   ```bash
   ./.aitask-scripts/aitask_remote_drift_check.sh "<base_branch>" "<plan_file>"
   ```

   Then bind the merge target from the plan header — the value there was validated when the externalize helper wrote it, and binding a variable (rather than pasting the literal) keeps a ref name containing shell metacharacters inert:

   ```bash
   output_branch=$(sed -n 's/^Output branch: //p' "<plan_file>" | head -n1)
   [ -n "$output_branch" ] || output_branch=main
   ```

   Then, **only if `"$output_branch"` differs from `<base_branch>`**, run the helper a second time for the merge target, with `--unsynced`:

   ```bash
   ./.aitask-scripts/aitask_remote_drift_check.sh --unsynced "$output_branch" "<plan_file>"
   ```

   `--unsynced` suppresses the legacy-mode short-circuit. In legacy mode `task_sync()` runs a bare `git pull --rebase`, refreshing only the *current* branch — the output branch is never checked out during implementation, so it is never pulled and the shortcut's "already pulled" premise does not hold for it. Without the flag this pass would return `LEGACY_MODE_SKIP` and the coverage would be inert on every legacy-mode project. **Never pass `--unsynced` on the base pass.**

3. **Parse each run's stdout independently** (line-oriented `KEY:value` protocol). Label every display with the branch of the run it came from — `<branch>` below means the branch that run was invoked with.

   - `LEGACY_MODE_SKIP` / `NO_REMOTE` / `UP_TO_DATE` → return for that pass; no display.
   - `FETCH_FAILED` → return for that pass; **no display, on both passes**. It means only "could not reach the remote" (timeout, auth, network) and is *not* evidence about the local branch. Reporting it as a missing branch would cry wolf on every flaky network and train the user to click past the warning below.
   - `LOCAL_BRANCH_MISSING`:
     - **Base pass** → return; no display (as before).
     - **Output pass** → display: "Output branch `<output_branch>` is not present locally — the Step 9 merge will fail." Then proceed to the AskUserQuestion below. This converts a mid-workflow Step 9 hard failure into a planning-time notice, and is the highest-value output of this procedure.
   - `AHEAD:<n>` followed by `NO_OVERLAP`:
     - If profile is `strong-only`: return; no display.
     - Else (default `warn`): display "Remote `<branch>` is ahead by `<n>` commit(s); none touch files in your plan." Then proceed to AskUserQuestion below.
   - `AHEAD:<n>` followed by one or more `OVERLAP:<file>` lines (always treated as strong, regardless of `warn` or `strong-only`):
     - Display: "Remote `<branch>` is ahead by `<n>` commit(s) and changes the following file(s) your plan also targets:" then list each overlapping file on its own line.
     - Proceed to AskUserQuestion below.

   **Collect both passes before prompting.** If both produce a display, show both, then ask the step-4 question **exactly once**. Never issue one prompt per pass — two prompts for one plan can collect conflicting answers ("Continue anyway" then "Stop and re-verify plan").

4. **AskUserQuestion:**

   - Question: "How would you like to proceed?"
   - Header: "Remote drift"
   - Options:
     - "Stop and re-verify plan" (description: "Release the lock, revert task to Ready, and end the workflow — pull the drifted branch(es) then re-pick the task")
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
     5. Display: "Plan saved. Task t\<task_id\> reverted to Ready due to remote drift on \<the branch(es) that drifted — name each one\>. Pull them, then re-pick with `/aitask-pick <task_id>` in a fresh context." If the output pass reported `LOCAL_BRANCH_MISSING`, say instead that the output branch must be created or fetched before the task can be merged.

     End the workflow. Do NOT proceed to Step 7.

   - **"Continue anyway":** Return so the caller can proceed to Step 7.

   - **"Abort task":** Execute the **Task Abort Procedure** (`task-abort.md`).

## Notes

- Always best-effort. Network failures, missing remotes, and legacy-mode setups all return silently without prompting. The one exception is `LOCAL_BRANCH_MISSING` on the **output** pass: that is a certain Step 9 failure, established without touching the network, so it is surfaced rather than swallowed.
- Idempotent: safe to call multiple times if the workflow re-enters the checkpoint via "Revise plan".
- Worktree mode: the helper runs from the repo root (the working directory at workflow entry); the worktree directory is irrelevant for the drift comparison because the helper compares `<branch>..origin/<branch>`, not the worktree's `aitask/<task_name>` branch.
- For child tasks, `<task_num>` in the "Stop and re-verify" branch refers to the **child** task id (e.g., `16_2`). The parent's status remains `Ready` (it has pending children) — only the active child is reverted.
