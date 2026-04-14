---
Task: t547_3_workflow_verify_integration.md
Parent Task: aitasks/t547_plan_verify_on_off_in_task_workflow.md
Sibling Tasks: aitasks/t547/t547_*_*.md
Archived Sibling Plans: aiplans/archived/p547/p547_*_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_6 @ 2026-04-14 17:35
---

# Context

Final integration child for parent t547. Consumes the helper script from Child 1 (`aitask_plan_verified.sh`) and the profile keys from Child 2 (`plan_verification_required`, `plan_verification_stale_after_hours`) and wires them into the task-workflow skill markdown (`planning.md`).

**Depends on:** Child 1 AND Child 2 (both must be archived before this child can start).

This is a documentation-only change — all behavioral logic lives in Child 1's helper script. The skill markdown just calls the helper and branches on the `DECISION:` line.

# Files to modify

| File | Change |
|---|---|
| `.claude/skills/task-workflow/planning.md` §6.0 | New verify decision tree using `decide` helper |
| `.claude/skills/task-workflow/planning.md` §6.1 | Append plan_verified entry after verify-path ExitPlanMode |
| `.claude/skills/task-workflow/planning.md` Checkpoint section | Add "Approve and stop here" option + cleanup sequence |

**NOT modified** (per CLAUDE.md — claude code is source of truth):
- `.gemini/skills/`, `.agents/skills/`, `.opencode/skills/`

# Edit 1 — §6.0 verify decision tree

Locate the existing §6.0 "Check for Existing Plan" section. The current verify path looks like:

```markdown
- If `"verify"`: Enter verification mode (step 6.1). Display: "Profile '\<name\>': verifying existing plan"
```

Replace with a new subsection that delegates to the helper. Insert immediately after the "If a plan file exists" path is taken:

```markdown
**Verify path (profile-driven):**

When the resolved `plan_preference` is `"verify"`, do NOT immediately enter verify mode. Instead, delegate the decision to the helper script:

1. Read `plan_verification_required` from the active profile (default `1` if key absent).
2. Read `plan_verification_stale_after_hours` from the active profile (default `24` if key absent).
3. Run:
   ```bash
   ./.aitask-scripts/aitask_plan_verified.sh decide <plan_file> <required> <stale_after_hours>
   ```
4. Parse the structured output (8 lines, `KEY:value` format):
   - `TOTAL:<N>` / `FRESH:<M>` / `STALE:<K>` / `LAST:<agent @ timestamp>` (or `LAST:NONE`)
   - `REQUIRED:<R>` / `STALE_AFTER_HOURS:<H>`
   - `DISPLAY:<human-readable summary>` — print this line to the user verbatim
   - `DECISION:<SKIP|ASK_STALE|VERIFY>`
5. Branch on `DECISION:`:
   - **`SKIP`** → jump to the Checkpoint at the end of Step 6 (same as `use_current`). Display confirmation: "Profile '\<name\>': skipping verification (sufficient fresh verifications exist)."
   - **`ASK_STALE`** → use `AskUserQuestion`:
     - Question: (the `DISPLAY:` line) + " How would you like to proceed?"
     - Header: "Stale plan"
     - Options:
       - "Verify now" (description: "Enter verify mode; a fresh entry will be appended on exit")
       - "Skip verification" (description: "Use the existing plan as-is, without refreshing")
       - "Create plan from scratch" (description: "Discard the existing plan and start fresh")
     - Handle each selection as in the interactive (non-profile) path below.
   - **`VERIFY`** → enter verification mode directly (proceed into step 6.1 with the verify-path framing). Display: "Profile '\<name\>': no prior verifications found — entering verify mode."
```

The interactive (no-profile) path below should remain unchanged — users without a profile continue to see the 3-option `AskUserQuestion` as before.

# Edit 2 — §6.1 append plan_verified entry

Locate the paragraph in §6.1 that reads:

> **If entering from the "Verify plan" path in 6.0:** Start by reading the existing plan file. Then explore the current codebase to check if the plan's assumptions, file paths, and approach are still valid. Focus on identifying what changed since the plan was written. Update the plan if needed, or confirm it is still sound and exit plan mode.

Append a new paragraph immediately after the existing one:

```markdown
**After `ExitPlanMode` on the verify path (post-externalization):**

After the plan has been externalized to `aiplans/` (via the Plan Externalization Procedure) but before the plan file is committed:

1. Execute the **Model Self-Detection Sub-Procedure** (`model-self-detection.md`) to get the current agent string (e.g., `claudecode/opus4_6`).
2. Run:
   ```bash
   ./.aitask-scripts/aitask_plan_verified.sh append <external_plan_path> "<agent_string>"
   ```
3. The appended entry (with current timestamp) is now part of the plan file. The subsequent `./ait git commit` in the Plan Externalization Procedure's "Commit the externalized plan" section includes the new entry automatically.

This only fires on the "Verify plan" path — NOT on "Create plan from scratch", "Use current plan", or first-time plan creation.
```

# Edit 3 — §6 Checkpoint "Approve and stop here"

Locate the Checkpoint `AskUserQuestion` at the end of §6. Current options:

```markdown
Otherwise, use `AskUserQuestion`:
- Question: "Plan saved to `<plan_path>`. How would you like to proceed?"
- Header: "Proceed"
- Options:
  - "Start implementation" (description: "Begin implementing the approved plan")
  - "Revise plan" (description: "Re-enter plan mode to make changes")
  - "Abort task" (description: "Stop and revert task status")
```

Update to add a 3rd option (between "Revise plan" and "Abort task"):

```markdown
Otherwise, use `AskUserQuestion`:
- Question: "Plan saved to `<plan_path>`. How would you like to proceed?"
- Header: "Proceed"
- Options:
  - "Start implementation" (description: "Begin implementing the approved plan")
  - "Revise plan" (description: "Re-enter plan mode to make changes")
  - "Approve and stop here" (description: "Approve the plan, release the lock, revert task to Ready, and end the workflow — pick it up later in a fresh context")
  - "Abort task" (description: "Stop and revert task status")

If "Revise plan": Return to the beginning of Step 6.
If "Approve and stop here":
1. Ensure the plan file is committed (idempotent — may be a no-op if already committed by the Plan Externalization Procedure):
   ```bash
   ./ait git add aiplans/<plan_file>
   ./ait git commit -m "ait: Add plan for t<task_id>" 2>/dev/null || true
   ```
2. Release the task lock:
   ```bash
   ./.aitask-scripts/aitask_lock.sh --unlock <task_num>
   ```
3. Revert status to Ready and clear `assigned_to`:
   ```bash
   ./.aitask-scripts/aitask_update.sh --batch <task_num> --status Ready --assigned-to ""
   ```
4. Push:
   ```bash
   ./ait git push
   ```
5. Display: "Plan approved and committed. Task reverted to Ready — pick it up later with `/aitask-pick <task_num>` in a fresh context." End the workflow (do NOT proceed to Step 7).

If "Abort": Execute the **Task Abort Procedure** (see `task-abort.md`).
```

The "Approve and stop here" option is **always** available, not profile-gated. It replaces the (infeasible) context-usage auto-detection the user originally proposed — the user makes the call based on their HUD.

The `post_plan_action: start_implementation` profile setting still takes effect normally (silently proceeds to Step 7 without showing the checkpoint at all). "Approve and stop here" is only surfaced when the checkpoint is shown — i.e., when `post_plan_action` is `"ask"` or unset. This is correct: profiles that opt into auto-implementation have explicitly chosen not to see the checkpoint.

# Edit 4 — cross-reference check

After the three edits above, do a consistency pass:

1. `grep -n 'plan_preference\|plan_verified\|plan_verification' .claude/skills/task-workflow/planning.md` — verify no stale references or typos
2. `grep -rn 'aitask_plan_verified' .claude/skills/task-workflow/` — verify the helper is referenced only from planning.md (not from SKILL.md or other procedure files unless they were specifically meant to update)
3. Verify §6.0's branching logic doesn't conflict with the Plan Externalization Procedure (`plan-externalization.md`) — the externalize call happens AFTER ExitPlanMode, regardless of whether verify ran
4. Verify the profile key names match Child 2 exactly: `plan_verification_required`, `plan_verification_stale_after_hours`
5. Verify the helper command names match Child 1 exactly: `decide`, `append`, `read`

# Verification

1. **Read-through:** Read planning.md end-to-end as a reviewer. The verify path should flow cleanly: profile → decide → display → branch → (verify or skip) → externalize → append → commit → checkpoint (with 4 options).
2. **Dry-run mental simulation 1:** Fast profile, child task, existing plan with 1 fresh verification entry, `required=1`:
   - `decide` returns `DECISION:SKIP`
   - Workflow displays "Plan has 1 fresh verification…"
   - Jumps to checkpoint → user sees 4 options → picks "Start implementation" (fast profile has `post_plan_action_for_child: ask`) → Step 7
3. **Dry-run mental simulation 2:** Fast profile, child task, plan with 1 stale verification entry:
   - `decide` returns `DECISION:ASK_STALE`
   - Workflow displays stale count and asks
   - User picks "Verify now" → enters verify plan mode → ExitPlanMode → externalize → append new entry → commit → checkpoint
   - User picks "Approve and stop here" → cleanup runs → task Ready → end
   - Next pick: `decide` sees the new entry (fresh) → `DECISION:SKIP` → straight to checkpoint
4. **Dry-run mental simulation 3:** No profile, plan exists:
   - Interactive `AskUserQuestion` (unchanged) shows 3 options — the `decide` helper is NOT invoked in the no-profile path
5. **Cross-ref grep:** `grep -n 'aitask_plan_verified\|plan_verification_' .claude/skills/task-workflow/planning.md` — every reference aligns with Child 1/Child 2 names

# Notes for future work

- After this child is archived, the parent task t547 will auto-archive (via `aitask_archive.sh`'s `PARENT_ARCHIVED:` output)
- Create follow-up aitasks to mirror the changes to `.gemini/skills/`, `.agents/skills/`, `.opencode/skills/` — the parent plan already flags this as expected
- The helper tests (Child 1) cover the decision logic; no new integration tests are needed for this child since it's markdown-only
