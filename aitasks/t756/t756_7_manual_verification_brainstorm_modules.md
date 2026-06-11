---
priority: medium
effort: medium
depends: [t756_6]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t756_1, t756_2, t756_3, t756_4, t756_5, t756_6]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-01 17:38
updated_at: 2026-06-11 09:21
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t756_1] Legacy single-head sessions still load and pass validate_graph_state.
- [ ] [t756_1] New map fields (current_heads/history/module_tasks/last_synced_at) round-trip write -> read -> validate for a multi-module state.
- [ ] [t756_1] is_ancestor_subgraph is correct on a constructed DAG (ancestor -> True; sibling/descendant -> False).
- [ ] [t756_1] current_head legacy alias resolves to current_heads["_umbrella"] in both directions.
- [ ] [t756_1] active_dimensions stays a flat session-wide list (not converted to a per-module map).
- [ ] [t756_2] With only _umbrella present, all existing ops behave exactly as before (subgraph selector auto-selects, no visible change).
- [ ] [t756_2] On a multi-module state the subgraph selector lists subgraphs and node-select filters candidates by module_label.
- [ ] [t756_2] Op group entries record subgraph; legacy groups without it default to _umbrella.
- [ ] [t756_3] module_decompose on the _umbrella HEAD spawns per-module roots with correct module_label / parents / current_heads.
- [ ] [t756_3] module_merge produces a 2-parent destination node and refuses a non-ancestor destination (ancestry guard fires before agent input is assembled).
- [ ] [t756_3] module_decompose --link-to-task creates a child aitask and writes module_tasks[M].
- [ ] [t756_3] module_decompose --from-sections slices deterministically when the parent proposal has clean section markers.
- [ ] [t756_4] module_sync refuses a subgraph with no linked_task.
- [ ] [t756_4] On a linked module, module_sync consumes the linked-task plan + scoped git diff + explain-context bundle and produces a synced HEAD.
- [ ] [t756_4] last_synced_at[<module>] advances after a sync so a re-sync sees only genuinely-newer context.
- [ ] [t756_4] The aitask_explain_* helper family is unmodified (consumed via shell-out only).
- [ ] [t756_5] Per-module status badges reflect mixed states correctly (unstarted/in_design/in_implementation/implemented/merged/deferred).
- [ ] [t756_5] The deferred-module toggle persists across a TUI reload.
- [ ] [t756_5] The dashboard renders the subgraph tree with per-module sync/merge state.
- [ ] [t756_6] The "Fast-track this module" preset creates a subgraph + linked task in a single pass, routing through the same register_module_decomposer() as the multi-module path.
- [ ] [all] Full brainstorm test suite still passes after every phase lands.
