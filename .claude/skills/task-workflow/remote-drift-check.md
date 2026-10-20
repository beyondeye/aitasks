# Remote Drift Check Procedure

Detects whether `origin/<branch>` has commits the local `<branch>` is missing, with stronger emphasis when the missing commits touch files referenced in the plan. Runs for the **base branch**, and — when the merge target differs from it — for the **output branch** too, since a base that has not moved does not imply the merge target has not. Invoked from two places, both immediately before implementation starts: `planning.md`'s Checkpoint, after the user (or profile) chooses to start implementation; and `SKILL.md`'s **Re-entry Routing** on the `IMPLEMENT` route, where a resumed task's plan is by construction the oldest relative to the remotes. (A `POSTIMPL` resume runs `merge-target-sync.md` instead — see that file for why.) Control returns to `SKILL.md` Step 7 in both cases.

## Input

| Variable | Type | Description |
|----------|------|-------------|
| `base_branch` | string | The Step-5 resolved base branch (e.g., `main`) — equivalently the plan header's `Base branch:` field, which records that resolution. `planning.md`'s Checkpoint passes it from Step 5 context; **Re-entry Routing** binds it from the header. The two agree by construction (t1277) |
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
   if ./.aitask-scripts/aitask_remote_drift_check.sh "<base_branch>" "<plan_file>"; then
     drift_rc=0
   else
     drift_rc=$?
   fi
   echo "DRIFT_RC:$drift_rc"
   ```

   The trailing `DRIFT_RC:<rc>` line is the run's exit status, printed so step 3 can read it alongside the output — it is not a protocol token. It is captured in the `if` form because errexit is suspended inside an `if` condition: under `set -e`, `helper; echo "DRIFT_RC:$?"` would exit on a non-zero status (e.g. `EXTRACT_FAILED`'s 3) before the line is printed.

   Then bind the merge target from the plan header — the value there was validated when the externalize helper wrote it, and binding a variable (rather than pasting the literal) keeps a ref name containing shell metacharacters inert:

   ```bash
   output_branch=$(sed -n 's/^Output branch: //p' "<plan_file>" | head -n1)
   [ -n "$output_branch" ] || output_branch=main
   ```

   Then, **only if `"$output_branch"` differs from `<base_branch>`**, run the helper a second time for the merge target, with `--unsynced`:

   ```bash
   if ./.aitask-scripts/aitask_remote_drift_check.sh --unsynced "$output_branch" "<plan_file>"; then
     drift_rc=0
   else
     drift_rc=$?
   fi
   echo "DRIFT_RC:$drift_rc"
   ```

   `--unsynced` suppresses the legacy-mode short-circuit. In legacy mode `task_sync()` runs a bare `git pull --rebase`, refreshing only the *current* branch — the output branch is never checked out during implementation, so it is never pulled and the shortcut's "already pulled" premise does not hold for it. Without the flag this pass would return `LEGACY_MODE_SKIP` and the coverage would be inert on every legacy-mode project. **Never pass `--unsynced` on the base pass.**

3. **Parse each run's stdout independently** (line-oriented `KEY:value` protocol). Label every display with the branch of the run it came from — `<branch>` below means the branch that run was invoked with.

   **First classify the run.** It is accepted only as one of these **complete outcomes** — the protocol shape *and* the exit status must both match:

   - `DRIFT_RC:0` and exactly one of `LEGACY_MODE_SKIP` / `LOCAL_BRANCH_MISSING` / `NO_REMOTE` / `FETCH_FAILED` / `UP_TO_DATE`;
   - `DRIFT_RC:0` and `AHEAD:<n>`, then zero or more `OVERLAP:` lines, then zero or more `WEAK_OVERLAP:` lines, **ending in a verdict**: `NO_OVERLAP` when there is no `OVERLAP` line, otherwise at least one `OVERLAP` line;
   - `DRIFT_RC:3` with `EXTRACT_FAILED` as the last token — alone, or after `AHEAD:<n>` — a complete *failure* outcome.

   Anything else is an **incomplete run**: any other non-zero exit (2 is a usage error from a malformed invocation, 128+n a killed helper), exit 3 without `EXTRACT_FAILED`, `EXTRACT_FAILED` with exit 0, `AHEAD:<n>` with no verdict after it, empty stdout, or an unrecognised line. Never read an incomplete run as one of the silent outcomes below — the bullets for those apply to complete outcomes only.

   - `LEGACY_MODE_SKIP` / `NO_REMOTE` / `UP_TO_DATE` → return for that pass; no display.
   - `FETCH_FAILED` → return for that pass; **no display, on both passes**. It means only "could not reach the remote" (timeout, auth, network) and is *not* evidence about the local branch. Reporting it as a missing branch would cry wolf on every flaky network and train the user to click past the warning below.
   - `LOCAL_BRANCH_MISSING`:
     - **Base pass** → return; no display (as before).
     - **Output pass** → display: "Output branch `<output_branch>` is not present locally — the Step 9 merge will fail." Then proceed to the AskUserQuestion below. This converts a mid-workflow Step 9 hard failure into a planning-time notice, and is the highest-value output of this procedure.
   - `AHEAD:<n>` followed by `NO_OVERLAP` (possibly with `WEAK_OVERLAP:<file>` lines before it):
     - If profile is `strong-only`: return; no display. `WEAK_OVERLAP` lines never escalate — they are evidence, not a verdict.
     - Else (default `warn`): display "Remote `<branch>` is ahead by `<n>` commit(s); none touch files in your plan." When there are `WEAK_OVERLAP:<file>` lines, display instead "Remote `<branch>` is ahead by `<n>` commit(s); none directly touch files in your plan, but these may be referenced:" and list each weak file on its own line. Then proceed to AskUserQuestion below.
   - `AHEAD:<n>` followed by one or more `OVERLAP:<file>` lines (always treated as strong, regardless of `warn` or `strong-only`):
     - Display: "Remote `<branch>` is ahead by `<n>` commit(s) and changes the following file(s) your plan also targets:" then list each overlapping file on its own line. If `WEAK_OVERLAP:<file>` lines follow, list them after, under "Possibly referenced:".
     - Proceed to AskUserQuestion below.
   - `EXTRACT_FAILED` (exit 3), **on either pass** — the overlap scan could not run: the plan file is unreadable, `lib/plan_paths.py` is unreachable, or there is no usable Python. The Python check runs *before* the fetch, so this is not a network problem and is never folded into `FETCH_FAILED`.
     - Display: "Remote drift check for `<branch>` could not run its overlap scan (EXTRACT_FAILED) — check that the plan file is readable; `ait setup` repairs a broken install." When an `AHEAD:<n>` line preceded it, prefix "Remote `<branch>` is ahead by `<n>` commit(s), but …".
     - It is the *absence* of a verdict, not a verdict: `strong-only` does not suppress it. Proceed to AskUserQuestion below.
   - **Incomplete run, on either pass** (see the classification above):
     - Display: "Remote drift check for `<branch>` did not complete (exit `<rc>`) — no drift verdict for this branch.", followed by the helper's stderr.
     - Proceed to AskUserQuestion below.

   `OVERLAP` means the plan names that remote-changed path in full. `WEAK_OVERLAP` means the plan mentions it only as a bare root-level name with no extension (`ait`, `Makefile` — the same word is ordinary prose, e.g. "run `ait setup`") or by a module-relative trailing sub-path (`internal/x/main.go` for `goengines/internal/x/main.go`). The helper tests every remote-changed path, whatever its language or extension.

   **Collect both passes before prompting.** If both produce a display, show both, then ask the step-4 question **exactly once**. Never issue one prompt per pass — two prompts for one plan can collect conflicting answers ("Continue anyway" then "Stop and re-verify plan").

   Steps 4 and 5 depend on what the collected passes **established**, so keep the two facts apart — pulling repairs drift, and it repairs nothing about a check that could not run:

   - **proven drift** — a pass whose complete outcome carries `AHEAD:<n>` (with a verdict, or followed by `EXTRACT_FAILED`), or the output pass's `LOCAL_BRANCH_MISSING`;
   - **check failure** — a pass that ended in `EXTRACT_FAILED`, or an incomplete run.

4. **AskUserQuestion:**

   - Question: "How would you like to proceed?"
   - Header: "Remote drift"
   - Options:
     - "Stop and re-verify plan" — the description depends on what step 3 established:
       - proven drift only: (description: "Release the lock, revert task to Ready, and end the workflow — pull the drifted branch(es) then re-pick the task")
       - check failure only: (description: "Release the lock, revert task to Ready, and end the workflow — repair the failed check (see above), then re-pick the task")
       - both: (description: "Release the lock, revert task to Ready, and end the workflow — pull the drifted branch(es) and repair the failed check, then re-pick the task")
     - "Continue anyway" (description: "Proceed to implementation; you may need to handle conflicts at merge time") — when there is a check failure, use instead (description: "Proceed to implementation without a drift verdict for <the branch(es) whose check failed>")
     - "Abort task" (description: "Discard the task and revert status")

5. **Branches:**

   - **"Stop and re-verify plan":** Execute the **Approved-Plan Stop Sequence** (see `plan-approved-stop.md`) with `task_id`, `task_num`, `plan_file`, `stop_reason`, `revert_commit_message` and `closing_message` chosen by case:
     - **proven drift only** → `stop_reason=drift`, `revert_commit_message="ait: Revert t<task_num> to Ready (remote drift)"`, `closing_message="Plan saved. Task t<task_id> reverted to Ready due to remote drift on <the branch(es) that drifted — name each one>. Pull them, then re-pick with /aitask-pick <task_id> in a fresh context."`
     - **check failure only** → `stop_reason=drift_check_failed`, `revert_commit_message="ait: Revert t<task_num> to Ready (remote drift check failed)"`, `closing_message="Plan saved. Task t<task_id> reverted to Ready — the remote drift check could not run for <each branch, with EXTRACT_FAILED or its exit status>. Repair it (\`ait setup\` for a broken install; make the plan file readable), then re-pick with /aitask-pick <task_id> in a fresh context."`
     - **both** → `stop_reason=drift` (drift was proven), the drift `revert_commit_message`, and a `closing_message` that names **separately** the drifted branch(es) to pull and the failed check to repair, before the re-pick command.

     If the output pass reported `LOCAL_BRANCH_MISSING`, the `closing_message`'s part about the output branch says that it must be created or fetched before the task can be merged, rather than pulled. That replaces only the output branch's wording: keep any failed-check repair guidance from the other pass, and the re-pick command — fixing the branch alone would otherwise send the user back into the same failed check.

     Reaching this branch means the user chose to **start implementation** — the plan *was* approved — so the shared sequence records `plan_approved` before releasing anything. That recording is why this is a reference and not a copy of the "Approve and stop here" steps: the earlier inline copy reproduced only that branch's numbered steps and silently dropped the unnumbered gate recording above them (t1380 Defect 1).

     The shared sequence ends the workflow. Do NOT proceed to Step 7.

   - **"Continue anyway":** Return so the caller can proceed to Step 7.

   - **"Abort task":** Execute the **Task Abort Procedure** (`task-abort.md`).

## Notes

- Always best-effort about the **network**. Network failures (`FETCH_FAILED`), missing remotes, and legacy-mode setups all return silently without prompting. The exceptions are local certainties, so they are surfaced rather than swallowed: `LOCAL_BRANCH_MISSING` on the **output** pass (a certain Step 9 failure, established without touching the network), and on either pass `EXTRACT_FAILED` or an incomplete run — the check did not produce a verdict, and staying silent would read as an all-clear.
- Idempotent: safe to call multiple times if the workflow re-enters the checkpoint via "Revise plan".
- Worktree mode: the helper runs from the repo root (the working directory at workflow entry). No worktree exists yet on this path — the fork is deferred to `SKILL.md` Step 7, which runs **after** this check returns "Continue anyway" — and it would be irrelevant anyway, because the helper compares `<branch>..origin/<branch>`, never the task's `aitask/<task_name>` branch. That ordering is the point: the branch is cut from the base as it stands after any pull this check prompted, so a "Stop and re-verify plan" leaves nothing behind to collide with on re-pick.
- For child tasks, `<task_num>` in the "Stop and re-verify" branch refers to the **child** task id (e.g., `16_2`). The parent's status remains `Ready` (it has pending children) — only the active child is reverted.
