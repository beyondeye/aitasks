---
Task: t432_avoid_duplicate_query_of_agent.md
Worktree: (none - current branch)
Branch: (current)
Base branch: main
---

# Plan: Avoid Duplicate Agent/Model Detection

## Context

The task-workflow runs agent/model detection twice per task:
1. **Step 7 (Agent Attribution)** — calls Model Self-Detection → gets `agent_string` → writes to `implemented_with` frontmatter
2. **Step 9b (Satisfaction Feedback)** — independently detects agent/model in its "Identify yourself" step → calls `aitask_verified_update.sh --agent --cli-id`

The `aitask_verified_update.sh` script already supports `--agent-string <agent/model>` as an alternative to `--agent + --cli-id`. So if the already-resolved agent string from Agent Attribution is available, Satisfaction Feedback can use it directly — skipping both the self-detection AND the script-internal resolution.

The same pattern applies to `aitask-wrap` (calls Agent Attribution in Step 4a, then Satisfaction Feedback in Step 6).

## Changes

### 1. Add `detected_agent_string` context variable (`SKILL.md`)

Add to the context variables table:

| `detected_agent_string` | string/null | Agent string from Agent Attribution (e.g., `claudecode/opus4_6`). Set by Agent Attribution, consumed by Satisfaction Feedback to skip re-detection. Initialized to `null`. |

### 2. Update Agent Attribution Procedure (`agent-attribution.md`)

After step 2 (write to frontmatter), add:

> 3. **Store for reuse:** Set `detected_agent_string` to the resolved `agent_string` value. This allows downstream procedures (e.g., Satisfaction Feedback) to skip re-detection.

### 3. Update Satisfaction Feedback Procedure (`satisfaction-feedback.md`)

Add a new input parameter and modify step 2:

**Input:** Add `detected_agent_string` (string, optional) — If provided (from Agent Attribution), skip self-detection and use directly.

**Step 2 changes:**
- Add at top of step 2: "If `detected_agent_string` is available (non-null, non-empty), parse agent name from the `<agent>/<model>` format and skip to step 3. Use `--agent-string` in the `aitask_verified_update.sh` call instead of `--agent + --cli-id`."
- Keep existing self-detection as fallback for standalone callers (aitask-explore, aitask-explain, etc.)

**Step 4 changes:**
- Add conditional: if using `detected_agent_string`, call with `--agent-string`:
  ```bash
  ./.aitask-scripts/aitask_verified_update.sh --agent-string "<detected_agent_string>" --skill "<skill_name>" --score <rating> --silent
  ```
- Otherwise use existing `--agent + --cli-id` call

### 4. Update callers that have both procedures

**`SKILL.md` Step 9b** — pass `detected_agent_string` context variable when calling Satisfaction Feedback.

**`aitask-wrap/SKILL.md`** — after Agent Attribution (Step 4a), store the agent string; pass it when calling Satisfaction Feedback (Step 6).

No changes needed for standalone skills (aitask-explore, aitask-explain, etc.) — they don't run Agent Attribution, so `detected_agent_string` will be null and they'll fall back to self-detection.

## Files to modify

1. `.claude/skills/task-workflow/SKILL.md` — context variables table + Step 9b wording
2. `.claude/skills/task-workflow/agent-attribution.md` — add step 3 to store result
3. `.claude/skills/task-workflow/satisfaction-feedback.md` — add input param, conditional in steps 2 and 4
4. `.claude/skills/aitask-wrap/SKILL.md` — store agent string after attribution, pass to feedback

## Verification

- Read all modified files to confirm instructions are clear and consistent
- Run `shellcheck .aitask-scripts/aitask_*.sh` (no shell scripts are being modified)
- Verify `aitask_verified_update.sh` `--agent-string` flag works: `bash .aitask-scripts/aitask_verified_update.sh --help`

## Final Implementation Notes

- **Actual work done:** Added `detected_agent_string` context variable to task-workflow. Agent Attribution (Step 7) now stores the resolved agent string. Satisfaction Feedback (Step 9b) checks for it before self-detecting — uses `--agent-string` fast path when available, falls back to `--agent + --cli-id` self-detection for standalone callers.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Used the existing `--agent-string` flag on `aitask_verified_update.sh` rather than adding new parameters. Kept self-detection as fallback to support standalone skills that don't run Agent Attribution.

## Step 9: Post-Implementation

Archive task, commit, push per standard workflow.
