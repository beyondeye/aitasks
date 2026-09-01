---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [task-workflow, planning, verification]
gates: [risk_evaluated]
anchor: 1538
created_at: 2026-09-01 15:18
updated_at: 2026-09-01 15:18
---

Land the advisory task-premise-staleness mechanism designed by t1561. The full design is fixed in the decision record `aidocs/framework/task_premise_staleness.md` — read it before planning any child; it is the durable context anchor for this whole tree.

## Summary of the selected design (details in the record)

- New frontmatter field `premise_baseline: <sha> @ <YYYY-MM-DD HH:MM>` — the commit at which the task's premise was last known valid. Distinct from `verification_baseline:` (that field stays scoped to manual-verification checklist validity).
- Scope and baseline are orthogonal: scope = curated `file_references:` (Tier A) or, for follow-ups, the origin's landed file surface via `lib/followup_origin.py` quality `exact` (Tier B); baseline = a stored `premise_baseline` only. **v1 is stored-baseline-only**: the measured pre-phase (2026-09-01, in the record) returned no-go on computed origin-landing baselines for legacy follow-ups (89.7% first-pick ASK_STALE, 0/5 sampled evidence sets actionable) — that tier is deferred behind a profile key.
- Verdict engine: pure core `lib/task_premise.py` (generalizing `roadmap_premise.baseline_for`/`check`) + impure producer `aitask_premise_stale.sh check <task_file>` emitting the fixed protocol `BASELINE/CHECKED/FINGERPRINT/FILES/CHANGED/DELETED/UNKNOWN/DISPLAY/DECISION` with tri-state `FRESH/ASK_STALE/SKIP`.
- Interaction: task-workflow Step 3 Check 6 (Ready tasks only), NON-SKIPPABLE four-option prompt (Proceed / Review & replan / Postpone / Pick another); baseline advances only on explicit confirmation, to the `CHECKED:` sha, gated by a post-lock `FINGERPRINT` re-check.
- Seeding: `aitask_create.sh` stamps the baseline at creation when scope is derivable (`--followup-of` / `--file-ref`); carry-over tasks inherit.

## Migration / rollout boundary

Legacy tasks without a stored baseline silently SKIP — no backfill, no prompts. Coverage grows only through creation-time seeding and manual `--premise-baseline` / `--file-ref` opt-in. The deferred computed-baseline tier (profile-keyed) is the only path to backlog-wide legacy coverage and is NOT part of this tree.

## Verification plan (tree-level)

Distributed across the children (each owns its cases — see their descriptions): protocol states incl. history rewrite and dirty worktree (child 1), concurrent metadata merges (child 2), seeding/inheritance (child 3), end-to-end prompt exercise + TOCTOU pins (child 4). The retrospective child (child 6) measures real prompt rates post-rollout and owns the deferred-surface dispositions.

## Related

- t1561 / `aiplans/p1561_generalize_task_staleness_detection.md` — the exploration that produced this tree.
- t1655 — adopts this mechanism in the roadmap and deletes `roadmap_premise.py`; depends on this parent.
- t1555 tree — the manual-verification seam; stays narrow and independent.
