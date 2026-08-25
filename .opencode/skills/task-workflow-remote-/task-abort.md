# Task Abort Procedure

This procedure is referenced from Step 6 (plan checkpoint) and Step 8 (user review) wherever the user selects "Abort task". It handles lock release, status revert, email clearing, and worktree cleanup.

**Run this procedure from the repo root.** Every step below invokes
`./.aitask-scripts/…` or `./ait git`, which an abort taken from inside
`aiwork/<task_name>` cannot even resolve — and the cleanup at the end removes
that directory, so a shell standing in it is left with no working directory at
all. `cd` to the repository root before starting.

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

- **Revert task status, clear assignment, and clear the deferred-plan marker:**
  ```bash
  ./.aitask-scripts/aitask_update.sh --batch <task_num> --status <selected_status> --assigned-to "" --plan-approved-at ""
  ```
  An abort rejects the plan, so `plan_approved_at` — "plan approved, implementation
  deliberately deferred" — must not survive it; otherwise every surface would keep
  advertising an approved plan the user just discarded. Like the ledger demotion
  above, it is unconditional and a no-op when no marker exists.

- **Commit the revert:**
  ```bash
  ./ait git add aitasks/ aiplans/
  ./ait git commit -m "ait: Abort t<N>: revert status to <status>"
  ```

- **Cleanup worktree/branch if created:**
  If a worktree was created — which happens at the top of **Step 7**, not in
  Step 5 (Step 5 only resolves the branch context):
  ```bash
  wt_rc=0
  wt_out="$(./.aitask-scripts/aitask_task_worktree.sh remove <task_name> --force)" || wt_rc=$?
  printf '%s\n' "$wt_out"
  ```
  Run this unconditionally. The helper resolves the worktree from its
  `git worktree list` record rather than from the conventional path, so a
  worktree that was moved out of `aiwork/<task_name>` is actually removed
  instead of silently missed (t1548). `--force` carries the abort's discard
  intent to `git worktree remove`.

  **Capture the status — do not run it under a bare `|| true`.** The exit status
  is non-zero for anything other than a fully clean teardown, so the procedure
  must not die on it; but `|| true` *alone* also swallows a usage or environment
  failure (exit 2 / 3 — not a repository, `git worktree list` failed), and those
  print **nothing** to stdout. An abort that treated no output as no residue
  would report a clean abort for a cleanup that never ran.

  So before reading the verdict, require a well-formed result: `wt_rc` is `0` or
  `1` **and** `$wt_out` is exactly three lines, the first starting `WORKTREE_`,
  the second `BRANCH_`, the third one of `CLEAN` / `PRESERVED` / `RESIDUE`.

  - **Anything else** (`wt_rc` of 2 or 3, empty output, a malformed shape) →
    **the cleanup did not run.** Report it as a failed cleanup, naming `wt_rc`
    and the helper's stderr, and tell the user the worktree and branch may both
    still exist. Do **not** report a clean abort. The usual cause is running the
    procedure from somewhere other than the repo root — see the prerequisite at
    the top of this file.

  An abort reached **before** the fork (a Step 6 "Abort task", or the Step 7
  ownership-guard abort that precedes the fork) is still a clean no-op: the
  helper prints `WORKTREE_NONE` / `BRANCH_NONE` / `CLEAN`, exits 0, and writes
  nothing to stderr. Nothing is removed and nothing is claimed to have been.

  **With a well-formed result, read the three lines and report what they say —
  do not assume a clean abort.** The last line is the verdict:

  - `CLEAN` — the worktree and branch are gone (or never existed). Report the
    abort normally.
  - `PRESERVED` — the teardown did exactly what it should and deliberately kept
    something. The case that reaches here is `BRANCH_KEPT unmerged_into:<ref>`:
    the branch carries commits that are not in `<ref>`, and the procedure uses
    `git branch -d`, never `-D`, so an abort never destroys them. Tell the user
    calmly: "your commits are still on `aitask/<task_name>`" — and mention
    `git branch -D aitask/<task_name>` only as the way to discard them *if they
    want to*, never as a cleanup step to run.
  - `RESIDUE` — the teardown could not finish. Name each `WORKTREE_KEPT
    <reason> <path>` / `BRANCH_KEPT <reason> <branch>` line with its remedy, and
    do **not** report a clean abort:
    - `stale_record` — the worktree was moved by hand; the record still names
      the old path. Nothing was pruned and the branch was left alone on purpose,
      because that record is what keeps the branch un-deletable while the user's
      work sits in the moved directory. Remedy: `git worktree repair <new path>`
      to re-link it, or `git worktree prune` if it really is abandoned.
    - `locked` — the user locked this worktree. Remedy: `git worktree unlock
      <path>`, then re-run.
    - `dirty` — uncommitted changes (only when `--force` was omitted).
    - `main_worktree` — `aitask/<task_name>` is checked out at the repo root.
      Remedy: check out another branch there first.
    - `unsafe_path` — the worktree path contains a tab, newline or carriage
      return; the helper refuses to operate on it. Remedy: move it somewhere
      without control characters (`git worktree move`), then re-run.

- **Inform user:**
  "Task t<N> has been reverted to '<status>' and is available for others."
