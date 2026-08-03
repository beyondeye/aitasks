# Approved-Plan Stop Sequence Procedure

The single release-and-revert sequence used by **every** branch that ends a
session on an **approved plan that will not be implemented now**. Two call sites
share it:

- `planning.md` Checkpoint → **"Approve and stop here"** (`stop_reason=deferred`)
- `remote-drift-check.md` step 5 → **"Stop and re-verify plan"** (`stop_reason=drift`)

Both branches approved the plan and then chose to stop, so both owe the ledger
the same record and the workspace the same release. Keeping the sequence in one
file is deliberate: it previously lived inline in `planning.md`, and
`remote-drift-check.md` reproduced only that branch's *numbered* steps — silently
dropping the gate recording that sat above the list (t1380 Defect 1). A
reference cannot drop a step the way a copy can. For the same reason the steps
below are **bullets, not a numbered list**: nothing here can read as "optional
preamble" to a numbered sequence.

This is a **stop, not an abort**: the plan is kept, the task returns to `Ready`,
and the worktree/branch are left in place. For a rejected plan see
`task-abort.md`.

## Input context

| Variable | Description |
|----------|-------------|
| `task_id` | The task being stopped (`16` or `16_2`). |
| `task_num` | Numeric id for `aitask_update.sh` — the task's **own** id; for a child that is the child id (`16_2`), never the parent's. |
| `plan_file` | Path to the externalized plan (e.g. `aiplans/p16_add_auth.md`). |
| `stop_reason` | `deferred` (implementation postponed) or `drift` (remote drifted). Recorded as the gate's `note=`. |
| `revert_commit_message` | Commit subject for the status revert, e.g. `ait: Revert t<task_num> to Ready after plan approval`. |
| `closing_message` | The message shown to the user, naming the re-pick command. |

## Procedure
{# ---------- record_gates ---------- #}{% if profile.record_gates is defined and profile.record_gates %}
- **Record the approval — once.** Reaching this procedure means the plan *was*
  approved, so the ledger must say so even though implementation is not
  starting. Check first whether an earlier session already recorded it:

  ```bash
  ./.aitask-scripts/aitask_gate.sh recorded-pass <task_id> plan_approved
  ```

  - Exit **1** (not currently recorded as `pass`) → execute the **Gate Recording
    Procedure** (see `gate-recording.md`) with `task_id`,
    `gate_name=plan_approved`, `status=pass`,
    `fields="type=human note=<stop_reason>"`.
  - Exit **0** → **skip**. The approval is already on the ledger (this is a
    re-entered task stopping again); re-appending would only add a redundant
    block and commit.

  **This is an audit record of the approval, not a routing signal.** Step 3
  Check 5 consults the ledger only for a task whose status is `Implementing`,
  and the revert bullet below returns this task to `Ready` — so on re-pick the
  recorded entry routes nothing. What resumes the task is §6.0's existing-plan
  preference (`plan_preference` / `plan_preference_child`), which reaches the
  Checkpoint and therefore re-runs the Remote Drift Check. The two mechanisms
  are deliberately different; see `aidocs/gates/ledger-driven-reentry.md`.
{% endif %}{# ---------- end record_gates ---------- #}
- **Ensure the plan file is committed** (idempotent — may be a no-op if the Plan
  Externalization Procedure already committed it):

  ```bash
  ./ait git add aiplans/<plan_file>
  ./ait git commit -m "ait: Add plan for t<task_id>" 2>/dev/null || true
  ```

- **Release the task lock** via the **Lock Release Procedure** (see
  `lock-release.md`).

- **Revert the task status to `Ready` and clear `assigned_to`:**

  ```bash
  ./.aitask-scripts/aitask_update.sh --batch <task_num> --status Ready --assigned-to ""
  ```

- **Commit the status revert and push:**

  ```bash
  ./ait git add aitasks/
  ./ait git commit -m "<revert_commit_message>" 2>/dev/null || true
  ./ait git push
  ```

- **Display `<closing_message>`** and **end the workflow** — do NOT proceed to
  Step 7.

## Notes

- **The worktree and `aitask/<task_name>` branch are intentionally left in
  place.** This is a stop, not an abort: the next pick reuses them. Only the
  **Task Abort Procedure** removes them.
- The revert to `Ready` is what makes the re-pick land in the planning path
  rather than Re-entry Routing — which is what stops a "stop → pull → re-pick"
  loop from re-triggering the very check that sent the user away.
