---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [task-workflow, planning, verification]
gates: [risk_evaluated]
anchor: 1538
created_at: 2026-08-17 23:48
updated_at: 2026-08-17 23:48
boardcol: now
boardidx: 17478
---

Brainstorm and design an advisory staleness mechanism for ordinary backlog tasks, generalizing the useful parts of t1555 without widening that manual-verification implementation beyond its deliberately narrow scope.

## Problem

Tasks can remain Ready for long periods while the codebase, product direction, dependencies, architecture, and surrounding task graph evolve. A task may therefore still be syntactically valid but have a stale purpose, premise, scope, design, or implementation approach. Today the framework has isolated freshness checks (for example plan-review age and t1555's curated-file manual-verification pre-check), but no coherent way to surface task-level premise drift when selecting work from a large backlog.

## Explore and decide

1. Inventory the task lifecycle signals already available: task and plan timestamps, task dependencies/statuses, anchors and follow-ups, `file_references:`, git history, plan verification metadata, implementation trails, archived/landed tasks, and cross-repository dependencies.
2. Define what task staleness means in this framework. Separate detectable evidence (for example referenced files or dependencies changed) from heuristic signals (age, broad architectural change) and from purely human/product judgment. Do not present weak evidence as a false all-clear.
3. Evaluate candidate baseline and scope models, including explicit task baselines plus curated references where available, plan-digest or review provenance, dependency/implementation status changes, and an opt-in versus automatic rollout. Account for legacy tasks that lack any new metadata.
4. Design an advisory interaction at the right workflow point(s), likely before planning or when picking a Ready task: show evidence, let the user refresh/replan, proceed unchanged, postpone, or cancel; never silently rewrite, bulk-demote, or block a task solely from a heuristic.
5. Decide data ownership, merge/clear semantics, portability, performance for a giant backlog, cross-repo behavior, and how re-review advances or clears a baseline so the same evidence does not re-prompt forever.
6. Specify measurable success criteria and tests, including clean/unknown/stale states, task metadata absent/present, history rewrite, dirty worktree, concurrent metadata merges, and UI/workflow integration.

## Constraints

- Treat t1555's `verification_baseline:` and `file_references:` mechanism as a narrow manual-verification seam, not automatically as a universal task-state subsystem.
- Preserve task autonomy: staleness is advisory and evidence-backed; no automatic closure, status change, or backlog cleanup.
- Keep product/purpose drift distinct from mechanical source-file drift; the design must state the limits and false-positive/false-negative behavior clearly.
- Reuse existing helpers and schemas only when their contracts match; avoid a broad shared-writer change until a justified model is selected.
- Consider a phased rollout that leaves legacy tasks safe and quiet unless explicitly opted in or supplied with verifiable evidence.

## Deliverable

Produce a decision record in `aidocs/framework/` (or explicitly reject the generalization with evidence). Then create the appropriately scoped implementation parent task and any sequential child tasks required to land the chosen design. The implementation task tree must state its migration/rollout boundary and verification plan. Do not implement the general mechanism directly in this exploration task unless the selected work is demonstrably tiny; the default outcome is a separately planned implementation task tree.

## Related

- t1555 — manual-verification staleness pre-check; its small precondition is a model for scope discipline, not a mandate to reuse its exact field everywhere.
- `aidocs/framework/manual_verification_staleness.md` — current narrow design and deferred trade-offs.
- `.claude/skills/task-workflow/planning.md` and `.aitask-scripts/aitask_plan_verified.sh` — the existing review-freshness precedent.
- `aidocs/framework/plan_path_reference_extraction_findings.md` — **input to consult for step 2** (separating detectable evidence from heuristic signals). Records six verified defects, each with a reproduction command, in the framework's only existing "which files does this plan reference?" implementation: the extension allowlist excludes most languages, the token character class silently truncates real paths, any replacement grammar needs a delimitation rule, Unicode NFC/NFD mismatch, invalid-UTF-8 git paths, and a grep-portability trap. Produced while fixing t1275 (drift-check root allowlist); consuming it implies no dependency on t1275 unless this task's implementation elects to reuse that helper.
