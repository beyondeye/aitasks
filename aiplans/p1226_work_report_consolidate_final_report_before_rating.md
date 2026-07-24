---
Task: t1226_work_report_consolidate_final_report_before_rating.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Added a **Finalization (before Step 7)** requirement to Step 6 of the
`aitask-work-report` skill so the complete report is always re-rendered as a
single consolidated block before the satisfaction-rating prompt. Previously
Step 6 only said "present the draft ... iterate until satisfied," with no
instruction to re-emit the whole report at finalization — so a report whose
last edits arrived as standalone deltas (e.g. an opt-in completion projection
shown on its own) could advance to rating without the user ever seeing one
whole, current version.

## Files Modified

- `.claude/skills/aitask-work-report/SKILL.md` — inserted a nine-line
  **Finalization (before Step 7)** paragraph after the existing Step 6
  "Present and Iterate" text. It requires that, on a user satisfaction signal
  ("finalize" / "good" / "ship it"), the agent re-render the COMPLETE report
  as a single consolidated block (all iterated edits and any opt-in projection
  integrated inline) and present it as the final version before moving to Step
  7, and never advance to the satisfaction prompt while the latest full report
  exists only as separate deltas across earlier turns.

## Probable User Intent

The gap surfaced in live use: a work report was iterated (a completion
projection added as a delta), then finalized, and the skill went straight to
the satisfaction rating without printing the assembled final report. The user
expected to see the consolidated final version before rating. The fix pins
that expectation in the skill source rather than leaving it to the agent to
infer, closing the "stitch of fragments" failure mode.

## Final Implementation Notes

- **Actual work done:** One additive prose insertion into Step 6 of the
  Claude Code source-of-truth SKILL.md. No logic/scripts changed.
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed).
- **Issues encountered:** N/A (change was made before wrapping).
- **Key decisions:**
  - Enforced the behavior in the skill source (contractual instruction),
    consistent with the project's "source enforcement over behavior-memory"
    convention, rather than relying on agent inference.
  - No cross-agent port task: the Codex (`.agents/`) and OpenCode
    (`.opencode/`) work-report skills are redirect wrappers that defer to the
    Claude Code source-of-truth, so they inherit the change automatically.
  - No `.j2` template exists for this skill, so no goldens required
    regeneration; `aitask_skill_verify.sh` reported OK (11 templates across 3
    agents).
