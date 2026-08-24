---
name: task-workflow
description: "Shared implementation workflow for task-based skills, with profile-check sites wrapped in Jinja conditionals."
user-invocable: false
---

## Context Requirements

This skill is invoked by other skills (e.g., aitask-pick, aitask-explore, aitask-review) after they have selected a task. The calling skill MUST establish the following context before handing off:

| Variable | Type | Description |
|----------|------|-------------|
| `task_file` | string | Path to selected task file (e.g., `aitasks/t16_implement_auth.md` or `aitasks/t10/t10_2_add_login.md`) |
| `task_id` | string | Task identifier (e.g., `16` or `16_2`) |
| `task_name` | string | Filename stem for branches/worktrees (e.g., `t16_implement_auth` or `t16_2_add_login`) |
| `is_child` | boolean | Whether this is a child task |
| `parent_id` | string/null | Parent task number if child (e.g., `16`), null otherwise |
| `parent_task_file` | string/null | Path to parent task file if child (e.g., `aitasks/t16_implement_auth.md`), null otherwise |
| `active_profile` | object/null | Loaded execution profile from calling skill (or null if no profile) |
| `active_profile_filename` | string/null | Scanner-returned filename for the profile (e.g., `fast.yaml` or `local/fast.yaml`), null if no profile |
| `previous_status` | string | Task status before workflow began (for abort revert, e.g., `Ready`) |
| `folded_tasks` | array/null | List of task IDs folded into this task (e.g., `[106, 129_5]`), or null/empty if none. Set by aitask-explore when existing tasks are folded into a new task. |
| `skill_name` | string | Name of the calling skill for feedback tracking (e.g., `pick`, `explore`, `pr-import`) |
| `feedback_collected` | boolean | Guard flag — initialized to `false`. Set to `true` after the Satisfaction Feedback Procedure runs. Prevents double execution across workflow paths. |
| `usage_collected` | boolean | Guard flag — initialized to `false`. Set to `true` before the unconditional usage bump fires in Satisfaction Feedback Step 0. Set-before-call so a mid-procedure failure does not cause a retry double-bump. |
| `detected_agent_string` | string/null | Agent string (e.g., `claudecode/opus4_6`). Set by either the verify-path append in `planning.md` Step 6.1 or by Agent Attribution in Step 7. Consumed by Agent Attribution (fast-path) and by Satisfaction Feedback in Step 9b to skip re-detection. Initialized to `null`. |

## Workflow

### Step 3: Task Status Checks

After a task is selected and confirmed, perform these checks before proceeding to Step 4.

**Check 1 - Done but unarchived task:**
- Read the task file's frontmatter `status` field
- If status is `Done`:
  - Check if a plan file exists:
    ```bash
    ./.aitask-scripts/aitask_query_files.sh plan-file <taskid>
    ```
    Parse the output: `PLAN_FILE:<path>` means found, `NOT_FOUND` means not found.
  - Use `AskUserQuestion`:
    - Question: "This task has status 'Done' but hasn't been archived yet. Would you like to archive it now?"
    - Header: "Archive"
    - Options:
      - "Yes, archive it" (description: "Proceed to archive the task and plan file if found")
      - "No, skip" (description: "Leave the task as-is and end the workflow")
  - If "Yes, archive it" → skip Steps 4-8, proceed directly to **Step 9** (Post-Implementation) for parent task archival
  - If "No, skip" → end the workflow

**Check 2 - Orphaned parent task (empty children_to_implement):**
- Check if the task file's frontmatter contains `children_to_implement: []` (empty list)
- If empty, check for archived children:
  ```bash
  ./.aitask-scripts/aitask_query_files.sh archived-children <number>
  ```
  Parse the output: `ARCHIVED_CHILD:<path>` lines mean archived children exist, `NO_ARCHIVED_CHILDREN` means none.
- If archived children exist, this is an orphaned parent task:
  - Use `AskUserQuestion`:
    - Question: "This parent task has all children completed and archived, but the parent itself was not archived. Would you like to archive it now?"
    - Header: "Archive"
    - Options:
      - "Yes, archive it" (description: "Proceed to archive the parent task and plan file if found")
      - "No, skip" (description: "Leave the task as-is and end the workflow")
  - If "Yes, archive it" → skip Steps 4-8, proceed directly to **Step 9** (Post-Implementation) for parent task archival
  - If "No, skip" → end the workflow

**Check 3 - Manual-verification task:**
- Read the task file's frontmatter `issue_type` field
- If `issue_type` is `manual_verification`:
  - Execute the **Manual Verification Procedure** (see `manual-verification.md`)
  - Skip Steps 6-8; proceed to Step 9 after the procedure returns
  - Step 4 (ownership) still runs before dispatch — manual verification is work that should be owned and locked. Step 5 also runs, but it only **resolves** the branch context; the fork itself lives at the top of Step 7, which this path skips. So a manual-verification task always runs on the current branch, even under a `create_worktree: true` profile. That is correct, not a gap: the checklist writes no code, and Step 9 has no task branch to merge

**Check 4 - In-flight gated task, all gates now pass:**
- Run `./.aitask-scripts/aitask_gate.sh archive-ready <taskid>` and parse:
  - `NO_GATES` or `BLOCKED:<csv>` → skip this check (fall through to normal selection). This is the common case today — no task declares gates yet.
  - `ALL_PASS` → the task's substantive work landed in an earlier session and every declared gate now passes, but archival was deferred (it was kept active). This is the next-pick backstop for the deferral in Step 9. Use `AskUserQuestion`:
    - Question: "This task has all gates passing and is ready to archive. Would you like to archive it now?"
    - Header: "Archive"
    - Options:
      - "Yes, archive it" (description: "Skip implementation and archive the now-complete task")
      - "No, keep it active" (description: "Leave the task as-is and end the workflow")
  - If "Yes, archive it" → skip Steps 4-8, proceed directly to **Step 9** (Post-Implementation) for archival
  - If "No, keep it active" → end the workflow

**Check 5 - In-flight task, resume from first unmet checkpoint:**

This makes task-workflow re-entrant: a task left `Implementing` (crash, session loss, multi-day work) resumes from the first unmet recorded checkpoint instead of restarting at planning.

- Read the task file's frontmatter `status`. If it is **not** `Implementing`, skip this check (a fresh task plans from scratch).
- Run `./.aitask-scripts/aitask_gate.sh resume-point <taskid>` and parse the single-word result:
  - `PLAN` → skip this check. Nothing durable was recorded (empty/early ledger), so the normal flow runs: Step 4 reclaims the lock and planning re-runs as today. This is the common case for profiles that do not record gates (the ledger stays empty → always `PLAN`), so they are behaviorally unchanged.
  - `IMPLEMENT` or `POSTIMPL` → the task has recorded checkpoints and is being re-entered. Set the context variable `resume_point` to that value. Show the recorded state and the resume target, e.g.:
    ```bash
    ./.aitask-scripts/aitask_gate.sh status <taskid>
    ```
    Display a banner: "Re-entering in-flight task t\<id\> — \<recorded checkpoints\> → will resume at \<implementation (Step 7) | post-implementation (Step 9)\> after the lock is reclaimed." Then **proceed to Step 4 normally** — ownership MUST be (re)claimed before any work resumes. The actual step-skipping happens after Step 4 (see **Re-entry Routing**).

**Note:** Check 1, Check 2, and Check 4 should NOT set the task status to "Implementing" — the task is already done (or its work is complete and gated). Skip Step 4 (Assign Task) entirely when archiving via Check 1, Check 2, or Check 4. Check 3 does run Step 4 as normal. **Check 5 also runs Step 4** (the in-flight lock must be reclaimed) — it does **not** skip it; step-skipping happens post-reclaim via **Re-entry Routing**.

If none of the checks trigger, proceed to Step 4 as normal.

### Step 4: Assign Task to User

- **Email resolution (priority order):**

  1. **Check task metadata:** Read the `assigned_to` field from the task file's frontmatter.
  2. **Check userconfig:** Read `aitasks/metadata/userconfig.yaml` and extract the `email:` field (if file exists).
  3. **Mismatch check:** If both `assigned_to` and userconfig email are non-empty and DIFFERENT, use `AskUserQuestion`:
     - Question: "Task is assigned to \<assigned_to\> but your userconfig email is \<userconfig_email\>. Which email to use?"
     - Header: "Email"
     - Options:
       - "Keep \<assigned_to\>" (description: "Continue with the existing assignment")
       - "Use \<userconfig_email\>" (description: "Override with your local email")
     - Use the selected email and proceed to the **Claim task ownership** step below.
  4. **If `assigned_to` is non-empty** (and matches userconfig, or userconfig is empty): use `assigned_to`. Display: "Using email from task metadata: \<email\>". Skip to **Claim task ownership**.
{# ---------- default_email ---------- #}{% if profile.default_email is defined %}
  5. **Profile-driven email resolution** (profile '{{ profile.name }}', `default_email: {{ profile.default_email }}`):
{# ---------- default_email value ---------- #}{% if profile.default_email == "userconfig" %}
     - Use the userconfig email (from step 2). If userconfig is empty/missing, fall back to reading `aitasks/metadata/emails.txt` (first email). Display: "Profile '{{ profile.name }}': using email \<email\> (from userconfig)". If both are empty, prompt the user via `AskUserQuestion` as described in step 6 below.
{% elif profile.default_email == "first" %}{# default_email: literal "first" #}
     - Read `aitasks/metadata/emails.txt` and use the first email address. Display: "Profile '{{ profile.name }}': using email \<email\>". If emails.txt is empty or missing, prompt the user via `AskUserQuestion` as described in step 6 below.
{% else %}{# default_email: literal email address #}
     - Use `{{ profile.default_email }}` directly. Display: "Profile '{{ profile.name }}': using email {{ profile.default_email }}".
{% endif %}{# ---------- end default_email value ---------- #}
     - Then skip step 6 and proceed to the **Userconfig sync check** below.
{% else %}{# default_email: key absent from profile #}
  5. **Profile check:** If the active profile has `default_email` set:
     - If value is `"userconfig"`: Use the userconfig email (from step 2). If userconfig is empty/missing, fall back to reading `aitasks/metadata/emails.txt` (first email). Display: "Profile '\<name\>': using email \<email\> (from userconfig)". If both are empty, fall through to the AskUserQuestion below.
     - If value is `"first"`: Read `aitasks/metadata/emails.txt` and use the first email address. Display: "Profile '\<name\>': using email \<email\>". If emails.txt is empty or missing, fall through to the AskUserQuestion below.
     - If value is a literal email address: Use that email directly. Display: "Profile '\<name\>': using email \<email\>"
     - Skip the AskUserQuestion below
{% endif %}{# ---------- end default_email ---------- #}

  6. **Otherwise, ask for email using `AskUserQuestion`:**
     - Read stored emails: `cat aitasks/metadata/emails.txt 2>/dev/null | sort -u`
     - Question: "Enter your email to track who is working on this task (optional):"
     - Header: "Email"
     - Options:
       - List each stored email from emails.txt (if any exist)
       - "Enter new email" (description: "Add a new email address")
       - "Skip" (description: "Don't assign this task to anyone")

  - **If "Enter new email" selected:**
    - Ask user to type their email via `AskUserQuestion` with free text (use the "Other" option)

- **Userconfig sync check:** After email is resolved, if the final email differs from the userconfig email (or userconfig doesn't exist):
  - Use `AskUserQuestion`:
    - Question: "The selected email (\<email\>) differs from your userconfig (\<userconfig_email\>). Update userconfig.yaml?"
    - Header: "Userconfig"
    - Options:
      - "Yes, update userconfig" (description: "Save this email to userconfig.yaml for future use")
      - "No, keep current userconfig" (description: "Use this email for now but don't change userconfig")
  - If "Yes": Write `email: <email>` to `aitasks/metadata/userconfig.yaml` (create file if needed with comment header `# Local user configuration (gitignored, not shared)`)
  - If "No": Proceed without updating
  - **Skip this check** if: the final email matches userconfig, or email was resolved from userconfig itself, or no email was selected ("Skip")

- **Claim task ownership (lock, update status, commit, push):**

  If email was provided (new or selected):
  ```bash
  ./.aitask-scripts/aitask_pick_own.sh <task_num> --email "<email>"
  ```
  If no email (user selected "Skip"):
  ```bash
  ./.aitask-scripts/aitask_pick_own.sh <task_num>
  ```

  **Parse the script output:**
  - `OWNED:<task_id>` — Success. Proceed to Step 5.
  - `FORCE_UNLOCKED:<previous_owner>` + `OWNED:<task_id>` — Force-unlock succeeded. Inform user: "Force-unlocked stale lock held by \<previous_owner\>." Proceed to Step 5.
  - One of `LOCK_RECLAIM:`, `RECLAIM_CRASH:`, or `RECLAIM_STATUS:` (in addition to `OWNED:`) — task was already in `Implementing` and re-locked. When multiple are present, prefer `LOCK_RECLAIM` > `RECLAIM_CRASH` > `RECLAIM_STATUS`. Parse the signal-specific fields and execute the **Crash Recovery Procedure** (see `crash-recovery.md`) with `signal_type` and the parsed fields.

    Signal field formats:
    - `LOCK_RECLAIM:<prev_hostname>|<prev_locked_at>|<current_hostname>` — multi-PC reclaim (cross-host).
    - `RECLAIM_CRASH:<prev_locked_at>|<prev_hostname>|<prev_pid>` — same-host crash (PID anchor is dead). Common case after a tmux/host-shell crash.
    - `RECLAIM_STATUS:<prev_status>|<prev_assigned_to>` — anomaly fallback: the lock is missing, is a pre-PID-anchor lock, recorded no session process, or is this session's own. A lock whose holder is a *different* live or unverifiable session on this host never reaches here — it is refused at acquire time (below).

    When the procedure returns:
    - `reclaim` → ownership is held here (`OWNED:` confirms). Continue to the **Re-entry Routing** gate at the end of Step 4 (it checks `resume_point`); if no resume applies, proceed to Step 5 normally.
    - `decline` → return to the calling skill's task selection. Do NOT proceed. (The procedure has already released the lock and reverted the task to `Ready`.)
  - `LOCK_FAILED:<owner>|<locked_at>|<hostname>` — Task is locked by another user/PC. Parse the `|`-separated fields for lock details. Use `AskUserQuestion`:
    - Question: "Task t\<N\> is locked by \<owner\> (since \<locked_at\>, hostname: \<hostname\>). Force unlock?"
    - Header: "Lock"
    - Options:
      - "Force unlock and claim" (description: "Override the stale lock and claim this task")
      - "Pick a different task" (description: "Leave the lock intact and select another task")
    - If "Force unlock and claim": Re-run ownership with `--force`:
      ```bash
      ./.aitask-scripts/aitask_pick_own.sh <task_num> --force --email "<email>"
      ```
      Parse the output again. If `FORCE_UNLOCKED` + `OWNED`: proceed. Otherwise: abort.
    - If "Pick a different task": Return to the calling skill's task selection. Do NOT proceed.
  - `LOCK_LIVE_HOLDER:<owner>|<locked_at>|<hostname>|<pid>` — **another session of yours on this machine is holding this task and is still running.** Nothing was claimed: the refusal happens before the lock, the status write and the commit, so the task is untouched and there is nothing to undo. This is not a crash — do **not** describe it as one, and do not run the Crash Recovery Procedure. Parse the `|`-separated fields and use `AskUserQuestion`:
    - Question: "Task t\<N\> is already held by another session of yours on this machine (pid \<pid\>, since \<locked_at\>), and that session is still running. Nothing has been claimed."
    - Header: "Live holder"
    - Options — **list them in this order**; the safe option must come first, because taking the lock here means two agents working the same task:
      - "Pick a different task" (description: "Leave the other session alone and select another task")
      - "Force-claim anyway" (description: "Take the lock while the other session keeps running — both agents will work this task and duplicate each other")
    - If "Pick a different task": return to the calling skill's task selection. Do NOT proceed.
    - If "Force-claim anyway": re-run with `--force`:
      ```bash
      ./.aitask-scripts/aitask_pick_own.sh <task_num> --force --email "<email>"
      ```
      Parse the output again. If `FORCE_UNLOCKED` + `OWNED`: proceed to Step 5. Otherwise: abort.
  - `LOCK_UNVERIFIABLE_HOLDER:<owner>|<locked_at>|<hostname>|<pid>` — a session of yours on this machine holds the task and **its liveness could not be established** — it is neither provably running nor provably gone (an uninspectable process, or an identity token too coarse to rule out a recycled PID). As above, nothing was claimed and this is not a crash. Same prompt shape, same option order:
    - Question: "Task t\<N\> is held by a session on this machine (pid \<pid\>, since \<locked_at\>) that could not be verified as either running or gone. Nothing has been claimed."
    - Header: "Unverified"
    - Options:
      - "Pick a different task" (description: "Leave the lock intact and select another task")
      - "Reclaim anyway" (description: "Take the lock — do this only if you know that session is gone")
    - Handle both branches exactly as for `LOCK_LIVE_HOLDER:` above.
  - `LOCK_ERROR:<message>` — Lock system error (fetch failure, race exhaustion, etc.). Display the error and suggest running `./.aitask-scripts/aitask_lock_diag.sh` for troubleshooting. Use `AskUserQuestion`:
    - Question: "Lock system error: \<message\>. How to proceed?"
    - Header: "Lock error"
    - Options:
      - "Retry" (description: "Try acquiring the lock again")
      - "Continue without lock" (description: "Proceed without locking (risky if multiple users)")
      - "Abort" (description: "Stop the workflow")
    - If "Retry": Re-run `aitask_pick_own.sh` (same command). Parse output again.
    - If "Continue without lock": Skip lock acquisition, proceed to Step 5 (task status will be updated but no lock held).
    - If "Abort": End the workflow.
  - `LOCK_INFRA_MISSING` — Lock infrastructure not initialized. Inform user to run `ait setup` and abort.

  **Note:** The script handles email storage, lock acquisition, task metadata update (`status` → Implementing, `assigned_to`), and git add/commit/push internally. If the script fails entirely (non-zero exit without structured output), display the error and abort.

- **Materialize the active-gates tuple (ALWAYS runs — never profile-omitted):** With ownership held, derive and persist the task's enforced gate set under the current profile. If `active_profile_filename` is set, run:

  ```bash
  ./.aitask-scripts/aitask_gate.sh materialize-active <task_num> --profile aitasks/metadata/profiles/<active_profile_filename>
  ```

  Parse the single stdout line:
  - `MATERIALIZED:<csv>` — active set persisted and committed. `MATERIALIZED:(empty)` means a fully profile-filtered (or ungated) task — that persisted empty set is exactly what makes a declared-but-unrendered gate invisible to every enforcer. Continue.
  - `MATERIALIZED_UNCOMMITTED:<csv>` — the tuple was written and is enforced locally, but the path-scoped git commit failed (e.g. an index lock). Warn: "active-gates tuple written but not committed — other checkouts won't see it until the task data is committed." and continue; a later `./ait git` commit of `aitasks/` picks it up.
  - `NOOP:unchanged` — re-pick under the same profile with unchanged inputs; nothing rewritten (any previously pending commit of the task file was verified/repaired). Continue.
  - `NOOP_UNCOMMITTED:pending-persist` — the tuple is unchanged and enforced locally, but the task file still carries changes git refused to commit. Warn as for `MATERIALIZED_UNCOMMITTED` and continue.
  - Nonzero exit — the re-derivation failed (unreadable/invalid profile, compute backend unavailable). The helper clears any previously persisted tuple (its stderr says whether the clear succeeded), but the raw-`gates:` fallback is only the task's declared intent — it does NOT include this profile's `default_gates`, so continuing could silently under-enforce the current profile. **ABORT the pick**: display "active-gates materialization failed (\<output\>) — fix the profile / compute backend and re-pick t\<task_num\>.", then execute the **Task Abort Procedure** (see `task-abort.md`). Do NOT proceed to Step 5.
  - **Also on stderr (advisory — not part of the stdout status line):** a `Warning: materialize-active: active gate '<gate>' has no verifier configured in <registry> — it will block archival.` line — or its `… has no registry entry in <registry> …` variant — means an **enforced** gate can never be satisfied, so the Step-9 archival guard will hold the task in-flight indefinitely. The exit status is still 0 and stdout still reports `MATERIALIZED:` / `NOOP:`, so **continue** — but **surface the warning to the user** and suggest `ait gates sync-registry` to reconcile the registry. Same warn-and-continue shape as `MATERIALIZED_UNCOMMITTED` / `NOOP_UNCOMMITTED` above; the exit-code contract is unchanged (a nonzero exit still aborts).

  If `active_profile_filename` is NOT set (a manual/resume invocation without a profile), skip the call. This is the claim-time-snapshot governance model: with no profile in scope there is nothing to re-derive against, so the previously persisted tuple (when present and intact) remains the enforced snapshot, and a task never materialized follows its raw `gates:` field. (`./.aitask-scripts/aitask_gate.sh active-gates-status <task_num> --profile <file>` shows the stored tuple + freshness when a profile is in scope.)

  This claim-time materialization replaces the former Step-7 `gates:` backfill: raw `gates:` stays the task's declared intent, and the persisted `active_gates` tuple is the enforced set that planning, the Step-9 orchestrator, and the archival guard all read. Re-running on every (re-)pick re-derives the set under the CURRENT profile, so a profile switch can never leave stale enforcement. (Gate CLI verb shapes — decision vs action vs introspection — are documented once in `gate-cli.md`.)

- **Store previous status for potential abort** (remember the `previous_status` from context)

- **Re-entry Routing gate:** After ownership is held (via **any** success path above — `OWNED`, `FORCE_UNLOCKED` + `OWNED`, or crash-recovery → `reclaim`), check the `resume_point` context variable set by Step 3 Check 5. If it is `IMPLEMENT` or `POSTIMPL`, follow the **Re-entry Routing** procedure below **instead of** proceeding to Step 5 → Step 6. Otherwise (unset, or `PLAN`), proceed to Step 5 normally. (The routing is gated on `resume_point`, not on which ownership path was taken — a force-unlock takeover of an in-flight task returns plain `OWNED` with no reclaim signal, and its resume must not be lost.)

### Re-entry Routing

Runs only when `resume_point` (from Step 3 Check 5) is `IMPLEMENT` or `POSTIMPL` and Step 4 left ownership held. It resumes the in-flight task from the first unmet checkpoint instead of restarting at planning. Profile-invariant.

- **Plan-existence guard:** Run `./.aitask-scripts/aitask_query_files.sh plan-file <taskid>`. If `NOT_FOUND` (a checkpoint was recorded but no plan was externalized — e.g. a failed externalization), discard the resume: clear `resume_point` and fall back to the normal flow (Step 5 → Step 6, re-plan). If `PLAN_FILE:<path>`, read the plan and continue below.

- **Resolve the plan's branches:** A resumed session carries none of the Step 5 branch variables, and its profile may differ from the original's. Resolve both branches **from the plan header only** — never from `profile.base_branch` / `profile.output_branch` (the same rule Step 9 states, for exactly this reason). Bind to variables; do not substitute the literals into any command:

  ```bash
  base_branch=$(sed -n 's/^Base branch: //p' "<plan_file>" | head -n1)
  provenance_base="plan header"
  [ -n "$base_branch" ] || { base_branch=main; provenance_base="legacy plan, no Base branch field"; }
  output_branch=$(sed -n 's/^Output branch: //p' "<plan_file>" | head -n1)
  provenance_output="plan header"
  [ -n "$output_branch" ] || { output_branch=main; provenance_output="legacy plan, no Output branch field"; }
  for b in "$base_branch" "$output_branch"; do
    printf '%s' "$b" | grep -qE '^[A-Za-z0-9._/-]+$' &&
      git check-ref-format --branch "$b" >/dev/null 2>&1 ||
      echo "UNSAFE_BRANCH:$b"
  done
  ```

  `UNSAFE_BRANCH:<b>` → **stop**: report the offending value and resume nothing (fail closed). Do **not** fall back to a default — an unsafe header value means the plan is untrustworthy about where work lands.

  Never fall back to `Base branch:` for the output branch: a plan written before that field existed merged to `main`, and reading its base would retroactively change where in-flight work lands. Carry both provenance strings and name them in any prompt, exactly as Step 9 does.

- **Resolve the worktree intent — from the plan header, exactly like the branches.** A resumed session may run under a **different profile** than the one that planned the task, so `profile.create_worktree` must not decide this: under `fast` a task planned with `create_worktree: true` would skip its fork entirely, and under a worktree profile a current-branch task would suddenly get one. The durable record is the header's `Worktree:` field, written from Step 5's intent at externalization time:

  A plan file is editable text, so the **read** side must re-apply every check the **write** side applied — the charset alone is not enough: `../../outside` and `aiwork/../../outside` both satisfy it, and the value is about to reach `mkdir -p` and `git worktree add`. These are the same three checks `validate_worktree_path()` in `aitask_plan_externalize.sh` runs when the field is written:

  ```bash
  worktree_path=$(sed -n 's/^Worktree: //p' "<plan_file>" | head -n1)
  if [ -n "$worktree_path" ]; then
    wt_ok=1
    printf '%s' "$worktree_path" | grep -qE '^[A-Za-z0-9._/-]+$' || wt_ok=0  # charset
    case "$worktree_path"   in /*)      wt_ok=0 ;; esac                      # absolute
    case "/$worktree_path/" in */../*)  wt_ok=0 ;; esac                      # .. segment
    [ "$wt_ok" = 1 ] || echo "UNSAFE_WORKTREE:$worktree_path"
  fi
  ```

  `UNSAFE_WORKTREE:<p>` → **stop**, exactly as for `UNSAFE_BRANCH` — a header value that is not repo-relative and shell-safe means the plan is untrustworthy about where the work lives, and treating it as usable would place a worktree outside the repository.

  Then bind the mode and the path together — every branch below sets **both**, because Step 7's fork block reads `worktree_path` and cannot run without it:

  - **Non-empty and safe** → worktree mode; `worktree_path` is the header's value.
  - **Empty** → the header makes no claim: either the task is current-branch, or it predates this field. Resolve it **without guessing**, in this order:
    1. Ask the canonical classifier — `./.aitask-scripts/aitask_task_worktree.sh resolve <task_name>`, keeping its exit status as Step 7 does. A `USABLE <path>` answer is evidence, not inference → worktree mode, and `worktree_path` is **that path** (the helper reads the record's own `worktree <path>`, so a moved worktree resolves correctly). `NONE` → fall through to the question below. Any other state (`STALE` / `LOCKED` / `MAIN` / `UNSAFE`), a non-zero exit, or empty output → **stop and ask the user**, naming the state or exit status: a dead, locked, root-held or control-character path means someone moved or pinned this worktree by hand and their work may be in it, and a silent empty answer means the classifier never ran.
    2. Otherwise **ask the user** (`AskUserQuestion`) whether this task should get its own worktree, saying that the plan header records none and that the current profile is not authoritative for a resumed task. Do **not** read `profile.create_worktree` to answer it for them. Both answers have a defined handoff:
       - **"Create the worktree now"** → worktree mode, and `worktree_path=aiwork/<task_name>` — the conventional location, which is the only defensible value when the header names none.
       - **"Work on the current branch"** → current-branch mode: leave `worktree_path` unset and treat Step 7's fork block as a no-op. Do not carry a path forward from any earlier context.

- **Environment setup — resolve here, fork later.** This step is **read-only**; do not run Step 7's fork block from it. The same split the whole task is about applies to the resume path: the drift check for this route runs *below*, so cutting here would pin the fork to the pre-drift HEAD and re-create exactly the stale-worktree timing the deferral removes. Do **not** send this to Step 5 either — Step 5 creates nothing any more.
  - If the reuse extraction already found a worktree record, you are working in that directory from now on; nothing needs to be created and there is no ordering question.
  - Otherwise, in worktree mode, the fork is **owed but not yet performed**. Where it happens depends on the route below:
    - **`IMPLEMENT`** → Step 7's **"Deferred worktree fork"** block runs **only after** the Remote Drift Check has returned "Continue anyway", immediately before implementation — see the route text.
    - **`POSTIMPL`** → the fork block does **not** run at all. The code is already committed and `review_approved` recorded, so there is nothing left to implement in a worktree; cutting a fresh branch from the base at this point would either fail outright (`aitask/<task_name>` already exists) or produce an empty worktree that Step 9 would then merge. Proceed to Step 9 from the repo root.
  - In current-branch mode every path here is a no-op and you work on the current branch.

- **Route by `resume_point`:**
  - **`IMPLEMENT`** → **first run the remote drift check, then** resume at Step 7's **"Follow the approved plan"** implementation body.

    **Remote drift check (re-entry).** Execute the **Remote Drift Check Procedure** (see `remote-drift-check.md`) with `base_branch` (from the branch-resolution step above), `plan_file`, `task_id`, `task_num` and `active_profile`. Pass **no** `output_branch` value of your own — the procedure re-derives it from the same plan header, which is what keeps the base and output passes on one rule. A resumed task's plan is by construction the *oldest* relative to `origin/<base>` and `origin/<output>`, so this is the path that most needs the check, and it was previously the only path that never got it (t1380 Defect 2). If the procedure ends the workflow ("Stop and re-verify plan" or "Abort task"), **stop** — do not resume implementation.

    **The loop terminates.** "Stop and re-verify plan" reverts the task to `Ready`; the re-pick therefore fails Step 3 Check 5's `Implementing` status gate, never reaches Re-entry Routing, and runs the normal planning path — whose Checkpoint runs the check once more, now against the pulled branches. The check that sent the user away is not the one they land back on.

    Then re-run **only** the **Pre-implementation ownership guard**, the **Deferred worktree fork** block, and the **Agent Attribution Procedure** (all idempotent — the fork block's reuse check short-circuits when a worktree already exists, and attribution re-records the *resuming* agent), in that order, and go straight to implementation.

    **The fork belongs here, not in the environment-setup step above** — after "Continue anyway", so the branch is cut from the base as it stands post-pull. Pass it the `worktree_path` and `base_branch` resolved above; on this route `base_branch` came from the plan header, so the block's agreement check is trivially satisfied and its legacy-fallback confirmation is the one that can fire. **Skip** Step 7's post-approval one-time gates:
    - Cross-Repo Child Assignment and the risk-mitigation pre-task creation (the post-approval "before" follow-ups) — these are **non-idempotent task creators** that *end the workflow* when they fire, so a task that is still a normal `Implementing` single task is necessarily past them; re-running would double-create.
    - The `plan_approved` / `risk_evaluated` gate re-recordings and the risk-level field write — already done in the original session; re-running only adds redundant commits.
  - **`POSTIMPL`** → **first run the merge-target sync pre-flight, then** resume at **Step 9** (Post-Implementation), skipping Steps 6–8 (the code is already committed and `review_approved` was recorded after the Step 8 commit). Step 9 is safe to re-enter: its merge approval is NON-SKIPPABLE (re-asked), a re-merge of an already-merged branch is a git no-op, and archival just moves and commits the task file. For child tasks, the "verify plan completeness before archival" sub-step backstops the Final Implementation Notes.

    **Merge-target sync pre-flight.** Step 9 **never fetches** — its pre-flight only checks local ref existence and foreign-worktree conflicts, and `git merge` is purely local. So a stale local output branch merges *cleanly* and the divergence surfaces only when the user later pushes and git rejects it as non-fast-forward. Execute the **Merge-Target Sync Pre-flight Procedure** (see `merge-target-sync.md`) with `output_branch` (from the branch-resolution step above), `plan_file` and `task_id`. If it ends the session ("Stop here"), do **not** proceed to Step 9.

    The full pre-implementation Remote Drift Check is deliberately **not** run on this route: at `POSTIMPL` the base branch is irrelevant (the plan is no longer being followed), and that procedure's only actionable branch reverts the task to `Ready` — the wrong move for work that is already reviewed and committed. `merge-target-sync.md` documents the split.

### Step 5: Environment and Branch Setup

> **Note:** For fully autonomous remote workflows (Claude Code Web), use the `aitask-pickrem` skill instead — it skips all environment setup and always works on the current branch.

{# ---------- create_worktree ---------- #}{% if profile.create_worktree is defined %}
{# ---------- create_worktree value ---------- #}{% if profile.create_worktree %}- Use a separate branch and worktree for this task. Display: "Profile '{{ profile.name }}': worktree mode — the branch and worktree are created after plan approval and the remote drift check, not now." Continue with the **If Yes** branch below.
{% else %}{# create_worktree: value is false / falsy #}- Work on the current branch in the current directory. Display: "Profile '{{ profile.name }}': working on current branch". Continue with the **If No** branch below.
{% endif %}{# ---------- end create_worktree value ---------- #}
{% else %}{# create_worktree: key absent from profile #}
- **Profile check:** If the active profile has `create_worktree` set:
  - If `true`: Use a separate branch and worktree. Display: "Profile '\<name\>': worktree mode — the branch and worktree are created after plan approval and the remote drift check, not now."
  - If `false`: Work on current branch. Display: "Profile '\<name\>': working on current branch"
  - Skip the AskUserQuestion below

  Otherwise, use `AskUserQuestion` to ask:
  - "Do you want to create a separate branch and worktree for this task? Nothing is created now — the branch and worktree are cut at the start of implementation, after you approve the plan and the remote drift check passes."
  - Options: "No, work on current branch" (default, first option) / "Yes, use a separate worktree (recommended for complex features or when working in parallel on multiple features)"
{% endif %}{# ---------- end create_worktree ---------- #}

**If Yes:**

- Extract `<task_name>` from the filename
  - For parent: `t16_implement_channel_settings` from `t16_implement_channel_settings.md`
  - For child: `t16_2_add_login` from `t16_2_add_login.md`

{# ---------- base_branch ---------- #}{% if profile.base_branch is defined %}
- Use base branch `{{ profile.base_branch }}` for this task. Display: "Profile '{{ profile.name }}': using base branch {{ profile.base_branch }} — the branch and worktree are created after plan approval and the remote drift check, not now."
{% else %}{# base_branch: key absent from profile #}
- **Profile check:** If the active profile has `base_branch` set:
  - Use the specified branch name. Display: "Profile '\<name\>': using base branch \<branch\> — the branch and worktree are created after plan approval and the remote drift check, not now."
  - Skip the AskUserQuestion below

  Otherwise, ask which branch to base the new branch on using `AskUserQuestion`:
  - "Which branch should the new task branch be based on? The branch and worktree are not created now — they are cut at the start of implementation, after you approve the plan and the remote drift check passes."
  - Options: "main (Recommended)" / "Other branch"
  - If "Other branch", ask user to specify the branch name

  The deferral belongs **inside the question text**, not in same-turn prose around it: the widget is the only surface the user is guaranteed to read when answering, and a user who believes the fork already happened will misjudge every later stop path.
{% endif %}{# ---------- end base_branch ---------- #}

{# ---------- output_branch ---------- #}{% if profile.output_branch is defined %}
- Use output branch `{{ profile.output_branch }}` as the merge target for this task. Display: "Profile '{{ profile.name }}': using output branch {{ profile.output_branch }}".
{% else %}{# output_branch: key absent from profile #}
- **Profile check:** If the active profile has `output_branch` set, use it as the merge target and display: "Profile '\<name\>': using output branch \<branch\>". Otherwise the merge target is the base branch resolved above — **do not ask**; there is no separate question for the merge target.
{% endif %}{# ---------- end output_branch ---------- #}

- **Never handle the branch name yourself.** It is user-authored config, and git accepts refs containing shell metacharacters (`dev$(id)`, ``dev`id` ``, `dev'x` are all valid refs). Quoting does not help — `"dev$(id)"` still executes inside double quotes — and re-reading the YAML with `sed` would mis-parse the equally valid `output_branch: "dev"` / `'dev'` / `dev # comment` forms. So the value is **displayed only**. Step 6 passes the profile *path* to the externalize helper, which resolves `output_branch` with a real YAML parser, validates it against a shell-safe subset, and fails closed. If it reports an unsafe branch name, stop and tell the user; do not continue to Step 9.

- **Nothing is created here — this step resolves, it does not fork.** Record `<task_name>`, the resolved `<base_branch>` and `<output_branch>` as workflow context. The branch and worktree are cut at the top of **Step 7**, after `planning.md`'s Checkpoint approved the plan and the **Remote Drift Check Procedure** returned "Continue anyway".

  Deferring the fork is what makes the fork point reflect the base *after* any pull the drift check prompted, and what stops every "stop, don't abort" exit (approve-and-stop, drift stop, a parent that decomposes into children) from stranding a worktree for work that never started.

- Two consequences worth stating here, because they are easy to get wrong later:
  - Step 6 externalizes the plan **before** the worktree exists. The plan header's `Worktree:` field therefore records the intent resolved above — pass `--worktree aiwork/<task_name>` in `<branch-flags>` (see `plan-externalization.md`). The helper does **not** probe the filesystem for it, so omitting the flag drops the field.
  - You are still in the repo root for Steps 6 and 7's pre-fork work. `aiwork/<task_name>/` becomes the working directory only from the Step 7 fork onward.

**If No:**
- Work directly on the current branch in the current directory

### Step 6: Create Implementation Plan

> **Full planning workflow:** Read `planning.md` for the complete Step 6 procedure including:
> - 6.0: Check for Existing Plan (profile-aware)
> - 6.1: Planning (EnterPlanMode, child tasks, complexity assessment)
> - Child Task Documentation Requirements
> - Save Plan to External File (naming conventions, metadata headers)
> - Checkpoint (post-plan action)
>
> After the checkpoint in `planning.md`:
> - If child tasks were created and the child checkpoint returned "Stop here" → collect **Satisfaction Feedback Procedure** (see `satisfaction-feedback.md`) with `skill_name` from context variables, then **END the workflow** (do NOT proceed to Step 7/8/9)
> - If child tasks were created and the child checkpoint returned "Start first child" → restart with `/aitask-pick <parent>_1` (do NOT proceed to Step 7)
> - Otherwise (normal single-task plan) → proceed to Step 7

### Step 7: Implement

**Pre-implementation ownership guard:**

Before starting implementation, verify that ownership/lock was acquired (Step 4 should have done this, but this guard catches edge cases like plan mode deferral):

- Read the task file's frontmatter `status` and `assigned_to` fields
- Resolve the current user's email: use the email from Step 4 if available, otherwise read from `aitasks/metadata/userconfig.yaml`
- **If status is `Implementing` AND `assigned_to` matches the current user's email:** Ownership *appears* to have been acquired in Step 4 — but verify the lock is held on *this* host before assuming so. Run `./.aitask-scripts/aitask_lock.sh --check <task_id>` and parse the `hostname:` line from the output. Compare against `hostname` (the running shell's hostname).
  - If the hostname matches **or** `--check` shows no lock at all (single-user / no-remote mode): ownership is confirmed for this host. Proceed normally.
  - If the hostname differs (a different machine holds the lock under your email): a multi-PC reclaim has been detected by the guard. Execute the **Crash Recovery Procedure** (see `crash-recovery.md`) with `signal_type=LOCK_RECLAIM`, parsing `prev_hostname` from `--check` output and using the current `hostname` as `current_hostname`. If the procedure returns `reclaim`, run `./.aitask-scripts/aitask_pick_own.sh <task_num> --email "<email>"` to refresh the lock to this host before proceeding. If `decline`, return to the calling skill's task selection. (Same-host crash recovery is moot here: by the time Step 7 fires, Step 4's `aitask_pick_own.sh` already owned the lock and surfaced any `RECLAIM_CRASH:` signal.)
- **Otherwise** (status is not `Implementing`, or `assigned_to` is empty/missing, or `assigned_to` does not match the current user's email): Ownership was not properly acquired. Display: "Guard: task ownership not confirmed — acquiring ownership now."
  - Run the ownership claim:
    ```bash
    ./.aitask-scripts/aitask_pick_own.sh <task_num> --email "<email>"
    ```
  - Parse output as in Step 4:
    - `OWNED:<task_id>` — Success. Proceed.
    - `LOCK_FAILED:<owner>|<locked_at>|<hostname>` — Parse the `|`-separated fields. Use `AskUserQuestion` with options: "Force unlock and claim" / "Abort task". If force unlock, re-run with `--force`. If abort, execute the **Task Abort Procedure** (see `task-abort.md`).
    - `LOCK_LIVE_HOLDER:` / `LOCK_UNVERIFIABLE_HOLDER:` — another session of yours on this machine holds the task and is running (or could not be verified as gone). Handle exactly as in Step 4, including the option order (safe option first). Reaching this from *this* guard is unusual — it means ownership was lost between Step 4 and here — so state that in the display before prompting.
    - `LOCK_ERROR:<message>` — Display error. Use `AskUserQuestion`: "Retry" / "Continue without lock" / "Abort". Handle as in Step 4.
    - `LOCK_INFRA_MISSING` — Inform user to run `ait setup` and abort.
    - Script fails entirely — display error and abort.

**Deferred worktree fork (Step-5 intent, cut now):**

This is the fork **Step 5** resolved but did not perform. Reaching here means the plan was approved *and* the Remote Drift Check returned "Continue anyway", so the fork point is the base branch as it stands after any pull that check prompted. It runs **after** the ownership guard above — ownership must be confirmed before anything is created — and **before** everything below it, so the risk-mitigation "before" stop later in this step still finds a real worktree.

**Which mode applies** depends on how you got here, and in both cases it is a recorded fact rather than a re-read of the current profile:

- **fresh** — the mode Step 5 resolved (its **If Yes** / **If No** branch), with `<worktree_path>` = `aiwork/<task_name>`.
- **re-entry** — the mode **Re-entry Routing** resolved from the plan header's `Worktree:` field, with `<worktree_path>` = that value.

**In current-branch mode** this whole block is a no-op — continue below.

**In worktree mode:**

- **Confirm the fork base before cutting.** `<base_branch>` reaches this block by exactly one of two routes, and **both always bind it**:
  - **fresh** — Step 5 resolved it (profile `base_branch`, else the user's answer). Provenance: `Step 5`.
  - **re-entry** — Step 5 was skipped and **Re-entry Routing** resolved it from the plan header, falling back to `main` with `provenance_base="legacy plan, no Base branch field"` for a plan written before that field existed.

  Three checks, in order. Each fails closed; none guesses:

  1. **Bound.** If `base_branch` is empty, neither route ran — a defect state, not a legacy one. **Stop and ask the user** for the base. Never run `git worktree add` with an empty final argument: git would silently cut from the current HEAD, which is exactly the wrong-base failure the deferral exists to prevent.
  2. **A legacy fallback is confirmed, never assumed.** If the provenance is the `legacy plan, no Base branch field` fallback, the value is a *guess* (`main`) that is about to become a real branch rather than just a comparison. Confirm it with `AskUserQuestion` before cutting — question text naming the plan file, the guessed base, and the reason ("this plan predates the `Base branch:` header, so the base was defaulted") — options "Use `main`" / "Pick a different base branch". This is the same name-the-provenance rule Step 9 and Re-entry Routing state, raised from *display* to *confirm* because this call site writes.

     **Then actually adopt the answer** — a confirmation that does not reach the variable the cut uses is worse than none, because the widget claims one base while `git worktree add` uses another. Whichever option was chosen:

     ```bash
     # Write the confirmed name with the Write tool (NOT a shell echo): a
     # user-supplied ref like `release$(id -u)` would expand before any check.
     confirmed_base=$(head -n1 <scratch-file>)
     printf '%s' "$confirmed_base" | grep -qE '^[A-Za-z0-9._/-]+$' &&
       git check-ref-format --branch "$confirmed_base" >/dev/null 2>&1 &&
       git rev-parse --verify --quiet "refs/heads/$confirmed_base" >/dev/null ||
       echo "UNUSABLE_BASE:$confirmed_base"
     base_branch="$confirmed_base"
     provenance_base="user-confirmed (legacy plan)"
     ```

     `UNUSABLE_BASE` → re-ask; do not cut. Note the third check: the base must exist as a **local branch**, since `git worktree add` would otherwise DWIM or fail mid-command. From here on `"$base_branch"` is the confirmed value, and it is what the cut below uses — verify that with a value **other than** `main`, since a handoff bug is invisible when the answer equals the guess.

     **The confirmation is per-session, and that is deliberate.** Do not expect it to be written back into the plan header: Step 8's externalize fallback is a no-op (`PLAN_EXISTS`) once the plan exists, which it always does by the time you are here, so nothing on the resume path rewrites `Base branch:`. A later resume of the same legacy plan therefore asks again. Re-confirming beats persisting a guess — but do **not** tell the user their answer is being remembered.
  3. **Agreement.** When both a Step-5 value and a non-empty header value exist they must match — the header is what a future resume reads, so a disagreement means the branch is cut from one base and resumed against another:

     ```bash
     header_base=$(sed -n 's/^Base branch: //p' "<plan_file>" | head -n1)
     [ -z "$header_base" ] || [ "$header_base" = "$base_branch" ] \
       || echo "BASE_MISMATCH:$header_base vs $base_branch"
     ```

     `BASE_MISMATCH` → **stop and ask** which base is correct; do not guess and do not cut.

- **Reuse check next** (the same rule Re-entry Routing states). A worktree can already exist here — the risk-mitigation "before" stop below leaves one in place, and `git worktree add -b` fails on an existing branch. Ask the **canonical classifier** rather than parsing porcelain here; it is the one definition of "a usable worktree record", shared with Re-entry Routing and with the abort / Step 9 teardown, so the two halves of the framework cannot drift (t1548):

  **Keep the exit status — `read` alone cannot tell "no worktree" from "the helper never ran".** On a usage or environment failure (exit 2 / 3 — not a repository, `git worktree list` failed) the helper prints **nothing** to stdout, and `read` still succeeds with an empty state. Capture both:

  ```bash
  wt_rc=0
  wt_out="$(./.aitask-scripts/aitask_task_worktree.sh resolve <task_name>)" || wt_rc=$?
  read -r wt_state wt_path <<<"$wt_out"
  ```

  - **`wt_rc` is non-zero, or `wt_state` is empty or not one of the six states below** → the classification did not happen. **Stop and ask the user**; report `wt_rc` and the helper's stderr. Do **not** treat it as "no worktree" and do **not** cut — the whole point of the helper's fail-closed contract is that a producer error is its own state, never a negative result.
  - **`USABLE`** → work in `"$wt_path"` and **skip the cut below**. Do not assume it equals `<worktree_path>` — a worktree that was moved makes that guess wrong, and the failure mode is silent (implementing in the wrong tree).
  - **`NONE`** → nothing is registered; cut it below.
  - **`STALE` / `LOCKED` / `MAIN` / `UNSAFE`** → **stop and ask the user**, naming the state and the path. Do **not** fall through to the cut: `aitask/<task_name>` already exists, so `git worktree add -b` would fail outright. And do not "repair" it by pruning — a `STALE` record is a worktree someone moved by hand, and the record is the only thing keeping their branch from being deletable. Offer the concrete remedies instead (`git worktree repair <new path>` to re-link it, `git worktree unlock` for a locked one) and let the user decide.

- **Otherwise cut it now**, at `<worktree_path>` and from the confirmed base:

  ```bash
  mkdir -p "$(dirname "$worktree_path")"
  git worktree add -b aitask/<task_name> "$worktree_path" "$base_branch"
  ```

  Bind the base to a shell variable rather than substituting the literal — the same injection rule Step 5 and Step 9 state for user-authored branch names.

- Work in the reused or newly cut directory for the implementation below.

**Record implementing agent:** Execute the **Agent Attribution Procedure** (see `agent-attribution.md`) to record which code agent and model is implementing this task.

**Repository structure awareness:** Before starting implementation, read `repo-structure.md`

**Cross-repo child assignment (post-approval creation):** If `cross_repo_planned` is `true` (set in `planning.md` §6.1 — the approved plan is a cross-repo paired design), execute the **Cross-Repo Child Assignment Procedure** (see `cross-repo-child-assignment.md`) now. It creates the cross-repo parent first, then assigns all children (local + cross-repo) to their parents with their plans, demotes the local parent to a parent-of-children, and presents its own child checkpoint. When it returns, the workflow has ended (via that checkpoint's "Start first child" / "Stop here") — do **NOT** continue with the normal single-task implementation below or proceed to Step 8. (This is the post-approval creation gate: planning runs in read-only plan mode, so no tasks were created during Step 6.)
{%- if profile.record_gates is defined and profile.record_gates %}

**Record plan-approved gate:** Reaching Step 7 means the Step 6 checkpoint approved the plan. Execute the **Gate Recording Procedure** (see `gate-recording.md`) with `task_id`, `gate_name=plan_approved`, `status=pass`, `fields="type=human"`.
{%- endif %}

**Risk fields (post-approval write):** If the approved plan contains a `## Risk` section (authored by the Risk Evaluation Procedure during planning), write the two decided levels to the task's frontmatter now:

```bash
./.aitask-scripts/aitask_update.sh --batch <task_id> \
  --risk-code-health <risk_level_code_health> \
  --risk-goal-achievement <risk_level_goal_achievement>
```

Skip silently if the plan has no `## Risk` section (e.g. the task is not risk-gated). This is the post-approval write gate: planning runs in read-only plan mode, so the fields are not written during Step 6.
{%- if profile.record_gates is defined and profile.record_gates and 'risk_evaluated' in rendered_set %}

**Record risk-evaluated gate (only when the task will NOT be orchestrator-recorded):** When the plan has a `## Risk` section, decide whether to self-record `risk_evaluated`. The Step-9 orchestrator records it for any task whose *enforced active set* contains `risk_evaluated`; self-recording here too would double-record. Check first:

```bash
./.aitask-scripts/aitask_gate.sh should-self-record <task_id> risk_evaluated
```

If it exits **0** (the gate is not in the task's active set), execute the **Gate Recording Procedure** (see `gate-recording.md`) with `task_id`, `gate_name=risk_evaluated`, `status=pass`, `fields="type=machine"`. If it exits **1** (active), **skip** — the Step-9 orchestrator records it (no double-record).
{%- endif %}
{%- if 'risk_evaluated' in rendered_set %}

**Risk-mitigation "before" creation (post-approval):** If the approved plan has a `### Planned mitigations` subsection with ≥1 `before` line (authored during planning by the Risk-Mitigation Follow-up Procedure; inline `pre-phase`/`post-phase` lines are not spawn candidates — a plan with only inline mitigations has no `before` lines, so `risk_before_blocking` stays false and the session-stop branch below never fires), execute **Part 2 (Step 7 "before" creation)** of that procedure now (see `risk-mitigation-followup.md`). It creates each "before" mitigation as an **independent task the original depends on** (not a child), reconciling tasks an earlier interrupted run already created, converges the original's `depends:` and `risk_mitigation_tasks` blocking edge, and back-fills the plan's mitigation links.

If it returns `risk_before_blocking: true`, the original is blocked by ≥1 unfinished mitigation — created this run or recovered from an earlier one — and must **not** be implemented this session. Stop the original here (name the unfinished mitigation task(s) in the display):

1. Release the task lock via the **Lock Release Procedure** (see `lock-release.md`).
2. Revert the task to `Ready` and clear `assigned_to` (it will show **Blocked** in `ait ls` until the mitigation lands):
   ```bash
   ./.aitask-scripts/aitask_update.sh --batch <task_num> --status Ready --assigned-to ""
   ```
3. Commit and push the status revert:
   ```bash
   ./ait git add aitasks/
   ./ait git commit -m "ait: Revert t<task_num> to Ready (risk mitigation pending)" 2>/dev/null || true
   ./ait git push
   ```
4. Display: "Unfinished risk-mitigation 'before' task(s) the original depends on: t\<ids\>. Task t\<task_id\> reverted to Ready — implement the mitigation(s) first, then re-pick t\<task_id\> (its plan will be force re-verified)." Then **END the workflow** — do NOT proceed to the implementation below or to Step 8.

If it returns `risk_before_blocking: false` (no "before" mitigations, or all of them already landed), continue to implementation normally.
{%- endif %}

Follow the approved plan, working in the directory specified in the plan metadata.

Update the external plan file as you progress:
- Mark steps as completed
- Note any deviations or changes from the original plan
- Record issues encountered during implementation

**IMPORTANT:** Do NOT commit changes automatically after implementation. Proceed to Step 8 for user review and approval.

**Note:** When committing implementation changes (in Step 8), the commit message must follow the `<issue_type>: <description> (t<task_id>)` format. See Step 8 for details.

### Step 8: User Review and Approval

**⚠️ NON-SKIPPABLE — Auto mode and execution profiles do NOT bypass this review.**

The AskUserQuestion below is load-bearing infrastructure, not a routine
confirmation. Auto mode's "minimize interruptions / prefer assumptions for
routine decisions" guidance and execution-profile shortcuts
(`skip_task_confirmation`, `post_plan_action`, etc.) target other prompts in
the flow — they do NOT cover this review. The only valid skips are profile
keys explicitly named in this SKILL.md as covering Step 8 review (currently:
none). Skipping this prompt removes the user's last chance to test the change
before it lands in git.

**Explicit acceptance required — every iteration.** When the user picks
"Need more changes", the loop returns to the top of Step 8: after applying
the requested changes, the AskUserQuestion review prompt MUST be re-issued.
Repeat for every iteration. The ONLY green light to commit is the user
explicitly selecting "Commit changes" with no accompanying notes, requests,
or open concerns. Tacit consent — silence, lack of objection, "looks fine
I guess", a comment that mentions any further change — is NOT acceptance;
keep iterating. There is no upper bound on iterations.


{%- if profile.record_gates is defined and profile.record_gates %}

**Procedure-backed gates — run before review (their changes must be reviewed and committed with the code):**

Some gates verify *work an agent must do* (`kind: procedure` in `aitasks/metadata/gates.yaml` — e.g. `docs_updated`). The headless engine defers these; the workflow runs them **here, before the change summary**, so any files they produce are part of the reviewed diff and land in the Step-8 `(t<task_id>)` commit.

- List the task's declared procedure-backed gates that are **not** terminal-satisfied (their current ledger status is neither `pass` nor `skip`):
  ```bash
  ./.aitask-scripts/aitask_gate.sh procedure-gates <task_id>
  ```
- If the output is empty, skip this step. Otherwise, for **each** gate `<gate>` printed:
  1. Allocate the run and open its `running` block:
     ```bash
     ./.aitask-scripts/aitask_gate.sh begin-procedure <task_id> <gate>
     ```
     Parse `RUN_ID:<run-id>` and `ATTEMPT:<attempt>` from the output.
  2. Resolve the gate's registry `verifier` (an `aitask-gate-<name>` value) to its `SKILL.md` **in your agent's skill tree** and **Read-and-follow that skill** with arguments `<task_id> <attempt> <run-id>`. The skill inspects the change, updates the docs **confirming with the user**, and appends the terminal result (`pass` / `skip` / `fail`) via `append --only-if-running <run-id>`. (Gate skills ship a wrapper surface in every supported agent tree, so the resolution succeeds wherever you are running. Selecting a specific code-agent/model per gate is a planned generalization — see t635_19's follow-up.)
  3. If the skill records `fail` (the user rejected needed doc work), surface it — the gate is unsatisfied and Step-9 archival will be blocked until it is resolved.

  This dispatch is generic over `kind: procedure` gates (`docs_updated` is the first); a gate already `pass`/`skip` is done and is not re-dispatched.
{%- endif %}

After implementation is complete, the user MUST be given the opportunity to review and test changes before any commits are made.

- **Show change summary:**
  ```bash
  git status
  git diff --stat
  ```

- **Ask for user approval using `AskUserQuestion`:**
  - Question: "Implementation complete. Please review and test the changes. When ready, select an option:"
  - Header: "Review"
  - Options:
    - "Commit changes" (description: "Changes reviewed and tested, ready to commit")
    - "Need more changes" (description: "Adjustments needed before committing")
    - "Abort task" (description: "Discard changes and revert task status")

- **If "Commit changes":**
  - **Verify the plan file exists externally (Claude Code only):** If running in Claude Code, execute the **Plan Externalization Procedure** (see `plan-externalization.md`) as a reactive safety fallback before touching the plan file. It is a no-op (`PLAN_EXISTS`) if the plan was already externalized in Step 6, and it recovers from `~/.claude/plans/` if Step 6 was skipped. If the procedure reports `NOT_FOUND:no_internal_files` / `no_internal_dir`, warn the user: "No plan file exists in `aiplans/` and no recent internal plan was found. The implementation will be committed without a plan file update." and skip the consolidation and plan-commit sub-steps below. Other code agents write plans directly to `aiplans/` and skip this check.
  - **Consolidate the plan file** before committing:
    - Read the current plan file from `aiplans/`
    - Review `git diff --stat` against the plan to identify any changes not yet documented
    - Add or update a "Final Implementation Notes" section at the end of the plan:
      ```markdown
      ## Final Implementation Notes
      - **Actual work done:** <summary of what was actually implemented vs what was originally planned>
      - **Deviations from plan:** <any changes from the original approach and why>
      - **Issues encountered:** <problems found during implementation and how they were resolved>
      - **Key decisions:** <technical decisions made during implementation>
      - **Upstream defects identified:** Did diagnosis surface a separate, pre-existing bug in a different script/helper/module — whether or not it *caused* the current symptom? Anything you noticed about another piece of code that is broken or wrong belongs here, including defects that are out of scope for the current task or "possibly worth a separate issue". List each defect as a bullet of the form `path/to/file.ext:LINE — short summary` (e.g. `aitask_brainstorm_delete.sh:109-111 — worktree-prune ordering bug leaves stale crew-brainstorm-<N> branch`). Write `None` (verbatim) only if no related defect was identified — this subsection is read by Step 8b. Do not list style/lint cleanups, refactor opportunities, test gaps (those go through `/aitask-qa`), or unrelated TODOs.

        **All related defects go here, in this canonical bullet.** Do not record related defects under a separate side bullet (e.g. `- **Trailing-slash follow-up:**`, `- **Possibly worth a separate issue:**`), an "Out of scope" section, or free prose. Step 8b parses this single bullet by name; anything written elsewhere is invisible to the follow-up offer.

        *Anti-example (do not do this):* canonical bullet writes `None` and a side bullet `- **Trailing-slash follow-up:**` carries the actual defect. The parser sees `None`, the user never gets the follow-up offer, and the defect is silently buried in the archived plan.
      - **Notes for sibling tasks:** <patterns established, gotchas discovered, shared code created, or other information useful for subsequent child tasks> (include this section if this is a child task)
      ```
    - **IMPORTANT for child tasks:** The plan file will be archived and serve as the primary reference for subsequent sibling tasks. Ensure the Final Implementation Notes are comprehensive enough that a fresh context can understand what was done and learn from the experience.
    - The plan file should now serve as a complete record of: the original plan, any post-review change requests (from the "Need more changes" loop), and final implementation notes
  - **Contributor attribution:** Execute the **Contributor Attribution Procedure** (see `contributor-attribution.md`) to determine whether the commit needs an imported-contributor block.
  - **Code-agent attribution:** Execute the **Code-Agent Commit Attribution Procedure** (see `code-agent-commit-attribution.md`) to resolve a `Co-Authored-By` trailer from `implemented_with`. If agent attribution fails, continue with the contributor-only or plain commit message as applicable.
  - **Commit code changes and plan file separately** (code uses regular `git`, plan uses `./ait git`):
    1. **Code commit** — Stage and commit source code changes:
       ```bash
       git add <changed_code_files>
       git commit -m "$(cat <<'EOF'
       <issue_type>: <description> (t<task_id>)

       <optional imported contributor block>
       <optional code-agent trailer>
       EOF
       )"
       ```
       Only include implementation files — never include `aitasks/` or `aiplans/` paths. Skip this commit if there are no code changes. If neither attribution procedure returns content, the code commit can remain a single-line subject.
    2. **Plan file commit** — Stage and commit the updated plan file:
       ```bash
       ./ait git add aiplans/<plan_file>
       ./ait git commit -m "ait: Update plan for t<task_id>"
       ```
       Skip if the plan file was not modified.
  - **IMPORTANT — Commit message conventions:**
    - **Code commits** MUST use `<issue_type>: <description> (t<task_id>)` format, where `<issue_type>` comes from the task's `issue_type` frontmatter (one of: `bug`, `chore`, `documentation`, `enhancement`, `feature`, `performance`, `refactor`, `style`, `test`). The `(t<task_id>)` suffix is used by `aitask_issue_update.sh` to find commits. Examples: `feature: Add channel settings screen (t16)`, `bug: Fix login validation (t16_2)`.
    - **When attribution is present,** compose one final multiline commit message: subject first, imported contributor block second, code-agent trailer last. For PR-imported tasks the contributor block includes `Based on PR:`; for issue-imported contributor metadata it may be only the contributor trailer.
    - **Plan/task file commits** use the `ait:` prefix (e.g., `ait: Update plan for t16`). Administrative commits (status changes, archival) also use `ait:` and must NOT include the `(t<task_id>)` tag.
    - **Never mix** code files and `aitasks/`/`aiplans/` files in the same `git add` or commit. Code uses regular `git`; task/plan files use `./ait git`. This separation is required when task data lives on a separate branch, and is safe in legacy mode where `./ait git` passes through to plain `git`.
  - **Note:** For test coverage analysis and test plan generation, run `/aitask-qa <task_id>` after implementation.
{%- if profile.record_gates is defined and profile.record_gates %}
  - **Record review-approved gate:** Execute the **Gate Recording Procedure** (see `gate-recording.md`) with `task_id`, `gate_name=review_approved`, `status=pass`, `fields="type=human"`.
{%- endif %}
  - Proceed to Step 8b

- **If "Need more changes":**
  - Ask user what needs to change
  - Make the requested changes
  - **Update the plan file** to log what was changed:
    - Append a "Post-Review Changes" section (if not already present) to the plan file in `aiplans/`
    - Add a numbered change request entry with timestamp:
      ```markdown
      ## Post-Review Changes

      ### Change Request 1 (YYYY-MM-DD HH:MM)
      - **Requested by user:** <summary of what the user asked for>
      - **Changes made:** <summary of what was actually implemented>
      - **Files affected:** <list of modified files>
      ```
    - Increment the change request number for each review iteration
  - Return to the beginning of Step 8

- **If "Abort":**
  - Execute the **Task Abort Procedure** (see `task-abort.md`)

### Step 8b: Upstream Defect Follow-up

Entered from Step 8 after the "Commit changes" branch has committed code and plan files. Offers the user a chance to spawn a standalone aitask for an upstream defect surfaced during diagnosis (when the failure was *seeded* by a separate, pre-existing bug elsewhere — a different script, helper, or module).

Execute the **Upstream Defect Follow-up Procedure** (see `upstream-followup.md`) with:
- `task_file`, `task_id`, `is_child`, `active_profile`, `parent_id` from the current context.
- `task_slug` — filename stem with the `t<id>_` prefix stripped (e.g. `aitasks/t42_add_login.md` → `add_login`).

When the procedure returns, proceed to Step 8c.

### Step 8c: Manual Verification Follow-up

Entered from Step 8b (or directly from Step 8 if 8b was a no-op). At this point code and plan files have already been committed. Offers the user a chance to queue a standalone manual-verification task that will be picked after this task archives.

Execute the **Manual Verification Follow-up Procedure** (see `manual-verification-followup.md`) with:
- `task_file`, `task_id`, `is_child`, `active_profile`, `parent_id` from the current context.
- `task_slug` — filename stem with the `t<id>_` prefix stripped (e.g. `aitasks/t42_add_login.md` → `add_login`).

{%- if 'risk_evaluated' in rendered_set %}
When the procedure returns, proceed to Step 8d.

### Step 8d: Risk-Mitigation "After" Follow-up

Entered from Step 8c. At this point the code and plan files have already been committed. This step applies only when the task was risk-gated; if the approved plan has a `### Planned mitigations` subsection with ≥1 `after` line (authored during planning by the Risk-Mitigation Follow-up Procedure; inline `pre-phase`/`post-phase` lines are not spawn candidates and are skipped), execute **Part 3 (Step 8d "after" creation)** of that procedure now (see `risk-mitigation-followup.md`) with `task_id`, `task_num`, `plan_file`, `is_child`, `parent_id`, and `active_profile` from the current context. If the plan has no such subsection (the common case for non-risk-gated tasks), this step is a no-op.

It creates each "after" mitigation as an independent follow-up task and records it in the original's `risk_mitigation_tasks`. "After" mitigations block nothing, so the workflow continues normally. When the procedure returns, proceed to Step 9.
{%- else %}
When the procedure returns, proceed to Step 9.
{%- endif %}

### Step 9: Post-Implementation

Execute the post-implementation cleanup steps.

**If a separate branch was created:**

- **Resolve the merge target into a shell variable.** Read it out of the plan file's metadata header — do **not** paste the value into any command:

  ```bash
  output_branch=$(sed -n 's/^Output branch: //p' "<plan_file>" | head -n1)
  provenance="plan header"
  [ -n "$output_branch" ] || { output_branch=main; provenance="legacy plan, no Output branch field"; }
  printf '%s' "$output_branch" | grep -qE '^[A-Za-z0-9._/-]+$' &&
    git check-ref-format --branch "$output_branch" >/dev/null 2>&1 ||
    echo "UNSAFE_OUTPUT_BRANCH"
  ```

  `UNSAFE_OUTPUT_BRANCH` → **stop**: the plan header records a branch name that is not shell-safe. Report it and do not merge.

  Binding to a variable — rather than substituting the literal — is what makes an injected ref name inert: `git checkout "dev$(id)" --` executes `id`, whereas `git checkout "$output_branch" --` never does. Use the quoted variable in every command below.

  Do **not** fall back to `Base branch:`. A plan written before this field existed merged to `main`, and reading its `Base branch:` would retroactively change where in-flight work lands.

  Call the resolved value `<output_branch>`. Resolve it **only** from the plan header — never from `profile.output_branch`. A resumed session (POSTIMPL re-entry) may run under a different profile, and the header is what guarantees it merges into the same branch the original session did, keeping the "re-merge is a git no-op" property this workflow relies on.

- **Probe the merge queue.** Run from the repo root, not from `aiwork/<task_name>/`. Before asking for approval, execute the **Merge Broker Procedure** (see `merge-broker.md`) section **`## Probe — report the queue holder`** with `task_id`, `task_name` and the bound `$output_branch`. It runs `aitask_merge_task.sh status`, which acquires nothing, and returns the queue state so the approval question can name the task this merge is waiting on.

  The merge itself — pre-flight, checkout and `git merge` — is performed by the broker inside the mutex, so it is **not** duplicated here. The tag/detached-HEAD trap and the foreign-worktree rule are explained with the `PREFLIGHT_MISSING` / `PREFLIGHT_FOREIGN_WORKTREE` branches in that procedure.

**⚠️ NON-SKIPPABLE — Auto mode and execution profiles do NOT bypass this merge approval.**

The AskUserQuestion below is a workflow gate, not a routine confirmation. The
following do NOT cover this prompt:
- Execution profiles (no profile key currently bypasses Step 9 merge approval).
- Auto mode / 'work without stopping' system-injected directives.
- Generic user instructions to 'be brief' or 'don't ask'.

The only valid skips are profile keys explicitly named in this SKILL.md as
covering Step 9 merge approval (currently: none) or the user explicitly
authorizing the merge in chat before the prompt fires.

**IMPORTANT:** Use `AskUserQuestion` to ask: "Proceed with merge of code changes into the `<output_branch>` branch (\<provenance\>)?" with options "Yes, proceed with merge" / "No, not yet". Name the resolved branch and its provenance in the question text itself — a target guessed via the legacy `main` fallback must be visible to the user as a guess. **When the probe reported `HELD`, append `Queued behind t<N>.` to the END of that question**, naming the holding task — appended, because the leading `Proceed with merge of code changes into` is a pinned phase anchor and must not be reworded. Serializing the merge is not a reason to auto-approve it. Do NOT proceed until the user approves.
{%- if profile.record_gates is defined and profile.record_gates %}

**Record merge-approved gate:** Once the user approves the merge, execute the **Gate Recording Procedure** (see `gate-recording.md`) with `task_id`, `gate_name=merge_approved`, `status=pass`, `fields="type=human"`.
{%- endif %}

- **Merge under the mutex.** The merge runs in the **shared repo root**, so concurrent tasks drive one HEAD, one index and one working tree. Execute the **Merge Broker Procedure** (see `merge-broker.md`) section **`## Entry — acquire the reservation and merge`** with `task_id`, `task_name` and the bound `$output_branch`. It holds the merge mutex across the pre-flight, `git checkout "$output_branch" --`, the `symbolic-ref` assertion and `git merge "aitask/<task_name>"`, and it branches on every verdict — including the dirty-tree and conflict cases this step used to handle inline.

  Pass `$output_branch` as the **quoted shell variable**, never as a pasted literal: `"dev$(id)"` executes inside double quotes and git accepts such refs, so binding is what makes an injected name inert. The broker validates it again and answers `UNSAFE_OUTPUT_BRANCH` if it is not shell-safe.

  The procedure returns here with the reservation **held** only when the merge landed. On every other verdict it stops the workflow itself — do not continue past it to verification.

- **Verify implementation (build / tests / lint):**

  This block is the re-entry target of the Merge Broker Procedure's **`## Return to Step 9 — Verify implementation`**. The merge reservation is **held for its entire duration** — that is what makes the verdict attributable, since nothing else can check out, merge into, or mutate the tree the build is reading. Do not release it here; the release decision comes after.

  Do **not** re-derive which gates this task declares — the **gate orchestrator**
  owns that decision and reports it. Dispatch it once, capturing both its output
  and exit status, then branch on the result:

  ```bash
  gates_out="$(./ait gates run <task_id> 2>&1)"; gates_rc=$?
  ```

  - **If `gates_rc` is nonzero** — an *infrastructure* failure (`ait`/wrapper
    error, task resolution failed, Python unavailable, bad registry path, usage
    error). `ait gates run` exits 0 for every normal gate outcome (a `fail`/`error`
    is a recorded result, not a process error), so a nonzero exit is never an
    ordinary gate failure. **STOP and diagnose** using `gates_out`; do **NOT** fall
    through to either branch below (the declared-vs-not decision is only meaningful
    on a clean exit).

  - **Else if `gates_out` contains the line `No gates declared; nothing to do.`** —
    the task has not opted into the gate system (the common case today). Run the
    legacy inline build verification:
    - Read `aitasks/metadata/project_config.yaml` and check the `verify_build` field
    - **If `verify_build` is absent, null, or empty (or file doesn't exist):** Display "No verify_build configured — skipping build verification." and skip this step.
    - **If `verify_build` is a single command string:** Run it.
    - **If `verify_build` is a list of commands:** Run each sequentially (stop on first failure).
    - **If the build fails:**
      1. Analyze the error output and compare against the changes introduced by this task (`git diff` against the base)
      2. **If the failure is caused by this task's changes:** Go back to the implementation to fix the build errors. After fixing, re-run the build command(s). Repeat until the build passes.
      3. **If the failure is NOT related to this task's changes** (pre-existing issue, environment problem, etc.): Log the build failure details in the plan file's "Final Implementation Notes" section under a "Build verification" entry and proceed with the workflow. Do not attempt to fix pre-existing issues.
{%- if profile.record_gates is defined and profile.record_gates %}
    - **Record build-verified gate:** When `verify_build` ran, execute the **Gate Recording Procedure** (see `gate-recording.md`) with `task_id`, `gate_name=build_verified`, `status=pass` (use `fail` if the build failed for reasons unrelated to this task and you proceeded), `fields="type=machine verifier=<command>"`. Skip if no `verify_build` is configured.
{%- endif %}

  - **Otherwise** — the orchestrator ran the task's declared gates and **recorded
    each run itself**. Read its per-gate report lines (`  <gate>: <status> …`) and
    act per status:
    - `pass` / `skip` — satisfied (`skip` = not applicable, e.g. no command configured); continue.
    - `fail` — an *ordinary* gate failure: inspect `./ait gate log <task_id> <gate>` and diff against the base. If caused by this task, fix and re-run `./ait gates run <task_id>`; repeat until it passes. If pre-existing/unrelated, record `./ait gate fail <task_id> <gate> --reason "…"` and log it in the plan's Final Implementation Notes.
    - `error` (`  <gate>: error …`) **or** a malformed-correction line (`  ⚠ <gate>: malformed …`) — a verifier **infrastructure** failure (launch failure, timeout, exit 3, or a status that contradicted the exit code), NOT an ordinary gate result. **Diagnose the verifier/config** (its log, the command, the timeout); do not "fix the code" as if it were a `fail`, do not record a manual pass, and do **not** proceed to archival until the verifier itself runs cleanly.
    - `blocked: …` — an unlocked gate could not run / none remain runnable. `blocked: exhausted …` or `blocked: upstream … not satisfied` means the gate is **unsatisfied** — surface and diagnose; do **not** treat it as satisfied or proceed. `blocked: pending human signal` → route to the human sign-off action (never self-signal).
    - `pending` (human gate) — surface to the user; never self-signal.
    - Do **NOT** also run the manual "Record build-verified gate" step in this branch — the orchestrator already appended each gate's run (no double-record).

- **Release decision, cleanup and release.** With the verification outcome in hand, return to the **Merge Broker Procedure** (see `merge-broker.md`) section **`## Re-entry — release decision`**, still holding the reservation. Its verification-outcome table decides whether this task completes or exits in-flight, and `## Exit — cleanup and release` performs `cleanup` and `finish` accordingly.

  Two rules that block the two damaging mistakes: **cleanup is a completion step, never an in-flight one** — it deletes `aitask/<task_name>` and its worktree, which is the branch a `POSTIMPL` resume must re-merge — and `finish` on an in-flight exit is a **release, not a success claim**. The broker's `cleanup` delegates to the same bare, `--strict` `aitask_task_worktree.sh remove <task_name>` this step used to run directly, so the teardown semantics are unchanged: uncommitted work blocks removal rather than being discarded, only `CLEAN` exits 0, the worktree is resolved from its `git worktree list` record so a moved one is still torn down (t1548), and nothing is ever pruned or force-deleted.

  Return here with `lock: none` for archival. If the release decision took an in-flight exit, the procedure ends the workflow — do not archive.

**For child tasks — verify plan completeness before archival:**

- Read the plan file from `aiplans/p<parent>/<child_plan>`
- Verify it contains a "Final Implementation Notes" section with comprehensive details
- If missing or incomplete, add/update it now — the archived plan will serve as the primary reference for subsequent sibling tasks
- Ensure the notes include: actual work done, issues encountered and resolutions, and any information useful for sibling tasks

**Run the archive script:**

Entered with `lock: none` — the merge reservation was released by the Merge Broker Procedure's `finish` before control returned here.

All archival operations (metadata updates, file moves, lock releases, folded task cleanup, git staging, and commit) are handled by a single script call:

For parent tasks:
```bash
./.aitask-scripts/aitask_archive.sh <task_num>
```

For child tasks:
```bash
./.aitask-scripts/aitask_archive.sh <parent>_<child>
```

The script automatically handles:
- Updating task metadata (status → Done, updated_at, completed_at)
- Creating archive directories and moving task/plan files
- For child tasks: removing child from parent's children_to_implement
- For child tasks: archiving parent too if all children are complete
- Releasing task locks (and parent locks if parent was also archived)
- For parent tasks: deleting folded tasks (if any, where status is not Implementing/Done)
- Git staging and committing all changes

**Gate guard — pending declared gates (handle BEFORE parsing the success output):**

The archive script refuses to archive a task whose declared `gates:` are not all
`pass`: it exits non-zero (code 2) and prints a `GATE_PENDING:<csv>` line (plus a
`GATE_BLOCKED` line). If you see that, the archival did **not** happen — do NOT
treat it as success or run the parse step below. (A task with no declared gates,
or all gates passing, exits 0 and archives straight through — the common case
today.) Instead use `AskUserQuestion`:
- Question: "Task t<task_id> can't archive yet — pending gate(s): <csv>. How would you like to proceed?"
- Header: "Gates"
- Options:
  - "Resolve now & archive" (description: "Satisfy the pending gate(s) in this session, then archive immediately")
  - "Defer — keep in-flight" (description: "Leave the task active and re-enterable; archive on a later pick")

- **If "Resolve now & archive":** For each pending gate the user can satisfy now
  (run docs/tests, perform the review, etc.), record the pass:
  ```bash
  ./.aitask-scripts/aitask_gate.sh append <task_id> <gate> pass [k=v ...]
  ```
  For a **procedure-backed** gate (`kind: procedure` — e.g. `docs_updated`; check
  `./.aitask-scripts/aitask_gate.sh procedure-gates <task_id>`), do **not** hand-append
  a pass — dispatch its skill instead (as in Step 8): `begin-procedure <task_id>
  <gate>` → Read-and-follow the gate's `aitask-gate-<name>` skill in your agent's
  skill tree, which records the terminal `pass`/`skip`/`fail` itself.
  After each, re-check `./.aitask-scripts/aitask_gate.sh archive-ready <task_id>`.
  **The moment it prints `ALL_PASS`, re-run the archive script** (same command as
  above) and continue with the normal success-path parsing below — no re-pick
  needed (the archival commit persists the recorded gate runs). If a gate
  genuinely cannot be satisfied in this session (e.g. an async reviewer you do
  not control), fall through to "Defer".
- **If "Defer — keep in-flight":** Do not archive. The task stays active
  (`Implementing`) and re-enterable — its committed code and recorded gate runs
  are the resume state, and the task lock is intentionally left held. Inform the
  user: "Archival deferred — t<task_id> stays in-flight. Re-pick it with
  `/aitask-pick <task_id>` once the pending gate(s) pass." Skip the
  push-after-archival step and proceed directly to **Step 9b** (Satisfaction
  Feedback) — the implementation work was completed.

**Parse the script output and handle interactive follow-ups:**

The script outputs structured lines. Parse each line and handle accordingly:

- `ISSUE:<task_num>:<issue_url>` — Execute the **Issue Update Procedure** (see `issue-update.md`) for the task
- `RELATED_ISSUE:<task_num>:<issue_url>` — A related/merged issue. Execute the **Related Issue Update Procedure** (see `issue-update.md`, "Related Issues" section) using `--issue-url`
- `PARENT_ISSUE:<task_num>:<issue_url>` — Execute the **Issue Update Procedure** (see `issue-update.md`) for the parent task
- `PARENT_RELATED_ISSUE:<task_num>:<issue_url>` — A related/merged issue on the parent. Execute the **Related Issue Update Procedure** (see `issue-update.md`, "Related Issues" section) using `--issue-url`
- `FOLDED_RELATED_ISSUE:<folded_task_num>:<issue_url>` — A related issue on a folded task (file deleted). Handle identically to `FOLDED_ISSUE:` below (same AskUserQuestion, same `--issue-url` commands, same `task_id` note)
- `FOLDED_ISSUE:<folded_task_num>:<issue_url>` — The folded task's file has been deleted, so the standard Issue Update Procedure cannot be used (it requires the task file). Instead, handle inline:
  - Use `AskUserQuestion`:
    - Question: "Folded task t<folded_task_num> had a linked issue: <issue_url>. Update/close it?"
    - Header: "Issue"
    - Options:
      - "Close with notes" (description: "Post implementation notes from primary task and close")
      - "Comment only" (description: "Post implementation notes but leave open")
      - "Close silently" (description: "Close without posting a comment")
      - "Skip" (description: "Don't touch the issue")
  - If "Close with notes":
    ```bash
    ./.aitask-scripts/aitask_issue_update.sh --issue-url "<issue_url>" --close <task_id>
    ```
  - If "Comment only":
    ```bash
    ./.aitask-scripts/aitask_issue_update.sh --issue-url "<issue_url>" <task_id>
    ```
  - If "Close silently":
    ```bash
    ./.aitask-scripts/aitask_issue_update.sh --issue-url "<issue_url>" --close --no-comment <task_id>
    ```
  - If "Skip": do nothing
  - Note: Uses the primary `task_id` (not `folded_task_num`) so the comment references the primary task's commits and plan file
- `PR:<task_num>:<pr_url>` — Execute the **PR Close/Decline Procedure** (see `pr-close-decline.md`) for the task
- `PARENT_PR:<task_num>:<pr_url>` — Execute the **PR Close/Decline Procedure** (see `pr-close-decline.md`) for the parent task
- `FOLDED_PR:<folded_task_num>:<pr_url>` — The folded task's file has been deleted, so the standard PR Close/Decline Procedure cannot be used. Instead, handle inline:
  - Use `AskUserQuestion`:
    - Question: "Folded task t<folded_task_num> had a linked PR: <pr_url>. Close/decline it?"
    - Header: "PR"
    - Options:
      - "Close with notes" (description: "Post implementation notes from primary task and close/decline")
      - "Comment only" (description: "Post implementation notes but leave open")
      - "Close silently" (description: "Close/decline without posting a comment")
      - "Skip" (description: "Don't touch the PR")
  - If "Close with notes":
    ```bash
    ./.aitask-scripts/aitask_pr_close.sh --pr-url "<pr_url>" --close <task_id>
    ```
  - If "Comment only":
    ```bash
    ./.aitask-scripts/aitask_pr_close.sh --pr-url "<pr_url>" <task_id>
    ```
  - If "Close silently":
    ```bash
    ./.aitask-scripts/aitask_pr_close.sh --pr-url "<pr_url>" --close --no-comment <task_id>
    ```
  - If "Skip": do nothing
  - Note: Uses the primary `task_id` (not `folded_task_num`) so the comment references the primary task's commits and plan file
- `FOLDED_WARNING:<task_num>:<status>` — Warn the user: "Folded task t<N> has status '<status>' — skipping automatic deletion. Please handle it manually."
- `PARENT_ARCHIVED:<path>` — Inform user: "All child tasks complete! Parent task also archived."
- `COMMITTED:<hash>` — Archival commit was created

**Push after archival:**

```bash
./ait git push
```

### Step 9b: Satisfaction Feedback

Execute the **Satisfaction Feedback Procedure** (see `satisfaction-feedback.md`) with `skill_name` and `detected_agent_string` from the context variables.

### Procedures

The following procedures are in individual files — read on demand when referenced:

- **Task Abort Procedure** (`task-abort.md`) — Lock release, status revert, worktree cleanup. Referenced from Step 6 checkpoint and Step 8.
- **Issue Update Procedure** (`issue-update.md`) — Update/close linked issues during archival. Referenced from Step 9.
- **PR Close/Decline Procedure** (`pr-close-decline.md`) — Close/decline linked pull requests during archival. Referenced from Step 9.
- **Contributor Attribution Procedure** (`contributor-attribution.md`) — Credit PR contributors in commit messages. Referenced from Step 8.
- **Code-Agent Commit Attribution Procedure** (`code-agent-commit-attribution.md`) — Resolve code-agent Co-Authored-By trailer. Referenced from Step 8.
- **Plan Externalization Procedure** (`plan-externalization.md`) — **Claude Code only.** Copy the approved internal plan file to `aiplans/` and parse externalize helper output. Referenced from planning.md (Step 6) and Step 8.
- **Model Self-Detection Sub-Procedure** (`model-self-detection.md`) — Detect the current code agent and model. Referenced from Agent Attribution and Satisfaction Feedback.
- **Agent Attribution Procedure** (`agent-attribution.md`) — Record implementing code agent and model. Referenced from Step 7.
- **Satisfaction Feedback Procedure** (`satisfaction-feedback.md`) — Collect user feedback and update verified model scores. Referenced from Step 9b and standalone skills.
- **Lock Release Procedure** (`lock-release.md`) — Release task locks. Referenced from Task Abort Procedure.
- **Crash Recovery Procedure** (`crash-recovery.md`) — Surveys in-progress work and prompts the user when a reclaim signal is detected (multi-PC, same-host crash via PID anchor, or lock anomaly). Referenced from Step 4 dispatcher and Step 7 ownership guard.
- **Manual Verification Procedure** (`manual-verification.md`) — Interactive checklist runner for `issue_type: manual_verification` tasks. Referenced from Step 3 (Check 3).
- **Auto-Verification Procedure** (`auto-verification.md`) — Automated verification for `manual_verification` tasks. Supports two strategies: autonomous (execute inline, document at end) and pre-built (design plan, optionally approve, then execute). Persists to `aiplans/p<id>_manual_verification_auto.md`. Referenced from `manual-verification.md` Step 1.5 (whole checklist) and Step 2 (per-item `auto` verb).
- **Manual Verification Follow-up Procedure** (`manual-verification-followup.md`) — Post-implementation prompt offering to create a standalone manual-verification task, with multi-source candidate discovery. Referenced from Step 8c.
- **Upstream Defect Follow-up Procedure** (`upstream-followup.md`) — Post-implementation prompt offering to spawn a standalone bug aitask for an upstream defect surfaced during diagnosis. Reads the plan file's "Upstream defects identified" subsection. Referenced from Step 8b.
- **Remote Drift Check Procedure** (`remote-drift-check.md`) — Warn before implementation if `origin/<base-branch>` is ahead of local, with strong emphasis on files the plan touches. Referenced from planning.md Checkpoint and from **Re-entry Routing**'s `IMPLEMENT` route.
- **Approved-Plan Stop Sequence** (`plan-approved-stop.md`) — The one release-and-revert sequence for a session that ends on an approved-but-not-implemented plan: record the approval (once, `record_gates`-gated), commit the plan, release the lock, revert to `Ready`, push. Referenced from planning.md's "Approve and stop here" and remote-drift-check.md's "Stop and re-verify plan" — a shared reference so neither branch can drop a step by partial copy.
- **Merge-Target Sync Pre-flight Procedure** (`merge-target-sync.md`) — Refresh the merge target before a resumed task reaches Step 9, which never fetches. Fast-forward-only recovery; never reverts the task. Referenced from **Re-entry Routing**'s `POSTIMPL` route.
- **Execution Profile Selection Procedure** (`execution-profile-selection.md`) — Interactive profile scan and selection. Referenced from Step 0a in calling skills.
- **Execution Profile Selection Procedure — Auto-Select** (`execution-profile-selection-auto.md`) — Non-interactive auto-select for remote/web skills. Referenced from Step 1 in aitask-pickrem/aitask-pickweb.
- **Batch Task Creation Procedure** (`task-creation-batch.md`) — Canonical command templates for creating tasks via `aitask_create.sh --batch`. Referenced from planning.md and multiple skills (explore, review, qa, wrap, pr-import, revert).
{%- if profile.record_gates is defined and profile.record_gates %}
- **Gate Recording Procedure** (`gate-recording.md`) — Record a workflow checkpoint into the task's gate ledger and persist it (path-scoped commit + best-effort push) via `aitask_gate_record.sh`. Gated behind the `record_gates` profile key; referenced from Step 7 (plan_approved, risk_evaluated), Step 8 (review_approved), Step 9 (build_verified, merge_approved), and `planning.md` Checkpoint (plan_approved).
{%- endif %}

---

## Notes

- When working on a child task, always include links to parent and sibling task files for context, plus archived sibling plan files as primary reference for completed siblings
- **Archived sibling context priority:** When gathering context for a child task, prefer archived **plan files** (`aiplans/archived/p<parent>/`) over archived task files (`aitasks/archived/t<parent>/`). Plan files contain the full implementation record; task files are just initial proposals. Only use archived task files as fallback when no corresponding plan exists.
- Child tasks are archived to `aitasks/archived/t<parent>/` preserving the directory structure
- Child plans are archived to `aiplans/archived/p<parent>/` preserving the directory structure
- **IMPORTANT:** When modifying any task file, always update the `updated_at` field in frontmatter to the current date/time using format `YYYY-MM-DD HH:MM`
- **Child task naming:** Use format `t{parent}_{child}_description.md` where both parent and child identifiers are **numbers only**. Do not insert tasks "in-between" (e.g., no `t10_1b` between `t10_1` and `t10_2`). If you discover a missing implementation step, add it as the next available number and adjust dependencies accordingly
- When archiving a task with an `issue` field, the workflow offers to update/close the linked issue using `aitask_issue_update.sh`. The SKILL.md workflow is platform-agnostic; the script handles platform specifics (GitHub, GitLab, etc.). It auto-detects commits and includes "Final Implementation Notes" from the archived plan file.
- **Folded tasks:** When a task has a `folded_tasks` frontmatter field (set by aitask-explore or aitask-fold), the listed tasks are deleted during Step 9 archival. Folded tasks have status `Folded` with a `folded_into` property pointing to the primary task. They are deleted (not archived) because their full content was incorporated into the primary task's description at creation/fold time.
- **Note:** Folded tasks are handled by `handle_folded_tasks()` in both parent and child archival paths. `/aitask-fold` and manual folding can add `folded_tasks` to any task type.
- **Symlinks and data worktree:** When the project uses a separate `aitask-data` branch, `aitasks/` and `aiplans/` are symlinks to `.aitask-data/`. See `repo-structure.md` for the full architecture and rules.

### Project Configuration

Project-level settings are stored in `aitasks/metadata/project_config.yaml` (git-tracked, shared across team). This is separate from execution profiles (workflow behavior) and `userconfig.yaml` (per-user, gitignored).

| Key | Type | Default | Description | Used in |
|-----|------|---------|-------------|---------|
| `verify_build` | string or list | (none — skip) | Shell command(s) to verify the build after implementation | Step 9; `build_verified` gate |
| `test_command` | string or list | (none — auto-detect) | Shell command(s) for running project tests | aitask-qa Step 4; `tests_pass` gate |
| `lint_command` | string or list | (none — skip) | Shell command(s) for linting project code | aitask-qa Step 4; `lint` gate |
| `attachments_gc_grace` | duration (`30d`/`24h`/`90m`/`120s`/int seconds) | `30d` | Grace window before a **fully-orphaned** attachment (no active *or archived* task references it) is reclaimed by `ait attach gc`. Archiving never decrefs, so an archived task's attachments are kept indefinitely; this knob only governs blobs left unreferenced by `ait attach rm` or task deletion. | `ait attach gc` |

If the file does not exist or a field is absent, the corresponding feature is skipped.

### Execution Profiles

> **Full reference:** See `profiles.md` for the complete profile schema, available keys, and customization guide.

Profiles are YAML files in `aitasks/metadata/profiles/` that pre-answer workflow questions. Default profiles: **default** (all questions asked) and **fast** (skip confirmations).
