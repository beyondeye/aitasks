# Plan for t1010: Guard Brainstorm Root Node Delete

## Summary

Prevent the brainstorm DAG root from being cascade-deleted. The fix uses
defense in depth: the Operations dialog disables delete for the canonical root,
and the DAG delete function refuses root deletion even if called directly.

## Implementation Plan

- Identify the canonical root as the earliest parentless node in a session,
  using the existing node-id ordinal logic and a deterministic id tie-breaker.
- Add a root-refusal branch to `delete_node_cascade` that returns an empty
  deletion report with `refused_root: True` and leaves graph files untouched.
- Pass the root fact into `op_states_for_selection` and disable `delete` at
  single-node cardinality with the reason `cannot delete the root design`.
- Add app-level guards in `_open_delete_node_modal` and
  `_on_delete_node_result` so stale/direct UI paths notify and return before
  any cascade work.
- Extend existing DAG, operation relevance, and delete callback tests for root
  refusal and unchanged non-root delete behavior.

## Verification

- `python -m unittest tests.test_brainstorm_dag tests.test_brainstorm_node_action_relevance tests.test_brainstorm_node_delete tests.test_brainstorm_node_action_modal`
- `python -m unittest tests.test_brainstorm_node_hub tests.test_brainstorm_node_action_integration`
- `python -m py_compile .aitask-scripts/brainstorm/brainstorm_dag.py .aitask-scripts/brainstorm/brainstorm_app.py`
- `git diff --check`

## Final Implementation Notes

- **Actual work done:** Added `root_node_id` / `is_root_node` helpers in the
  brainstorm DAG layer, taught `delete_node_cascade` to return `refused_root`
  without mutating files, disabled the Operations dialog delete row for the
  canonical root, and added callback guards for root-delete modal paths.
- **Deviations from plan:** None. The implemented approach follows the planned
  defense-in-depth design.
- **Issues encountered:** The existing single-parentless-node delete test was
  asserting the old behavior. It was updated to use a later disconnected
  parentless node so it still verifies non-root parentless head deletion while
  the earliest parentless node is protected as root.
- **Key decisions:** The root is the earliest parentless node, not hard-coded
  `n000_init`, so imported or nonstandard sessions remain protected without
  blocking deletion of later disconnected parentless nodes.
- **Upstream defects identified:** None
