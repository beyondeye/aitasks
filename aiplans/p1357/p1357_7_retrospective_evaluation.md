---
Task: t1357_7_retrospective_evaluation.md
Parent Task: aitasks/t1357_task_workflow_step_stats_and_drift.md
Sibling Tasks: aitasks/t1357/t1357_1_*.md … t1357_6_*.md
Archived Sibling Plans: aiplans/archived/p1357/p1357_*_*.md
Worktree: aiwork/t1357_7_retrospective_evaluation
Branch: aitask/t1357_7_retrospective_evaluation
Base branch: main
Output branch: main
---

# Plan: t1357_7 — Retrospective evaluation of the step-stats system

**Timing gate:** pick this only after ≥2–3 weeks of real accumulated data
(check: `ls aitasks/metadata/stats/events/` spans enough runs). If picked
early, revert to Ready and defer.

## Steps

1. **Data pull:** small throwaway queries over the event store (python
   one-liners or a scratch script; cite every command in the report):
   - Per step: count of runs containing that step's events, split by `src`
     (`helper:*` vs `skill` vs `capture`) → skill-stamp fire-rate table.
   - Drift-flag history: run `ait stats` drift section over the period;
     count flags; classify each as real signal / noise by inspecting the
     underlying runs.
   - Enrichment: `join=` distribution from run/end extras; effort-dimension
     population rate (rows with effort != unknown).
   - Outcomes: done / aborted / deferred / orphaned counts.
2. **Decisions** (each recorded with rationale in the findings report):
   - Harden specific under-firing skill stamps (move to helper / strengthen
     wording) — only where absence degrades the step table materially.
   - Tune `drift_threshold_pct` / `drift_min_samples` in stats_config.
   - Enrichment join: keep heuristic vs. propose session-id-from-env task.
   - Re-prioritize t1358 (TUI pane) and t1359 (Codex/OpenCode enrichment).
3. **Findings report:** append `## Retrospective findings` to this plan file
   (method + numbers + decisions). Config tuning lands as normal commits in
   this task. New follow-up tasks only where data justifies them
   (`ait create --batch --followup-of 1357 …`).
4. Zero-findings outcome is valid: the documented audit is the deliverable
   (no speculative infrastructure).

## Verification

Report contains reproducible commands; any config change is reflected in a
subsequent `ait stats` run shown in the report.

## Step 9

Standard Step 9. This is the last child — its archival triggers the parent
archival check on the next pick.
