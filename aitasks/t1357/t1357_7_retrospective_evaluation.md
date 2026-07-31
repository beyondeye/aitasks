---
priority: medium
effort: low
depends: [t1357_6]
issue_type: chore
status: Ready
labels: [reporting, task_workflow]
gates: [risk_evaluated]
anchor: 1357
created_at: 2026-07-31 10:59
updated_at: 2026-07-31 10:59
---

## Context

Trailing retrospective child of t1357 (per planning conventions: a
retrospective-evaluation child bounded by the parent, whose outputs may
include new top-level tasks). Pick this up only after >=2-3 weeks of
step-stats data have accumulated from real /aitask-pick runs.

Parent plan: `aiplans/p1357_task_workflow_step_stats_and_drift.md`
(child t1357_7 section). Depends on all prior siblings.

## What to evaluate (against real accumulated data)

1. **Event completeness:** using the `src` field, measure which skill-text
   stamps (src=skill, from t1357_3) actually fire vs. get skipped by
   agents, per step. Harden (move to a deterministic helper, or strengthen
   the skill wording) ONLY the ones whose absence materially degrades the
   step table — do not blanket-harden.
2. **Drift signal quality:** are the default thresholds
   (`drift_threshold_pct=20`, `drift_min_samples=3` in stats_config) firing
   usefully — no noise floods, no missed real regressions? Tune in config.
3. **Enrichment join quality:** fraction of runs with `join=pid` vs
   `window` vs `none`; is the Claude Code effort back-fill populating the
   effort dimension? Decide whether the join heuristic needs the
   session-id-from-env approach instead.
4. **Orphan/abort accounting:** how many runs end `outcome=orphaned` /
   `aborted` — does the sweep work in practice?
5. **Deferred follow-ups priority check:** re-prioritize the two follow-up
   tasks created at decomposition (stats-TUI drift pane; Codex/OpenCode
   transcript enrichment) based on observed usage — bump or postpone.

## Deliverables

- A short findings report appended to this task's plan file (method +
  numbers + decisions), config tuning commits if warranted, and new
  standalone follow-up tasks ONLY where the data justifies them
  (`ait create --batch --followup-of 1357 ...`).
- If everything checks out with no changes needed, the documented audit
  itself is the deliverable (audit-only tasks with zero findings produce
  audit-only plans — no speculative infrastructure).

## Verification

- The report cites concrete queries over the event store (commands
  included) so numbers are reproducible.
