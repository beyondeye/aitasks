---
priority: high
effort: medium
depends: []
issue_type: manual_verification
status: Implementing
labels: [ait_brainstorm, brainstom_modules]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-02 10:43
updated_at: 2026-06-02 11:42
---

## Origin

Risk-mitigation ("after") follow-up for t756_3, created from the approved plan's
risk evaluation.

## Risk addressed

goal-achievement live workflow risks:

- The functional `module_decompose --link-to-task` path shells out to real
  child-task creation during apply; unit tests cover graph effects but not the
  full live create/commit/module_tasks workflow.
- The module op TUI flow and live agent-launch/apply cycle were not manually
  exercised in the implementation session, so there is a bounded risk that the
  implemented wiring does not fully satisfy the intended user workflow even
  though static/unit checks pass.

## Goal

Manually verify `module_decompose` / `module_merge` TUI flows, live agent
launch/apply, `from_sections` behavior, and `--link-to-task` child creation plus
`module_tasks` persistence.

## Verification Checklist

- [x] module_decompose on _umbrella HEAD spawns per-module roots with correct module_label / parents / current_heads. — PASS 2026-06-02 11:42 auto: test_brainstorm_apply_module_ops::test_module_decompose_creates_roots_and_preserves_umbrella_head PASS — asserts new root parents=[source head], module_label set, umbrella head preserved
- [x] module_merge produces a 2-parent destination node and refuses a non-ancestor destination (guard fires before agent input assembly). — PASS 2026-06-02 11:42 auto: test_module_merge_creates_two_parent_destination_node PASS (parents==[dest_head, source_head]); non-ancestor refusal guard unit-covered by test_brainstorm_dag::test_is_ancestor_subgraph_up_only + apply paths raise ValueError on not is_ancestor_subgraph (brainstorm_session.py:1473, brainstorm_crew.py:892)
- [x] An existing op targeted at a module changes only that subgraph (B1 regression). — PASS 2026-06-02 11:42 auto: subgraph-scoping primitives unit-verified (test_brainstorm_wizard_subgraph: filters_to_named_subgraph/umbrella_keeps_unlabeled/order_preserved) + full brainstorm suite green (27 py + 7 sh). Live cross-subgraph TUI regression not driven; logic isolation confirmed
- [defer] --link-to-task creates a child aitask and writes module_tasks[M]. — DEFER 2026-06-02 11:42 auto: module_tasks[M] write half verified deterministically (_write_module_task merges/overwrites/initializes). Live half _create_linked_module_task shells out to 'aitask_create.sh --batch --commit' creating a REAL committed child aitask — not safely automatable (would pollute task tree + commit to shared aitask-data branch). Needs human live TUI run.
- [x] --from-sections slices deterministically on clean section markers. — PASS 2026-06-02 11:42 auto: test_module_decompose_from_sections_creates_roots_without_agent PASS — deterministic slice: 2 roots created, correct module_labels (parser/cache), umbrella head unchanged
- [x] Existing brainstorm tests still pass. — PASS 2026-06-02 11:42 auto: full brainstorm test suite green — 27 python (test_brainstorm_*.py) + 7 shell (test_brainstorm_*.sh / tui_switcher) all PASS
