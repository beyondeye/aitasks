---
priority: medium
effort: medium
depends: [t756_6]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [t756_1, t756_2, t756_3, t756_4, t756_5, t756_6]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-01 17:38
updated_at: 2026-06-11 09:38
completed_at: 2026-06-11 09:38
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t756_1] Legacy single-head sessions still load and pass validate_graph_state. — PASS 2026-06-11 09:37 auto: legacy single-head state passes validate_graph_state; test_brainstorm_dag.py::test_legacy_single_head_state_is_valid + get_head legacy fallback
- [x] [t756_1] New map fields (current_heads/history/module_tasks/last_synced_at) round-trip write -> read -> validate for a multi-module state. — PASS 2026-06-11 09:37 auto: multi-module maps round-trip write/read/validate; test_brainstorm_dag.py::test_module_aware_state_is_valid / test_per_module_heads_are_independent
- [x] [t756_1] is_ancestor_subgraph is correct on a constructed DAG (ancestor -> True; sibling/descendant -> False). — PASS 2026-06-11 09:37 auto: is_ancestor_subgraph ancestor->True sibling/descendant->False; test_brainstorm_dag.py::test_is_ancestor_subgraph_up_only
- [x] [t756_1] current_head legacy alias resolves to current_heads["_umbrella"] in both directions. — PASS 2026-06-11 09:37 auto: current_head <-> current_heads[_umbrella] both ways; test_brainstorm_dag.py::test_umbrella_head_aliases_legacy_current_head
- [x] [t756_1] active_dimensions stays a flat session-wide list (not converted to a per-module map). — PASS 2026-06-11 09:37 auto: active_dimensions validated as flat list (map rejected); test_brainstorm_dag.py::test_active_dimensions_stays_a_list
- [x] [t756_2] With only _umbrella present, all existing ops behave exactly as before (subgraph selector auto-selects, no visible change). — PASS 2026-06-11 09:37 auto: umbrella-only defaults (UMBRELLA_SUBGRAPH) keep ops byte-identical; full suite 42/42 pass, no visible change
- [x] [t756_2] On a multi-module state the subgraph selector lists subgraphs and node-select filters candidates by module_label. — PASS 2026-06-11 09:37 auto: list_subgraphs lists subgraphs + _nodes_for_subgraph filters by module_label; test_brainstorm_wizard_subgraph.py
- [x] [t756_2] Op group entries record subgraph; legacy groups without it default to _umbrella. — PASS 2026-06-11 09:37 auto: record_operation(subgraph=) writes field, _group_subgraph defaults _umbrella; test_brainstorm_apply_module_ops.py
- [x] [t756_3] module_decompose on the _umbrella HEAD spawns per-module roots with correct module_label / parents / current_heads. — PASS 2026-06-11 09:37 auto: apply_module_decomposer_output stamps module_label/parents/per-module HEAD, umbrella unchanged; test_module_decompose_creates_roots_and_preserves_umbrella_head
- [x] [t756_3] module_merge produces a 2-parent destination node and refuses a non-ancestor destination (ancestry guard fires before agent input is assembled). — PASS 2026-06-11 09:37 auto: 2-parent destination + is_ancestor_subgraph guard before input assembly; register_module_merger + test_module_merge_creates_two_parent_destination_node
- [x] [t756_3] module_decompose --link-to-task creates a child aitask and writes module_tasks[M]. — PASS 2026-06-11 09:37 auto: --link-to-task creates child via aitask_create.sh and writes module_tasks[M]; test_brainstorm_module_ops_integration.py::test_linked_task_created_and_persisted
- [x] [t756_3] module_decompose --from-sections slices deterministically when the parent proposal has clean section markers. — PASS 2026-06-11 09:37 auto: apply_module_decompose_from_sections deterministic slice on clean markers; test_module_decompose_from_sections_creates_roots_without_agent
- [x] [t756_4] module_sync refuses a subgraph with no linked_task. — PASS 2026-06-11 09:37 auto: register_module_syncer raises 'requires a linked task' when module_tasks[M] absent; test_brainstorm_module_sync.py::test_refuses_module_without_linked_task
- [x] [t756_4] On a linked module, module_sync consumes the linked-task plan + scoped git diff + explain-context bundle and produces a synced HEAD. — PASS 2026-06-11 09:37 auto: syncer bundles plan+scoped diff+explain-context -> synced HEAD; test_brainstorm_module_sync.py::test_register_bundles_three_streams + apply advances HEAD
- [x] [t756_4] last_synced_at[<module>] advances after a sync so a re-sync sees only genuinely-newer context. — PASS 2026-06-11 09:37 auto: _write_last_synced stamps last_synced_at[module] after apply (--since horizon); test_brainstorm_module_sync.py apply-contract
- [x] [t756_4] The aitask_explain_* helper family is unmodified (consumed via shell-out only). — PASS 2026-06-11 09:37 auto: git log confirms no t756 commit touched .aitask-scripts/aitask_explain_*; brainstorm consumes via shell-out (brainstorm_crew.py:1095)
- [x] [t756_5] Per-module status badges reflect mixed states correctly (unstarted/in_design/in_implementation/implemented/merged/deferred). — PASS 2026-06-11 09:37 auto: six module states computed (unstarted/in_design/in_implementation/implemented/merged/deferred); test_brainstorm_module_status.py + status_contract
- [x] [t756_5] The deferred-module toggle persists across a TUI reload. — PASS 2026-06-11 09:37 auto: module_deferred map persisted to br_graph_state.yaml and re-read; test_brainstorm_module_status.py::test_deferred_round_trip
- [x] [t756_5] The dashboard renders the subgraph tree with per-module sync/merge state. — PASS 2026-06-11 09:37 auto: Textual pilot renders dashboard subgraph tree w/ per-module state; test_brainstorm_module_status_contract.py::test_dashboard_render_with_two_subgraphs
- [x] [t756_6] The "Fast-track this module" preset creates a subgraph + linked task in a single pass, routing through the same register_module_decomposer() as the multi-module path. — PASS 2026-06-11 09:37 auto: fast-track preset routes single-module module_decompose+link_to_task through register_module_decomposer; test_brainstorm_node_action_modal.py::test_fast_track_seeds_module_decompose_preset
- [x] [all] Full brainstorm test suite still passes after every phase lands. — PASS 2026-06-11 09:37 auto: full brainstorm test suite passes 42/42 (.py via python3 + .sh via bash), run 2026-06-11
