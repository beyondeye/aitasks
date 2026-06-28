# Step 6: Create Implementation Plan

Detailed planning workflow for the task-workflow skill. Read this file when
Step 5 (Environment and Branch Setup) is complete and you are ready to plan.

## Table of Contents

- [6.0: Check for Existing Plan](#60-check-for-existing-plan)
- [6.1: Planning](#61-planning)
- [Child Task Documentation Requirements](#child-task-documentation-requirements)
- [Save Plan to External File](#save-plan-to-external-file)
- [Checkpoint](#checkpoint-after-plan-is-saved)

---

## 6.0: Check for Existing Plan

Check if a plan file already exists at the expected path:
- For parent tasks: `aiplans/p<taskid>_<name>.md`
- For child tasks: `aiplans/p<parent>/p<parent>_<child>_<name>.md`

```bash
./.aitask-scripts/aitask_query_files.sh plan-file <taskid>
```
Parse the output: `PLAN_FILE:<path>` means found, `NOT_FOUND` means not found.

**If a plan file exists**, read it.

### Step 6.0a: Force-reverify when a risk mitigation landed

Before applying any plan preference, check whether a "before" risk-mitigation
task has landed since this plan was last verified. If one has, the codebase
changed underneath the plan and it must be re-verified — even if a fresh
verification entry would otherwise let it be skipped. (This is a no-op in the
common case where the task has no `risk_mitigation_tasks`.)

1. Run:
   ```bash
   ./.aitask-scripts/aitask_risk_mitigation_landed.sh <task_file> <plan_file>
   ```
2. Parse the output. The first line is `FORCE_VERIFY:<0|1>`; any following
   `LANDED:<id>|<completed_at>` lines name the mitigations that landed after the
   last verification.
   - **`FORCE_VERIFY:0`** → no mitigation landed (or the field is absent).
     Proceed to the plan-preference logic below unchanged.
   - **`FORCE_VERIFY:1`** →
     - Display the landed mitigations to the user, e.g. "Risk-mitigation task(s)
       landed since the last plan verification: t884_4 (2026-06-01 18:14).
       Forcing plan re-verification."
     - Set a **`force_verify` signal** for this Step 6: the **Verify Decision**
       sub-procedure below MUST append `--force-verify` to its `decide` call.
     - Keep the landed `<id>` list — on entering verify mode (Step 6.1), resolve
       each with `./.aitask-scripts/aitask_query_files.sh archived-task <id>` and
       read the matching `aiplans/archived/p<parent>/` plan to see exactly what
       changed, then re-check the plan's assumptions and file paths against those
       changes. This makes the re-verification targeted, not a blind re-read.


**Profile-driven plan preference** (profile 'fast').


For **child tasks** (when `is_child` is true), use `plan_preference_child: verify`. For **parent tasks**, use `plan_preference: use_current`. Resolve which one applies based on `is_child`, then act on the effective value as follows:


- If the effective value is `"use_current"`: Skip to the **Checkpoint** at the end of Step 6. Display: "Profile 'fast': using existing plan".
- If the effective value is `"verify"`: Run the **Verify Decision** sub-procedure below, then branch on its result. Display: "Profile 'fast': checking verification status".
- If the effective value is `"create_new"`: Proceed with step 6.1 as normal. Display: "Profile 'fast': creating plan from scratch".

When the profile resolves the preference, skip the interactive AskUserQuestion below.

**Verify Decision sub-procedure** (profile-driven verify path only):

1. Use `plan_verification_required = 1` (from profile, default 1 when absent).
2. Use `plan_verification_stale_after_hours = 24` (from profile, default 24 when absent).
3. Run:
   ```bash
   ./.aitask-scripts/aitask_plan_verified.sh decide <plan_file> 1 24
   ```
   If Step 6.0a set the `force_verify` signal, append `--force-verify` to the
   command above (it forces `DECISION:VERIFY` even when a fresh verification
   exists).
4. Parse the 8-line structured output (`KEY:value` per line):
   - `TOTAL:<N>` / `FRESH:<M>` / `STALE:<K>` / `LAST:<agent @ timestamp>` (or `LAST:NONE`)
   - `REQUIRED:<R>` / `STALE_AFTER_HOURS:<H>`
   - `DISPLAY:<human-readable summary>` — print this line verbatim to the user
   - `DECISION:<SKIP|ASK_STALE|VERIFY>`
5. Branch on `DECISION:`:
   - **`SKIP`** → skip verification entirely; jump to the **Checkpoint** at the end of Step 6 (same as `use_current`).
   - **`ASK_STALE`** → use `AskUserQuestion`:
     - Question: the `DISPLAY:` line plus " How would you like to proceed?"
     - Header: "Stale plan"
     - Options:
       - "Verify now" (description: "Enter verify mode; a fresh entry will be appended on exit")
       - "Skip verification" (description: "Use the existing plan as-is, without refreshing")
       - "Create plan from scratch" (description: "Discard the existing plan and start fresh")
     - "Verify now" → enter verification mode (step 6.1 via the verify path).
     - "Skip verification" → jump to the **Checkpoint** (same as `use_current`).
     - "Create plan from scratch" → proceed with step 6.1 as normal, ignoring the existing plan.
   - **`VERIFY`** → enter verification mode directly (step 6.1 via the verify path). Display: "Profile 'fast': no fresh verifications — entering verify mode."



**If no plan file exists**, proceed with step 6.1 as normal.

## 6.1: Planning

Use the `EnterPlanMode` tool to enter Claude Code's plan mode.

**If entering from the "Verify plan" path in 6.0:** Start by reading the existing plan file. Then explore the current codebase to check if the plan's assumptions, file paths, and approach are still valid. Focus on identifying what changed since the plan was written. Update the plan if needed, or confirm it is still sound. Then — **do not `ExitPlanMode` yet** — run the shared **End-of-planning terminal step** at the bottom of this §6.1. It decides at runtime whether this task is risk-gated; when it is, re-run the Risk Evaluation Procedure even if the existing plan already has a `## Risk` section (re-check it against the possibly-changed plan and update it in place). Only after the terminal step completes, `ExitPlanMode`.

**After `ExitPlanMode` on the verify path (post-externalization, pre-commit):**

When the verify path is taken (either via the `"verify"` profile setting that returned `DECISION:VERIFY` or `ASK_STALE → Verify now`, or via the interactive "Verify plan" option), a fresh `plan_verified` entry must be appended to the external plan file. This is the signal future picks use to decide whether to re-verify.

Sequence (runs inside the **Save Plan to External File** section, after the externalize helper emits `EXTERNALIZED:` / `OVERWRITTEN:` but before the `./ait git add`):

1. Execute the **Model Self-Detection Sub-Procedure** (see `model-self-detection.md`) to obtain `agent_string` (e.g., `claudecode/opus4_6`).
1b. Set `detected_agent_string` = `agent_string` so downstream procedures (Step 7 Agent Attribution, Step 9b Satisfaction Feedback) can reuse the resolved value instead of re-detecting.
2. Run:
   ```bash
   ./.aitask-scripts/aitask_plan_verified.sh append <external_plan_path> "<agent_string>"
   ```
3. The append modifies the plan file in place. The subsequent `./ait git add aiplans/<plan_file>` and `./ait git commit` (per the Plan Externalization Procedure) include the new entry in the same commit automatically.

This step only fires on the verify path — NOT on "Create plan from scratch", "Use current plan", "Skip verification", or first-time plan creation.

**For child tasks:** Include context links to related files (in priority order):
- Parent task file: `aitasks/t<parent>_<name>.md`
- Archived sibling plan files (primary reference for completed siblings): `aiplans/archived/p<parent>/p<parent>_*_*.md` — these contain the most up-to-date and detailed implementation records including post-implementation feedback
- Archived sibling task files (fallback, only for siblings without an archived plan): `aitasks/archived/t<parent>/t<parent>_*_*.md`
- Pending sibling task files: `aitasks/t<parent>/t<parent>_*_*.md`
- Pending sibling plan files: `aiplans/p<parent>/p<parent>_*_*.md`

While in plan mode:

- Ask the user clarifying questions about the task requirements
- Explore the codebase to understand the relevant architecture
- **Folded Tasks Note:** If the task has a `folded_tasks` frontmatter field, the task description already contains all relevant content from the folded tasks (their content was incorporated at creation time by aitask-explore). There is no need to read the original folded task files during planning — they exist only as references for post-implementation cleanup (deletion in Step 9).
- **Ad-Hoc Fold Request:** If the task description contains a request to fold other tasks into this one (e.g., "fold t42 and t43 into this task", "merge t16_2 here", "incorporate t42") OR the user explicitly requests folding during the planning conversation, execute the **Ad-Hoc Fold Procedure** below before continuing with planning. Both standalone parent tasks (e.g., `42`) and child tasks (e.g., `16_2`) can be folded.

  **Ad-Hoc Fold Procedure:**

  1. **Parse the requested task IDs** from the description text or the user's message. Accept both parent IDs (plain number, e.g., `42`) and child IDs (`<parent>_<child>`, e.g., `16_2`).

  2. **Validate** — run the fold validator, excluding the current task:
     ```bash
     ./.aitask-scripts/aitask_fold_validate.sh --exclude-self <current_task_id> <id1> <id2> ...
     ```
     For each output line:
     - `VALID:<id>:<path>` — keep this task in the valid set.
     - `INVALID:<id>:<reason>` — warn "t\<id\>: \<reason\> — skipping" and exclude. `<reason>` values: `not_found`, `status_<status>`, `has_children`, `is_self`.

  3. **Confirm** — If no valid tasks remain, inform the user and continue planning without folding. Otherwise, present the list of valid tasks and use `AskUserQuestion`:
     - Question: "The following tasks will be folded into t\<current\>: \<list\>. Proceed?"
     - Header: "Fold"
     - Options: "Yes, fold them" / "No, skip folding"

  4. **Execute fold** (only if user confirmed):
     ```bash
     ./.aitask-scripts/aitask_fold_content.sh <current_task_file> <folded_file1> <folded_file2> ... \
       | ./.aitask-scripts/aitask_update.sh --batch <current_task_id> --desc-file -

     ./.aitask-scripts/aitask_fold_mark.sh --commit-mode fresh <current_task_id> <folded_id1> <folded_id2> ...
     ```
     Parse the `aitask_fold_mark.sh` output for a `COMMITTED:<hash>` line confirming the fold was committed. The marking script automatically handles transitive folds and removes folded child tasks from their parent's `children_to_implement`.

  5. **Resume planning** — Re-read the updated task file to pick up the merged content, then continue planning with the enriched description.
- **Cross-repo dispatch check (auto-fire with confirmation):** Read and
  follow the **Cross-Repo Planning Procedure** (see `planning-cross-repo.md`)
  with `current_task_id` = the current task ID and `trigger_source` = the
  task body. Trigger detection is metadata-only (it reads `xdeprepo` from the
  task frontmatter); the body is not scanned. The procedure is **read-only**
  — it designs a paired decomposition (nominally assigning each child to the
  current task or to a future cross-repo parent) and records it in the plan,
  but **creates no tasks** (creation runs in plan mode, which is read-only).
  If it returns `cross_repo_planned: true`, skip the rest of this Complexity
  Assessment branch (child-task batch creation, child-plan writing, the
  manual-verification sibling, and the child-task checkpoint), set
  `cross_repo_planned = true` in the workflow context, and proceed to **Save
  Plan to External File** for the local parent. The actual cross-repo parent
  and child creation runs after the plan is approved, at the start of Step 7
  (see `cross-repo-child-assignment.md`). If it returns `cross_repo_planned:
  false`, continue with the Complexity Assessment below.
- **Complexity Assessment:**
  - After initial exploration, assess implementation complexity
  - If the complexity appears HIGH for a parent task, use `AskUserQuestion`:
    - Question: "This task appears complex. Would you like to break it into child subtasks?"
    - Options: "Yes, create child tasks" / "No, implement as single task"
  - **If creating child tasks:**
    - Ask how many subtasks and get brief descriptions for each
    - For each child task, execute the **Batch Task Creation Procedure** (see `task-creation-batch.md`) with mode `child`, the parent task number, an appropriate name, and the child task description content
    - **IMPORTANT:** Each child task description MUST include detailed context (see Child Task Documentation Requirements below)
    - **IMPORTANT:** Revert the parent task status back to "Ready" since only the child task being worked on should be "Implementing":
      ```bash
      ./.aitask-scripts/aitask_update.sh --batch <parent_num> --status Ready --assigned-to ""
      ```
      The `aitask_ls.sh` script will automatically display the parent as "Has children" because it has pending `children_to_implement`. Do NOT manually set the parent status to "Blocked".
    - **IMPORTANT:** Release the parent task lock since only child tasks should be locked during child implementation:
      ```bash
      ./.aitask-scripts/aitask_lock.sh --unlock <parent_num> 2>/dev/null || true
      ```
      Parent task locking/unlocking should be left to the user via `ait board` or `ait lock`. Only child tasks should be automatically locked when picked for implementation.
    - **Write implementation plans for ALL child tasks** before proceeding:
      - For each child task created, write a plan file to `aiplans/p<parent>/p<parent>_<child>_<name>.md`
      - Use the child plan file naming and metadata header conventions from the **Save Plan to External File** section below
      - Each plan should leverage the codebase exploration already done during the parent planning phase
      - Plans do not need to go through `EnterPlanMode`/`ExitPlanMode` — write them directly as files since the overall parent plan was already approved
      - Commit all child plan files together (child task files were already committed by the Batch Task Creation Procedure):
        ```bash
        mkdir -p aiplans/p<parent>
        ./ait git add aiplans/p<parent>/
        ./ait git commit -m "ait: Add t<parent> child implementation plans"
        ```
    - **Manual verification sibling (post-child-creation):**
      After the child plans are committed, offer to add an aggregate manual-verification sibling that covers behavior only a human can validate (TUI flows, live agent launches, multi-screen navigation, etc.). Skip this step entirely if `<N>` (the number of children just created) is `1`.

      Use `AskUserQuestion`:
      - Question: "Do any of these children produce behavior that needs manual verification (TUI flows, live agent launches, on-disk artifact inspection, multi-screen navigation)?"
      - Header: "Manual verify"
      - Options:
        - "No, not needed" (description: "Skip — no aggregate verification sibling")
        - "Yes, add aggregate sibling covering all children (Recommended for TUI/UX-heavy work)" (description: "Create one manual-verification sibling that verifies every child task just created")
        - "Yes, but let me choose which children it verifies" (description: "Create a manual-verification sibling narrowed to a subset of the children")

      If "Yes, but let me choose": use a second `AskUserQuestion` with `multiSelect: true`, one option per child (label = child task filename, description = brief summary). The selected children form the `--verifies` list.

      If either "Yes" option is chosen:
      - Build a `<tmp_checklist>` file: for each selected child, read its plan file (`aiplans/p<parent>/p<parent>_<child>_<name>.md`) and extract bullet lines from its `## Verification` section (if present). Prefix each bullet with `[t<parent>_<child>] ` so the failure origin is visible at-a-glance. If a child's plan has no `## Verification` section, emit a single stub line: `TODO: define verification for t<parent>_<child>`.
      - Shell out to the seeder:
        ```bash
        ./.aitask-scripts/aitask_create_manual_verification.sh \
          --parent <parent_num> \
          --name manual_verification_<parent_slug> \
          --verifies <selected_child_ids_csv> \
          --items <tmp_checklist>
        ```
        where `<parent_slug>` is derived from the parent task's filename (e.g. `aitasks/t571_structured_brainstorming.md` → `structured_brainstorming`). `<selected_child_ids_csv>` lists the verified children by bare ID (`571_4,571_5`).
      - Parse the `MANUAL_VERIFICATION_CREATED:<new_id>:<path>` line and display the new task ID to the user. The seeder already commits the new task and its seeded checklist.
      - The new sibling becomes the last child of the parent; it is automatically added to `children_to_implement` by `aitask_create.sh --parent`.

      After this step, continue to the child task checkpoint below.
    - **Child task checkpoint (ALWAYS interactive — ignores `post_plan_action` profile setting):**
      Use `AskUserQuestion`:
      - Question: "Created <N> child tasks with implementation plans. How would you like to proceed?"
      - Header: "Children"
      - Options:
        - "Start first child" (description: "Continue to pick and implement the first child task")
        - "Stop here" (description: "All child tasks and plans are written — end this session and pick children later in fresh contexts")
      - **If "Start first child":** Restart the pick process with `/aitask-pick <parent>_1`
      - **If "Stop here":** Display: "Child tasks and plans written to `aiplans/p<parent>/`. Pick individual children later with `/aitask-pick <parent>_<N>`." Execute the **Satisfaction Feedback Procedure** (see `satisfaction-feedback.md`) with `skill_name` from the context variables. Then end the workflow.
- Create a detailed, step-by-step implementation plan. "Detailed" means:
  specific file paths, detailed implementation steps with exact changes
  needed in each file, code snippets for non-trivial modifications, and
  verification steps. Do not produce a high-level overview.
- Include a reference to **Step 9 (Post-Implementation)** in the plan for the cleanup, archival, and merge steps

#### End-of-planning terminal step (NON-SKIPPABLE — runs on EVERY plan path)

This is the shared terminus of **all** planning paths that reach `ExitPlanMode` — create-new, verify, and `ASK_STALE → Verify now`. It is **not** specific to the create-new narrative above. Whichever path you arrived by, first decide whether this task is **gated for risk evaluation**, then run the risk sub-steps below (when gated) **before** `ExitPlanMode`.

**Risk-gate check (runtime — replaces the old `risk_evaluation` profile toggle).** Compute this task's effective gate set. If `active_profile_filename` is set:

```bash
./.aitask-scripts/aitask_gate.sh effective-gates <task_id> --profile aitasks/metadata/profiles/<active_profile_filename>
```

Otherwise (no active profile — e.g. a manual / resume invocation), omit `--profile`:

```bash
./.aitask-scripts/aitask_gate.sh effective-gates <task_id>
```

If the output includes `risk_evaluated`, run **both** risk sub-steps below; otherwise **skip** them (no `## Risk` section is authored, and Step 7 writes no risk fields). The effective set = this task's own `gates:` field if present (even empty = opt-out), else the active profile's `default_gates` — so the planning-time producer here and the verify-time checker (the `risk_evaluated` gate at Step 9) **toggle together**. An existing `## Risk` section does not exempt the verify path — when risk-gated, re-run the evaluation and update the section in place.

- **Risk evaluation (end of planning):** Now that the plan is designed (or re-verified), read and follow the **Risk Evaluation Procedure** (see `risk-evaluation.md`). It assesses the two risk dimensions (code-health and goal-achievement) **separately**, assigns a level to each, and appends (or updates) a `## Risk` section in the plan. Thread `risk_level_code_health`, `risk_level_goal_achievement`, and `risk_mitigations_planned` into the workflow context — `SKILL.md` Step 7 writes the two fields post-approval (plan mode is read-only).
- **Risk-mitigation design (end of planning):** Immediately after the risk evaluation, read and follow **Part 1 (Design-in-planning)** of the **Risk-Mitigation Follow-up Procedure** (see `risk-mitigation-followup.md`). It proposes before/after mitigation tasks for the identified risks (propose-and-confirm), records the confirmed ones into the plan's `## Risk` section, and threads `risk_mitigations_confirmed`. It creates nothing (plan mode is read-only) — `SKILL.md` Step 7 creates the "before" mitigations and Step 8d creates the "after" ones, post-approval.
- Use `ExitPlanMode` when ready for user approval

## Child Task Documentation Requirements

When creating child tasks, each task file MUST include detailed context that enables independent execution in a fresh Claude Code context. The assumption is that child tasks will NOT be executed in the current context, so ALL information currently available should be stored in the child task definition.

**Required sections for each child task:**

1. **Context Section**
   - Why this task is needed
   - How it fits into the parent task's goal
   - Relevant background from the exploration phase that led to this specific child task

2. **Key Files to Modify**
   - Full paths to files that need changes
   - Brief description of what changes are needed in each file

3. **Reference Files for Patterns**
   - Existing files that demonstrate similar patterns to follow
   - Specific line numbers or function names when helpful

4. **Implementation Plan**
   - Step-by-step instructions
   - Code snippets where helpful
   - Dependencies between steps

5. **Verification Steps**
   - How to build/compile
   - How to test the changes
   - Expected outcomes

## Save Plan to External File

**If running in Claude Code,** execute the **Plan Externalization Procedure** (see `plan-externalization.md`) immediately after `ExitPlanMode` and before proceeding to the Checkpoint. Claude Code's `EnterPlanMode` writes the plan to an internal file at `~/.claude/plans/<random>.md` and `ExitPlanMode` does **not** copy it to `aiplans/` automatically — the procedure file details the externalize helper, output parsing, and error handling. Other code agents write plans directly to `aiplans/` and skip this step.

**Verify-path append reminder:** If you arrived here via the verify path (profile `"verify"` resolved to `DECISION:VERIFY` / `ASK_STALE → Verify now`, or the interactive "Verify plan" option), after the externalize helper emits `EXTERNALIZED:` / `OVERWRITTEN:` and **before** you run `./ait git add aiplans/<plan_file>`, run the plan-verified append step described in §6.1 ("After `ExitPlanMode` on the verify path"). The append modifies the plan file in place so the subsequent commit picks it up in the same commit.

If the externalize helper reports `NOT_FOUND:no_internal_files` / `no_internal_dir`, fall back to writing the plan manually with the Write tool using the naming convention and metadata header below. These subsections remain the source of truth for the plan file format regardless of how it is created.

**File naming convention:**

For parent tasks:
- Location: `aiplans/`
- Filename: Replace `t` prefix with `p`
- Example: `t16_implement_auth.md` → `aiplans/p16_implement_auth.md`

For child tasks:
- Location: `aiplans/p<parent>/`
- Filename: Replace `t` prefix with `p`
- Example: `t16_2_add_login.md` → `aiplans/p16/p16_2_add_login.md`

**Required metadata header for parent tasks:**
```markdown
---
Task: t16_implement_auth.md
Worktree: aiwork/t16_implement_auth
Branch: aitask/t16_implement_auth
Base branch: main
---
```

**Required metadata header for child tasks:**
```markdown
---
Task: t16_2_add_login.md
Parent Task: aitasks/t16_implement_auth.md
Sibling Tasks: aitasks/t16/t16_1_*.md, aitasks/t16/t16_3_*.md
Archived Sibling Plans: aiplans/archived/p16/p16_*_*.md
Worktree: aiwork/t16_2_add_login
Branch: aitask/t16_2_add_login
Base branch: main
---
```

**Risk-section guard (NON-SKIPPABLE when risk-gated — verifies the §6.1 terminal step ran):** This guard applies only when this task is **gated for risk evaluation** (the §6.1 risk-gate check found `risk_evaluated` in the effective gate set). If it is *not* risk-gated, skip the guard. Also skip if `cross_repo_planned` is true (a cross-repo parent has no single-task `## Risk` section). Otherwise, before proceeding to the Checkpoint, confirm the externalized plan file contains a `## Risk` section:

```bash
grep -q '^## Risk' aiplans/<plan_file> && echo "RISK_OK" || echo "RISK_MISSING"
```

- `RISK_OK` → the end-of-planning Risk Evaluation ran; proceed to the Checkpoint.
- `RISK_MISSING` → the §6.1 End-of-planning terminal step was skipped on this risk-gated path. Do **not** proceed. Re-enter plan mode (`EnterPlanMode`), run the **Risk Evaluation Procedure** and the **Risk-Mitigation design** step now, `ExitPlanMode`, and re-run **Save Plan to External File** so the `## Risk` section is persisted.

## Checkpoint (after plan is saved)

**Determine effective post-plan action:**


Profile 'fast' configures the post-plan action.

For **child tasks** (when `is_child` is true), the effective action is `post_plan_action_for_child: ask`. For **parent tasks**, the effective action is `post_plan_action: ask`. Resolve which one applies based on `is_child`.


Then act on the effective value:

- If the effective action is `"start_implementation"`: Display "Profile 'fast': proceeding to implementation". Execute the **Remote Drift Check Procedure** (see `remote-drift-check.md`) with `base_branch`, `plan_file`, and `active_profile` from context. If the procedure ends the workflow ("Stop and re-verify plan" or "Abort task"), do NOT proceed to Step 7. Otherwise, skip the interactive AskUserQuestion below and proceed to Step 7.
- If the effective action is `"ask"`: show the interactive checkpoint below.



Otherwise, use `AskUserQuestion`:
- Question: "Plan saved to `<plan_path>`. How would you like to proceed?"
- Header: "Proceed"
- Options:
  - "Start implementation" (description: "Begin implementing the approved plan")
  - "Revise plan" (description: "Show the full plan, re-enter plan mode, and request specific changes")
  - "Approve and stop here" (description: "Approve the plan, release the lock, revert task to Ready, and end the workflow — pick it up later in a fresh context")
  - "Abort task" (description: "Stop and revert task status")

If "Start implementation": Execute the **Remote Drift Check Procedure** (see `remote-drift-check.md`) with `base_branch`, `plan_file`, and `active_profile` from context. If the procedure returns ("Continue anyway"), proceed to Step 7. If it ends the workflow ("Stop and re-verify plan" or "Abort task"), stop.

If "Revise plan":

1. Re-enter plan mode with `EnterPlanMode`.
2. **Show the current plan in full.** Read the saved plan file (`aiplans/<plan_file>`) and present its complete content to the user. Do NOT condense it to "main points" or ask which section to change via a fixed multiple-choice list — the user needs the actual plan visible to decide what to revise.
3. **Find out what to change.** If the user already named a specific modification (in their message or via the `AskUserQuestion` "Other" free-text option), apply it directly. Otherwise, ask the user what they would like to change and accept a free-text answer.
4. Edit the plan in plan mode to incorporate the requested changes.
5. `ExitPlanMode`, then re-run **Save Plan to External File** to persist the revised plan, and return to **this Checkpoint** to re-present the approval prompt with the revised plan shown. Repeat the revise loop until the user selects "Start implementation" or "Approve and stop here".

Do NOT return to the beginning of Step 6 — that re-triggers the 6.0 existing-plan preference check and, on profiles with `plan_preference: use_current`, skips plan mode entirely and bounces straight back here without ever showing or revising the plan.

If "Approve and stop here":

Execute the **Gate Recording Procedure** (see `gate-recording.md`) with `task_id`, `gate_name=plan_approved`, `status=pass`, `fields="type=human note=deferred"` (the plan is approved; implementation is deferred to a later session — this is the resume signal).

1. Ensure the plan file is committed (idempotent — may be a no-op if the Plan Externalization Procedure already committed it):
   ```bash
   ./ait git add aiplans/<plan_file>
   ./ait git commit -m "ait: Add plan for t<task_id>" 2>/dev/null || true
   ```
2. Release the task lock via the **Lock Release Procedure** (see `lock-release.md`).
3. Revert the task status to `Ready` and clear `assigned_to`:
   ```bash
   ./.aitask-scripts/aitask_update.sh --batch <task_num> --status Ready --assigned-to ""
   ```
4. Commit the status revert and push:
   ```bash
   ./ait git add aitasks/
   ./ait git commit -m "ait: Revert t<task_num> to Ready after plan approval" 2>/dev/null || true
   ./ait git push
   ```
5. Display: "Plan approved and committed. Task t\<task_num\> reverted to Ready — pick it up later with `/aitask-pick <task_num>` in a fresh context." End the workflow (do **NOT** proceed to Step 7). The "Approve and stop here" option is always available (not profile-gated); it replaces the infeasible context-usage auto-detection by letting the user make the call based on their own HUD.

If "Abort": Execute the **Task Abort Procedure** (see `task-abort.md`).

