---
priority: medium
effort: medium
depends: [t873_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [873_1, 873_2, 873_3, 873_4]
created_at: 2026-05-31 13:24
updated_at: 2026-05-31 13:24
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t873_1] Run `bash tests/run_all_python_tests.sh` — all brainstorm_sections tests (incl. new glob-expansion / validate-with-node-keys) pass.
- [ ] [t873_1] `ait brainstorm` → session crew-brainstorm-635 → node n004: dimension rows covered only by a glob section tag now show a real `[N §]` count (not `[0 §]`).
- [ ] [t873_1] On such a row, Enter opens the proposal (no "No proposal sections tagged" warning).
- [ ] [t873_1] Stub nodes n005/n007/n008 still legitimately show `[0 §]` (they have zero section markers).
- [ ] [t873_1] (Optional, generation) Run one explore/detail op — the new proposal uses `tradeoff_*` / real keys, not invented `tradeoff_pros`/`tradeoff_cons`.
- [ ] [t873_2] `ait brainstorm` → session 635 → n004 (709-line proposal): Enter on a deep-section dimension row lands on that section's heading, not screens away.
- [ ] [t873_2] Repeat on n002 (373/585-line proposals) — section jump lands accurately.
- [ ] [t873_2] Minimap section selection in the SectionViewer also lands on the correct heading.
- [ ] [t873_3] `ait brainstorm` → session 635 → node with long dimension values: the toggle key (e.g. space) expands a clipped dimension row to the full wrapped description and collapses again.
- [ ] [t873_3] Enter on a dimension row still performs the proposal jump (no collision with the expand key).
- [ ] [t873_3] The expand toggle is discoverable in the detail-pane footer/hint.
- [ ] [t873_4] `ait brainstorm` → session 635 → Actions → compare → select 2 nodes: dimension checklist shows only those nodes' dimensions (not the whole-graph union of 50).
- [ ] [t873_4] Dimensions are grouped by prefix (Requirements/Assumptions/Components/Tradeoffs) and each entry is labeled with its description, not just the raw key.
- [ ] [t873_4] `active_dimensions` are pre-checked by default; changing the node selection re-scopes the dimension list.
- [ ] [t873_4] Submitting the compare operation passes the correct raw dimension keys (verify the launched comparator config / resulting node).
