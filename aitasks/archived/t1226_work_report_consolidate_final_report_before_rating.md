---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Done
labels: [claudeskills, workflows]
implemented_with: claudecode/opus4_8
created_at: 2026-07-24 10:29
updated_at: 2026-07-24 10:31
completed_at: 2026-07-24 10:31
---

## Summary

The `aitask-work-report` skill's Step 6 ("Present and Iterate") did not
require the agent to re-render the complete report before advancing to the
Step 7 satisfaction-rating prompt. When a report was finalized after
incremental edits — for example an opt-in completion projection shown on its
own as a standalone delta — the agent could jump straight to the rating
without the user ever seeing one consolidated final version. The report
existed only as fragments scattered across earlier turns.

## Change

Added a **Finalization (before Step 7)** paragraph to Step 6 of
`.claude/skills/aitask-work-report/SKILL.md`: on a user satisfaction signal
("finalize" / "good" / "ship it"), the skill MUST re-render the COMPLETE
report as a single consolidated block — every iterated edit and any opt-in
projection integrated inline — and present it as the final version before
moving to Step 7. It must never advance to the satisfaction prompt while the
latest full report exists only as separate deltas.

## Scope notes

- Codex (`.agents/`) and OpenCode (`.opencode/`) variants are redirect
  wrappers pointing at the Claude Code source-of-truth, so they inherit the
  change; no cross-agent port task is needed.
- No `.j2` template exists for this skill, so there are no goldens to
  regenerate. `aitask_skill_verify.sh` passes (11 templates across 3 agents).

Retroactively wrapped with aitask-wrap.
