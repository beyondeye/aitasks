---
priority: medium
effort: medium
depends: [t756_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [756_1, 756_2, 756_3, 756_4]
created_at: 2026-06-01 17:08
updated_at: 2026-06-01 17:08
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
- [ ] [t756_2] module_decompose on the _umbrella HEAD spawns per-module roots with correct module_label / parents / current_heads.
- [ ] [t756_2] module_merge produces a 2-parent destination node and refuses a non-ancestor destination (ancestry guard fires before agent input is assembled).
- [ ] [t756_2] An existing op (e.g. explore) targeted at a module changes only that subgraph, not the umbrella or other modules.
- [ ] [t756_2] module_decompose --link-to-task creates a child aitask and writes module_tasks[M].
- [ ] [t756_2] module_decompose --from-sections slices deterministically when the parent proposal has clean section markers.
- [ ] [t756_3] module_sync refuses a subgraph with no linked_task.
- [ ] [t756_3] On a linked module, module_sync consumes the linked-task plan + scoped git diff + explain-context bundle and produces a synced HEAD.
- [ ] [t756_3] last_synced_at[<module>] advances after a sync so a re-sync sees only genuinely-newer context.
- [ ] [t756_3] The aitask_explain_* helper family is unmodified (consumed via shell-out only).
- [ ] [t756_4] Per-module status badges reflect mixed states correctly (unstarted/in_design/in_implementation/implemented/merged/deferred).
- [ ] [t756_4] The "Fast-track this module" preset creates a subgraph + linked task in one pass.
- [ ] [t756_4] The deferred-module toggle persists across a TUI reload.
- [ ] [t756_4] The dashboard renders the subgraph tree with per-module sync/merge state.
- [ ] [all] Full brainstorm test suite still passes after every phase lands.
