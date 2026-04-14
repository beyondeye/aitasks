---
priority: medium
effort: medium
depends: [t547_2]
issue_type: feature
status: Implementing
labels: [task_workflow, aitask_pick]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-14 16:12
updated_at: 2026-04-14 17:36
---

## Context

Parent task t547 wires up plan verification tracking so the task-workflow can skip re-verification when enough fresh verifications already exist, and lets the user "Approve and stop here" after verification to break context-usage pressure.

This is the final integration child — it consumes the helper script from Child 1 and the profile keys from Child 2 and updates the skill markdown (`planning.md`) to use them.

**Depends on:** Child 1 (helper script `aitask_plan_verified.sh`) and Child 2 (profile keys `plan_verification_required`, `plan_verification_stale_after_hours`).

## Key Files to Modify

- `.claude/skills/task-workflow/planning.md` — three edits:
  - §6.0 Check for Existing Plan → new verify decision tree calling `aitask_plan_verified.sh decide`
  - §6.1 Planning → append verified entry after ExitPlanMode on the verify path
  - §6 Checkpoint (end of the file) → add "Approve and stop here" option with cleanup sequence

**NOT modified** (per CLAUDE.md — claude code is source of truth, separate aitasks for gemini/codex/opencode):
- `.gemini/skills/`, `.agents/skills/`, `.opencode/skills/`

## Reference Files for Patterns

- `.claude/skills/task-workflow/planning.md` — the file to modify. Study §6.0 (current verify handling) and the Checkpoint section (existing options) before editing.
- `.claude/skills/task-workflow/task-abort.md` — reference for lock release + status revert cleanup sequence. The "Approve and stop here" flow uses similar primitives (`aitask_lock.sh --unlock`, `aitask_update.sh --batch --status Ready`) but KEEPS the plan file.
- `.claude/skills/task-workflow/model-self-detection.md` — procedure to get the current agent string (e.g., `claudecode/opus4_6`). Call before appending a plan_verified entry.
- `aiplans/p547_plan_verify_on_off_in_task_workflow.md` — parent plan with the full design, profile key names, helper output format, and decision tree. Canonical reference.
- `aiplans/p547/p547_1_plan_verified_helper.md` — Child 1's plan file (for exact helper interface)
- `aiplans/p547/p547_2_profile_verification_keys.md` — Child 2's plan file (for exact profile key names)

## Implementation Plan

### Step 1: Update §6.0 verify decision tree

Replace the current verify path in §6.0 (the section that handles `plan_preference: verify`) with a new flow that:

1. Reads `plan_verification_required` from the active profile (default `1`)
2. Reads `plan_verification_stale_after_hours` from the active profile (default `24`)
3. Calls: `./.aitask-scripts/aitask_plan_verified.sh decide <plan_file> <required> <stale_after_hours>`
4. Parses the 8-line structured output (TOTAL, FRESH, STALE, LAST, REQUIRED, STALE_AFTER_HOURS, DISPLAY, DECISION)
5. Prints the DISPLAY line to the user
6. Branches on DECISION:
   - `SKIP` → jump to Checkpoint (behaves like `use_current`)
   - `ASK_STALE` → `AskUserQuestion` with 3 options (Verify now / Skip verification / Create plan from scratch), handled as in the current manual interactive path
   - `VERIFY` → enter verification mode directly

The existing non-profile interactive path (when no profile is active) should be preserved — the decide helper is only invoked when `plan_preference` resolves to `verify` via a profile.

### Step 2: Update §6.1 to append verified entry on exit

After the "Verify plan" path completes and `ExitPlanMode` is called (and before proceeding to externalization), add an instruction:

1. Execute the **Model Self-Detection Sub-Procedure** (`model-self-detection.md`) to get the current agent string into a variable (e.g., `agent_string`)
2. Run: `./.aitask-scripts/aitask_plan_verified.sh append <plan_file> "<agent_string>"`

Important: this append must happen AFTER the plan is externalized to `aiplans/` (so we're appending to the external file, not the internal one). The procedure is:
- ExitPlanMode
- Run Plan Externalization Procedure (`--force`)
- Now the plan is at `aiplans/p<...>.md`
- Run Model Self-Detection
- Call the append helper on the external file
- Commit the plan (the append is included in the same commit)

Make sure the instruction only fires on the "Verify plan" path, not on "Create plan from scratch" or first-time plan creation.

### Step 3: Update §6 Checkpoint with "Approve and stop here"

Locate the `post_plan_action` Checkpoint `AskUserQuestion` at the end of §6. Add a new 3rd option (between "Revise plan" and "Abort"):

- Label: "Approve and stop here"
- Description: "Approve the plan, commit it, release the lock, revert task to Ready, and end the workflow. Pick it up later in a fresh context."

Handle the new option with this cleanup sequence:

```bash
# 1. Commit the plan file (if not already committed)
./ait git add aiplans/<plan_file>
./ait git commit -m "ait: Add plan for t<task_id>" || true  # may be a no-op if already committed
# 2. Release task lock
./.aitask-scripts/aitask_lock.sh --unlock <task_num>
# 3. Revert task status to Ready and clear assigned_to
./.aitask-scripts/aitask_update.sh --batch <task_num> --status Ready --assigned-to ""
# 4. Push
./ait git push
```

Then display: "Plan approved and committed. Task reverted to Ready — pick it up later with `/aitask-pick <N>` in a fresh context." and end the workflow (skip Step 7 entirely).

The option is ALWAYS available (not profile-gated), because this replaces the infeasible context-usage trigger.

### Step 4: Check cross-references

- Search `.claude/skills/task-workflow/planning.md` for any references to `plan_preference` that might need updating to mention the new keys. Usually only §6.0 and profiles.md reference them.
- Verify `.claude/skills/task-workflow/SKILL.md` still references planning.md correctly.
- Grep for `plan_verified` across `.claude/skills/task-workflow/` to verify there are no stale mentions conflicting with the new format.

## Verification Steps

1. Read through planning.md end-to-end as a human would, looking for inconsistencies or broken cross-references
2. Verify the helper invocation in §6.0 exactly matches the interface from Child 1 (`decide <plan_file> <required> <stale_after_hours>`)
3. Verify the profile key names in §6.0 exactly match Child 2 (`plan_verification_required`, `plan_verification_stale_after_hours`)
4. Verify the append helper in §6.1 uses the correct agent string format (the one from model-self-detection.md)
5. Verify the "Approve and stop here" cleanup sequence uses the same lock/status primitives as `task-abort.md` (but keeps the plan file)
6. Simulate a dry-run: mentally walk through fast profile → child task with existing plan → decide returns SKIP → checkpoint → should work without hitting the verify path again
7. Simulate: fast profile → child task with existing plan that has a stale entry → decide returns ASK_STALE → user picks "Verify now" → verify runs → append new entry → checkpoint now shows 4 options including "Approve and stop here" → user picks that → cleanup runs → task is Ready → end

## Notes for sibling tasks

- This is the **last** child in the sequence — after this, the parent task t547 becomes eligible for parent archival
- No new tests required — the workflow changes are in markdown; Child 1's tests cover the helper
- After merging, suggest a follow-up aitask to mirror the changes to `.gemini/skills/`, `.agents/skills/`, `.opencode/skills/` per CLAUDE.md convention (the parent plan notes this intentionally)
