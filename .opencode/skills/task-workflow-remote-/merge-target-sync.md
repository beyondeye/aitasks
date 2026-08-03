# Merge-Target Sync Pre-flight Procedure

Refreshes the **merge target** before a resumed task hands off to Step 9.
Invoked from **Re-entry Routing**'s `POSTIMPL` route only (see `SKILL.md`).

## Why this exists

**Step 9 never fetches.** Its pre-flight checks only that
`refs/heads/<output_branch>` exists locally and is not held by another worktree,
and `git merge` is a purely local operation. So when `origin/<output_branch>`
has advanced past the local branch, the merge **succeeds cleanly**, the local
branch quietly diverges, and the problem surfaces only when the user later
pushes and git rejects it as non-fast-forward. A resumed task is exactly where
that staleness is most likely — its local refs are as old as the interruption.

## Why not the Remote Drift Check Procedure

At `POSTIMPL` the code is already committed and `review_approved` recorded; the
plan is no longer being followed, so the **base** branch is irrelevant. More
importantly, the drift check's only actionable branch ("Stop and re-verify
plan") releases the lock and reverts the task to `Ready` — the right move before
implementation, and the wrong move for work that is already reviewed and
committed. This procedure keeps the same detection (it calls the same helper)
and swaps in recovery actions that fit the post-implementation state.

## Input context

| Variable | Description |
|----------|-------------|
| `output_branch` | The merge target, already resolved from the plan header **and validated** by the caller (Re-entry Routing's branch-resolution step). Never resolve it from `profile.output_branch` — a resumed session may run under a different profile. |
| `plan_file` | Path to the externalized plan (used for the file-overlap emphasis). |
| `task_id` | Task identifier, for display. |

## Procedure

1. **Run the helper for the merge target:**

   ```bash
   ./.aitask-scripts/aitask_remote_drift_check.sh --unsynced "$output_branch" "<plan_file>"
   ```

   `--unsynced` is **mandatory** here. The output branch is never checked out
   during implementation, so `task_sync()`'s "already pulled" premise does not
   hold for it; without the flag this pass returns `LEGACY_MODE_SKIP` and the
   whole procedure is inert on every legacy-mode project.

2. **Parse the single result** (line-oriented `KEY:value` protocol):

   - `UP_TO_DATE` / `NO_REMOTE` / `LEGACY_MODE_SKIP` → return; no display.
   - `FETCH_FAILED` → return; **no display**. It means only "could not reach the
     remote" and is not evidence about the local branch — same cry-wolf rule the
     Remote Drift Check applies.
   - `LOCAL_BRANCH_MISSING` → display: "Output branch `<output_branch>` is not
     present locally — the Step 9 merge will fail." Then return. Step 9's own
     pre-flight stops on this too; surfacing it here saves the user a pointless
     merge-approval prompt.
   - `AHEAD:<n>` (with or without following `OVERLAP:<file>` lines) → display
     "Remote `<output_branch>` is ahead by `<n>` commit(s)" plus, when present,
     "and changes the following file(s) your plan also targets:" and each
     overlapping file on its own line. Then ask.

3. **AskUserQuestion:**

   - Question: "The merge target `<output_branch>` is behind its remote. How
     would you like to proceed?"
   - Header: "Merge target"
   - Options:
     - "Sync `<output_branch>` now (Recommended)" (description: "Fast-forward the
       local branch to origin, then continue to the merge")
     - "Continue anyway" (description: "Merge into the stale local branch; the
       eventual push may be rejected as non-fast-forward")
     - "Stop here" (description: "End the session without merging; the task stays
       in flight and can be re-picked")

4. **Branches:**

   - **"Sync `<output_branch>` now":** fast-forward only — never rewrite.

     ```bash
     git checkout "$output_branch" --   # trailing `--`: the arg is a branch, never a pathspec
     git symbolic-ref --short HEAD      # MUST print "$output_branch"; if not, STOP — do not merge
     git merge --ff-only "origin/$output_branch"
     ```

     Use the quoted **variable**, never the literal: binding is what keeps a ref
     name containing shell metacharacters inert (the same rule Step 9 states).

     A non-zero `git merge --ff-only` means the local branch holds commits
     `origin` does not — a real divergence, not staleness. **Stop and ask the
     user** how to reconcile it. Do **not** rebase, reset, force, or retry
     without `--ff-only`: this procedure is allowed to move the branch forward,
     never to move it sideways.

     On success, return so the caller proceeds to Step 9.

   - **"Continue anyway":** return so the caller proceeds to Step 9, having
     warned: "Merging into a stale `<output_branch>`; the merge will succeed
     locally but the push may be rejected as non-fast-forward."

   - **"Stop here":** **end the session without merging.** Do **not** revert the
     task status and do **not** release the lock — the code is committed and
     `review_approved` is recorded, so the task legitimately stays
     `Implementing` at `POSTIMPL` and re-picking it resumes here. Display: "Not
     merged. Pull `<output_branch>`, then re-pick t\<task_id\> to finish the
     merge."

## Notes

- Best-effort detection, deliberate recovery: every network failure mode returns
  silently, and the only mutation is a fast-forward the user explicitly asked
  for.
- Idempotent: running it twice on an already-synced branch returns
  `UP_TO_DATE` and does nothing.
- Run from the repo root, not from `aiwork/<task_name>/` — the helper compares
  `<branch>..origin/<branch>`, and the `git checkout` in the sync branch needs
  the main worktree.
- **The same staleness affects the non-resumed Step 9 path.** Wiring this
  procedure in there unconditionally would add a network fetch and a possible
  prompt to every task's merge — a behaviour change for every user that deserves
  its own decision, so it is tracked separately rather than folded in here.
