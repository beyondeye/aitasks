# Task Abort Procedure

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

- **Release task lock:** Execute the **Lock Release Procedure** (see `lock-release.md`) for the task.

- **Re-open a recorded plan approval (ledger-conditional, NOT profile-gated):** An abort rejects the plan, so a `plan_approved` pass recorded by an earlier session must not survive it. Check whether one exists:

  ```bash
  ./.aitask-scripts/aitask_gate.sh recorded-pass <task_id> plan_approved
  ```

  - Exit **0** — a previous session recorded the plan as approved. Append the demotion so the ledger stops claiming approval (the ledger is derived last-marker-wins, so a later `fail` correctly re-opens the checkpoint and `resume-point` falls back to `PLAN`):

    ```bash
    ./.aitask-scripts/aitask_gate_record.sh <task_id> plan_approved fail type=human note=aborted
    ```

  - Exit **1** — nothing recorded; skip. This is the common case, and the *only* case on a project that has never run a gate-recording profile.

  **Why this is not wrapped in the `record_gates` guard.** A task recorded under a profile that sets `record_gates` (e.g. `fast`) can be aborted under one that does not (e.g. `default`), and a Jinja guard would render the demotion away in exactly the case where the stale entry exists. Gating on **ledger content** instead makes it a no-op wherever no approval was ever recorded — so behaviour under `record_gates: false` is unchanged. (This mirrors the reasoning in `aidocs/gates/ledger-driven-reentry.md` for why the re-entry prose itself is profile-invariant.) Without this step the safety would rest entirely on Step 3 Check 5's `Implementing` status gate — an accident of the status revert below, not an invariant.

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
