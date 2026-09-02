# Approved-Plan Stop Sequence Procedure

The single release-and-revert sequence used by **every** branch that ends a
session on an **approved plan that will not be implemented now**. Four call
sites share it:

- `planning.md` Checkpoint → **"Approve and stop here"** (`stop_reason=deferred`)
- `remote-drift-check.md` step 5 → **"Stop and re-verify plan"** (`stop_reason=drift`)
- `resource-admission.md` step 4 → **the hook refused, or could not decide**
  (`stop_reason=resource_admission`)
- `parallel-admission.md` step 7 → **the user chose "Stop and re-plan"**
  (`stop_reason=parallel_admission`)

Every one of them approved the plan and then chose — or was told — to stop, so
each owes the ledger the same record and the workspace the same release. Keeping the sequence in one
file is deliberate: it previously lived inline in `planning.md`, and
`remote-drift-check.md` reproduced only that branch's *numbered* steps — silently
dropping the gate recording that sat above the list (t1380 Defect 1). A
reference cannot drop a step the way a copy can. For the same reason the steps
below are **bullets, not a numbered list**: nothing here can read as "optional
preamble" to a numbered sequence.

This is a **stop, not an abort**: the plan is kept and the task returns to
`Ready`. Whether a worktree/branch is left behind depends on which call site got
here — see the Notes. For a rejected plan see `task-abort.md`.

## Input context

| Variable | Description |
|----------|-------------|
| `task_id` | The task being stopped (`16` or `16_2`). |
| `task_num` | Numeric id for `aitask_update.sh` — the task's **own** id; for a child that is the child id (`16_2`), never the parent's. |
| `plan_file` | Path to the externalized plan (e.g. `aiplans/p16_add_auth.md`). |
| `stop_reason` | `deferred` (implementation postponed), `drift` (remote drifted), `resource_admission` (the host could not afford the phase), or `parallel_admission` (the user stopped on an in-flight collision). Recorded as the gate's `note=`, so the ledger says *why* the session stopped. |
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

- **Revert the task status to `Ready`, clear `assigned_to`, and settle the
  deferred-plan marker — one call, selected by `stop_reason`.**

  `plan_approved_at` records "this plan was approved and implementation was
  **deliberately deferred**". The disposition follows that meaning, not the call
  site: a stop that leaves the plan **intact and awaiting implementation** stamps
  the marker, and a stop that **invalidates** the plan clears it. There are still
  exactly two commands, and each `stop_reason` selects one of them:

  | `stop_reason` | the plan afterwards | marker |
  |---|---|---|
  | `deferred` | approved, implementation postponed by the user | **stamp** |
  | `resource_admission` | approved, implementation postponed by the host's capacity | **stamp** |
  | `drift` | must be re-verified before it can be implemented | **clear** |
  | `parallel_admission` | must be re-checked against in-flight work before it can be implemented | **clear** |

  The two **clear** rows mean the opposite of the two **stamp** rows — those
  flows stopped *because* the plan must be re-checked before it may be
  implemented — so they **clear** the marker rather than refreshing it; leaving
  (or renewing) it there would advertise a plan as
  implementation-ready on exactly the path that just established it is not. The
  marker is folded into the revert call rather than added as a separate bullet so
  no branch can perform one without the other.

  **Run exactly ONE of the two commands below — the one this call site's
  `stop_reason` selects. Never both, and never the other one:**

  - **If `stop_reason` is `deferred`** (the Checkpoint's "Approve and stop here")
    **or `resource_admission`** (the admission hook's park), run **only** this:

    ```bash
    ./.aitask-scripts/aitask_update.sh --batch <task_num> --status Ready --assigned-to "" --plan-approved-at now
    ```

  - **If `stop_reason` is `drift`** (the drift check's "Stop and re-verify plan")
    **or `parallel_admission`** (the preflight's user-elected "Stop and re-plan"),
    run **only** this:

    ```bash
    ./.aitask-scripts/aitask_update.sh --batch <task_num> --status Ready --assigned-to "" --plan-approved-at ""
    ```

  There is no fifth case: `stop_reason` is documented in the Input context table
  as exactly `deferred`, `drift`, `resource_admission` or `parallel_admission`. If it is anything else,
  stop and report it rather than guessing a marker disposition — a new stop path
  must state which side of the table above it belongs on before it may use this
  sequence.

- **Commit the status revert and push:**

  ```bash
  ./ait git add aitasks/
  ./ait git commit -m "<revert_commit_message>" 2>/dev/null || true
  ./ait git push
  ```

- **Display `<closing_message>`** and **end the workflow** — do NOT proceed to
  Step 7.

## Notes

- **Whether a worktree exists at all here depends on the call site.** Reached
  from `planning.md`'s "Approve and stop here", `remote-drift-check.md`'s
  "Stop and re-verify plan", `resource-admission.md`'s park, or
  `parallel-admission.md`'s user-elected stop at the planning Checkpoint, **no
  worktree exists yet** — those stops all happen before `SKILL.md` Step 7's
  deferred fork
  (the admission hook is consulted immediately before it, for this reason among
  others). That is the improvement: the drift
  stop no longer strands a branch cut from the pre-drift HEAD, and the re-pick
  cuts a fresh one from the pulled base. Reached from Step 7's risk-mitigation
  "before" stop, the worktree **does** exist and is intentionally left in place —
  the next pick reuses it via the reuse check at the fork site. The parallel
  preflight's **other** call site — `SKILL.md` **Re-entry Routing**'s `IMPLEMENT`
  route — is the same case: a worktree from the earlier session may already
  exist, and is likewise left in place. Only the **Task Abort Procedure** removes
  a worktree.
- **The marker is a display/prompt signal, never a routing one.** `ait ls -v`
  shows it (and `ait ls --plan-approved` filters on it), and `planning.md` §6.0
  names it in the existing-plan prompt — but nothing routes on it. The re-pick
  still goes through §6.0's plan preference and therefore through the Checkpoint
  and its Remote Drift Check, exactly as `aidocs/gates/ledger-driven-reentry.md`
  requires. It is consumed at the top of `SKILL.md` Step 7's implementation body,
  and cleared by a replan (§6.0), an abort (`task-abort.md`) and a cross-repo
  demotion (`cross-repo-child-assignment.md`). A `resource_admission` park never
  reaches that consumption point — it stops earlier in Step 7 — which is why it
  stamps the marker rather than clearing it.
- The revert to `Ready` is what makes the re-pick land in the planning path
  rather than Re-entry Routing — which is what stops a "stop → pull → re-pick"
  loop from re-triggering the very check that sent the user away.
