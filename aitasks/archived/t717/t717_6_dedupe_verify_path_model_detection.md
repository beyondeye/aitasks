---
priority: low
effort: low
depends: []
issue_type: refactor
status: Done
labels: [verifiedstats, task-workflow]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-30 10:22
updated_at: 2026-04-30 14:47
completed_at: 2026-04-30 14:47
---

## Context

Sixth child of t717. Refactor to eliminate duplicate model self-detection in the verify-path of `task-workflow`.

**Issue identified during t717_1 verification:** In a verify-mode pick (e.g., when `plan_preference_child: verify`), the Model Self-Detection sub-procedure runs **twice**:

1. **`planning.md` line 90** (Step 6.1, verify-append) — detects to obtain `agent_string` for the `plan_verified` entry.
2. **`agent-attribution.md` line 9** (Step 7) — detects again, then sets `detected_agent_string`.

These two call sites do not share state. The verify-append path does not set `detected_agent_string`, so Step 7 has no choice but to detect again.

This is independent of t717_2's usagestats hook (which already correctly reuses `detected_agent_string` via the Step 9b fast path) — but it's the same general pattern: detect once, reuse via context variable.

**Cost is small but real:** Self-detection involves a system-message read + `aitask_resolve_detected_agent.sh` invocation (~tens of ms). The cleanup is mostly about correctness/clarity, not raw speed.

## Key Files to Modify

- `.claude/skills/task-workflow/planning.md` — at the verify-path append (currently around line 90, the section "After ExitPlanMode on the verify path"), after the Model Self-Detection call, add a step: "Set `detected_agent_string` to the resolved `agent_string` value so downstream procedures (Step 7 Agent Attribution, Step 9b Satisfaction Feedback) can reuse it."
- `.claude/skills/task-workflow/agent-attribution.md` — at step 1 (currently "Execute the Model Self-Detection Sub-Procedure to get `agent_string`"), add a fast-path guard: "If `detected_agent_string` is already set (non-null, non-empty) from an earlier procedure (e.g., the verify-path append in `planning.md`), use it directly. Otherwise execute Model Self-Detection."
- `.claude/skills/task-workflow/SKILL.md` — update the `detected_agent_string` row in the Context Requirements table to reflect that it can now also be set by `planning.md`'s verify-append, not only Step 7.

## Reference Files for Patterns

- `.claude/skills/task-workflow/satisfaction-feedback.md` lines 8, 20-22 — the existing fast-path pattern for Step 9b. Mirror the same "if detected_agent_string is non-null, skip detection" wording.
- `.claude/skills/task-workflow/SKILL.md` row 25 — current `detected_agent_string` documentation. Adjust the "Set by" clause to include verify-path.

## Implementation Plan

1. Edit `.claude/skills/task-workflow/planning.md`:
   - In the verify-path append section, after step "1. Execute the Model Self-Detection Sub-Procedure ... to obtain `agent_string`", add a new step "1b. Set `detected_agent_string` = `agent_string` (so Agent Attribution can reuse it instead of re-detecting)."
2. Edit `.claude/skills/task-workflow/agent-attribution.md`:
   - Replace step 1 with: "**Fast path:** If `detected_agent_string` is already set (non-null, non-empty), use it directly as `agent_string` and skip detection. Otherwise execute the Model Self-Detection Sub-Procedure to get `agent_string`."
3. Edit `.claude/skills/task-workflow/SKILL.md`:
   - Update the `detected_agent_string` row in Context Requirements: "Set by either the verify-path append in `planning.md` Step 6.1, or by Agent Attribution in Step 7. Consumed by both Agent Attribution (fast-path) and Satisfaction Feedback (Step 9b) to skip re-detection. Initialized to `null`."
4. Mirror the same edits to OpenCode's `.opencode/skills/task-workflow/` if it exists.
   - **Codex / Gemini:** these wrappers consolidate into `.agents/skills/task-workflow/` — verify whether `planning.md` / `agent-attribution.md` / `SKILL.md` exist there and mirror only if so. Surface as part of "post-implementation suggest separate aitasks for code-agent ports" per CLAUDE.md.

## Verification Steps

This is a docs-only / skill-instructions refactor; no automated tests apply directly. Verify by:

1. Re-read all three edited files end-to-end and confirm:
   - `planning.md` verify-append explicitly sets `detected_agent_string`.
   - `agent-attribution.md` step 1 fast-path mentions `detected_agent_string` and the fallback to Model Self-Detection.
   - `SKILL.md` Context Requirements row mentions both writers.
2. Trace a verify-mode pick mentally and confirm Model Self-Detection now fires at most once per pick.
3. Trace a non-verify pick (no verify-append) and confirm Model Self-Detection still fires once in Step 7 (no regression — the fast-path's null check falls through to detection).
4. Run shellcheck on any helper scripts touched (if any) — none expected.

## Notes for sibling tasks

- t717_2's `usage_collected` Step 0 already inherits `detected_agent_string` correctly; this refactor does not alter that. Land order does not matter — t717_2 and t717_6 are independent.
- Future sibling skills that add new model-self-detection call sites must follow this pattern: check `detected_agent_string` first, detect only on null. This convention is now uniform across `planning.md`, `agent-attribution.md`, and `satisfaction-feedback.md`.
