---
priority: medium
effort: low
depends: []
issue_type: chore
status: Ready
labels: [trails, tui]
gates: [risk_evaluated]
anchor: 2175
followup_kind: risk_mitigation
created_at: 2026-11-26 12:40
updated_at: 2026-11-26 12:40
---

## Origin

Risk-mitigation ("before") for t2335_3, created at Step 7 from the approved plan's risk evaluation.

## Risk addressed

critical-path interpretation (goal-achievement)

> The critical-path rule is an interpretation of the schema and the documented classifications (classification-aware wave edges, live depends authoritative, `released` satisfying depends but not waves, cross-repo prerequisites blocking readiness, outside prerequisites not followed, only verified-Done clears); child t2335_4's skill quotes it, so a wrong shape means rework there · severity: medium

## Goal

Review the critical-path rule and the advice contract written in t2335_3's approved plan, before t2335_3 is implemented, and record the outcome in that plan.

The plan is `aiplans/p2335/p2335_3_trails_highlight_and_critical_path_overlay.md`. Read its sections "Semantics" and "Advice contract (freshness and lifecycle)", and the `critical-path` line protocol in its implementation section 4.

Check each of these points against the sources the plan names (`.aitask-scripts/lib/implementation_trail.schema.json`, `.aitask-scripts/lib/trail_schema.py`, `aidocs/implementation_trail_design.md`, `website/content/docs/workflows/implementation-trails.md`, the classification table in `website/content/docs/tuis/board/reference.md`, `.aitask-scripts/lib/dep_resolution.py`, `.aitask-scripts/lib/cross_repo_deps.py`) and against how t2335_4 (`aitasks/t2335/t2335_4_skill_directions_code.md`: the `>d`, `>q` and `>p` codes) will quote the result:

- Wave edges by classification: only an earlier-wave `hard_prerequisite` entry blocks; `preferred_predecessor` and `core` are advisory; `coordination_only` and `optional` contribute nothing; same-wave peers are not predecessors.
- A task's readable live `depends:` is authoritative for the dependency edges into it; saved `hard_depends` / `snapshot.depends` edges apply only when the live field is unavailable, and dropped saved edges are reported as superseded.
- The `released` state (required gates passed, not Done): it satisfies dependency edges and does not satisfy wave-hard edges.
- Cross-repo prerequisites (`xdeps`) block readiness under the existing rule (only a probed `Done` unblocks).
- NEXT means pick eligibility (clear of every trail-known blocker and status `Ready`), with `in_progress` and `on_hold` beside it; the full readiness value set, including `landed` and `unverified` for foreign members.
- Prerequisites outside the stored trail are reported and not followed.
- Only a verified Done state clears a node; missing, unreadable and unresolvable tasks stay blockers.
- The freshness qualifier on every NEXT claim (current / stale / unknown, plus the TUI-only "rechecking cross-repo").
- Direction identity (slug) versus display title in the overlay request.

## Deliverable

A section `## Critical-path rule review` added to `aiplans/p2335/p2335_3_trails_highlight_and_critical_path_overlay.md`, holding one line per point above with the verdict `confirmed` or `corrected`, and for each correction the exact change made to the plan's "Semantics", "Advice contract" or line-protocol text. Edit those plan sections in place for every correction, so that the plan t2335_3 is implemented from carries the reviewed rule. Commit the plan with `./.aitask-scripts/aitask_task_commit.sh`.

This task changes no code. When a point cannot be decided from the sources, ask the user and record the answer in the review section.
