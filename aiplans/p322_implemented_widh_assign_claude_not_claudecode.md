---
Task: t322_implemented_widh_assign_claude_not_claudecode.md
Worktree: (none - working on current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Fix agent attribution and child task checkpoint skip (t322)

## Context

Two bugs were observed during t319_1 implementation:

1. **Agent attribution used `claude/opus4_6` instead of `claudecode/opus4_6`** — The Agent Attribution Procedure in `procedures.md` correctly lists `claudecode` as the agent identifier, but the model misidentified itself as `claude`. The instructions need to be more explicit/reinforced.

2. **Child task checkpoint was skipped with fast profile** — The fast profile has `post_plan_action: start_implementation` which caused the model to skip the checkpoint after verifying a child task plan, despite `planning.md` line 175 explicitly stating the checkpoint should ALWAYS be interactive for verified child tasks. The user proposes adding a `post_plan_action_for_child` profile key to eliminate the conflicting instructions.

## Changes

### 1. Add `post_plan_action_for_child` profile key

**Files to modify:**
- `aitasks/metadata/profiles/fast.yaml` — Add `post_plan_action_for_child: ask`
- `.claude/skills/task-workflow/profiles.md` — Add key to schema table
- `.claude/skills/task-workflow/planning.md` — Refactor checkpoint logic to use the new key instead of the special override rule

**Logic change in `planning.md` Checkpoint section:**

Current (conflicting):
- Override rule: "If child task AND plan was verified, checkpoint is ALWAYS interactive — ignore `post_plan_action`"
- Profile check: If `post_plan_action` is `start_implementation`, skip checkpoint

New (consolidated):
- Determine effective `post_plan_action`: if `is_child` and profile has `post_plan_action_for_child`, use that value; otherwise use `post_plan_action`
- If effective value is `"start_implementation"`: skip checkpoint
- If effective value is `"ask"` or not set: show interactive AskUserQuestion
- Remove the separate override rule — it's now encoded in the profile key `post_plan_action_for_child: ask`

### 2. Strengthen agent attribution instructions

**File to modify:**
- `.claude/skills/task-workflow/procedures.md` — Add emphasis that the agent name MUST be one of the exact strings listed: `claudecode`, `geminicli`, `codex`, `opencode`. Not `claude`, not `gemini`, etc.

### 3. Remote profile — no change needed

`remote.yaml` already has `post_plan_action: start_implementation` and no child-specific setting. Since remote profile is fully autonomous, omitting `post_plan_action_for_child` means it falls back to `post_plan_action` (start_implementation), which is correct.

## Verification

1. Read the updated `planning.md` checkpoint section and verify the logic is clear
2. Read the updated `profiles.md` schema and verify the new key is documented
3. Read the updated `fast.yaml` and verify it has `post_plan_action_for_child: ask`
4. Read the updated `procedures.md` and verify the agent attribution emphasis

## Final Implementation Notes
- **Actual work done:** All planned changes implemented as described. Added `post_plan_action_for_child` profile key, refactored checkpoint logic, strengthened agent attribution instructions.
- **Deviations from plan:** None. Implementation matched the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Added `"ask"` as an explicit documented value for `post_plan_action` (previously only `"start_implementation"` was documented, with omission being the implicit "ask"). This makes the `post_plan_action_for_child: ask` setting self-documenting.
