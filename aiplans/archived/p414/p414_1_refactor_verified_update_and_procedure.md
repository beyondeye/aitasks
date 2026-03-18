---
Task: t414_1_refactor_verified_update_and_procedure.md
Parent Task: aitasks/t414_simplify_satisfaction_feedback_verified_update.md
Sibling Tasks: aitasks/t414/t414_2_integrate_in_aitask_changelog.md, aitasks/t414/t414_3_update_all_affected_skills.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

## Context

The Satisfaction Feedback Procedure requires agents to follow a 3-file chain (satisfaction-feedback.md → model-self-detection.md → aitask_resolve_detected_agent.sh → aitask_verified_update.sh). In context-heavy skills, agents fail to follow the chain and hallucinate script names. This task consolidates the chain into a single script call with `--agent`/`--cli-id` flags.

## Plan

### Step 1: Add --agent/--cli-id flags to aitask_verified_update.sh

**File:** `.aitask-scripts/aitask_verified_update.sh`

Add two new variables at the top (near line 13-16):
```bash
CLI_AGENT=""
CLI_ID=""
```

Add cases to `parse_args()` (near line 108-141):
```bash
--agent)
    [[ $# -lt 2 ]] && die "--agent requires a value"
    CLI_AGENT="$2"
    shift 2
    ;;
--cli-id)
    [[ $# -lt 2 ]] && die "--cli-id requires a value"
    CLI_ID="$2"
    shift 2
    ;;
```

Add validation after the existing required-field checks. Replace the standalone `--agent-string` required check and `parse_agent_string` call with resolution logic that handles both paths.

Update `show_help()` to document the new flags.

### Step 2: Simplify satisfaction-feedback.md

**File:** `.claude/skills/task-workflow/satisfaction-feedback.md`

Replace step 2 (model-self-detection reference) with inlined self-detection instructions. Update step 4 to use `--agent`/`--cli-id` flags instead of `--agent-string`.

### Step 3: Create test file for the new flags

**File:** `tests/test_verified_update_flags.sh` (NEW)

Test cases: --agent/--cli-id resolves, backward compat, mutual exclusion, missing args.

## Verification

1. `--agent claudecode --cli-id claude-opus-4-6` resolves and updates
2. `--agent-string claudecode/opus4_6` backward compat works
3. Both flags together errors
4. shellcheck passes
5. Tests pass
6. satisfaction-feedback.md no longer references model-self-detection.md

## Final Implementation Notes

- **Actual work done:** All 3 steps implemented as planned. Added `--agent`/`--cli-id` flags to `aitask_verified_update.sh`, simplified `satisfaction-feedback.md` to inline self-detection and use the new flags, created test file with 6 test cases.
- **Deviations from plan:** None — implementation followed plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Used `local` keyword for `resolve_output` variable inside `parse_args()` since `parse_args` is called from `main()` and bash supports local in nested function calls. The `AGENT_STRING` global is set by the resolution logic so downstream code (which uses `AGENT_STRING`) works without changes.
- **Notes for sibling tasks:** The `--agent-string` flag still works for backward compatibility, so t414_2 (changelog verification) should confirm the new `--agent`/`--cli-id` path works end-to-end. t414_3 should audit all skills for any custom/inline satisfaction feedback code that bypasses `satisfaction-feedback.md`. The `model-self-detection.md` file was NOT modified — it's still used by `agent-attribution.md`.
