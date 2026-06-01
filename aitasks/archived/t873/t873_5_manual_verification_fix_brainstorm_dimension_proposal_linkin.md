---
priority: medium
effort: medium
depends: [t873_4]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [t873_1, t873_2, t873_3, t873_4]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-31 13:24
updated_at: 2026-06-01 08:44
completed_at: 2026-06-01 08:44
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t873_1] Run `bash tests/run_all_python_tests.sh` — PASS 2026-06-01 08:41 auto: full suite 929/929 OK; test_brainstorm_sections 39 pass incl. glob-expansion (test_matches_prefix_glob, test_glob_tag_resolves_real_key) + validate-with-node-keys (test_node_keys_flags_invented_tag/accepts_glob_and_real_key)
- [x] [t873_1] `ait brainstorm` → session crew-brainstorm-635 → node n004: dimension rows covered only by a glob section tag now show a real `[N §]` count (not `[0 §]`). — PASS 2026-06-01 08:41 auto: glob-expansion fix verified on real data. n004 proposal now uses explicit per-key tags (no globs) so badges all compute (38/45 dims non-zero; 7 legit-unlinked). Glob-only coverage demonstrated on n002_profile_templated_gates: 10 dims covered ONLY by component_*/assumption_* globs all resolve to [1 §] (pre-fix exact-membership returned False -> would show [0 §])
- [x] [t873_1] On such a row, Enter opens the proposal (no "No proposal sections tagged" warning). — PASS 2026-06-01 08:41 auto: get_sections_for_dimension returns non-empty for all 10 glob-only dims on n002 -> Enter pushes SectionViewerScreen (no 'No proposal sections tagged' warning); best_section_for_dimension yields a scroll target
- [x] [t873_1] Stub nodes n005/n007/n008 still legitimately show `[0 §]` (they have zero section markers). — PASS 2026-06-01 08:41 auto: n005/n007/n008 proposals have 0 '<!-- section:' markers (6-line stubs) -> every dimension count=0 -> [0 §] legitimately
- [skip] [t873_1] (Optional, generation) Run one explore/detail op — SKIP 2026-06-01 08:43 Optional generation check; not applicable for offline auto-verification (needs live explorer/detailer agent run). Template-side fix verified + unit-tested under t873_1.
- [x] [t873_2] `ait brainstorm` → session 635 → n004 (709-line proposal): Enter on a deep-section dimension row lands on that section's heading, not screens away. — PASS 2026-06-01 08:41 auto: test_section_viewer_scroll.py AutoScrollPilotTests (Pilot-driven, real Textual widgets) assert a deep section heading lands at viewport-top offset <=2; plan records live confirmation on n004 (709-line). 27 tests OK
- [x] [t873_2] Repeat on n002 (373/585-line proposals) — PASS 2026-06-01 08:41 auto: same Pilot suite covers inline-code headings + n002/n000 sections landing top-aligned; plan confirmed live against n002 (373/585). Green
- [x] [t873_2] Minimap section selection in the SectionViewer also lands on the correct heading. — PASS 2026-06-01 08:41 auto: AutoScrollPilotTests includes minimap-selection-scrolls case; scroll_to_section (minimap path) uses same TOC-correlated anchor lookup. Green
- [x] [t873_3] `ait brainstorm` → session 635 → node with long dimension values: the toggle key (e.g. space) expands a clipped dimension row to the full wrapped description and collapses again. — PASS 2026-06-01 08:41 auto: test_brainstorm_dimension_row_expand.py Pilot test drives real DimensionRow: space grows size.height 1->multi-line->1 (expand/collapse). 2 tests OK
- [x] [t873_3] Enter on a dimension row still performs the proposal jump (no collision with the expand key). — PASS 2026-06-01 08:41 auto: same Pilot test asserts enter posts DimensionRow.Activated without toggling expand; on_key routes enter->Activated, space->toggle (distinct keys, no collision)
- [x] [t873_3] The expand toggle is discoverable in the detail-pane footer/hint. — PASS 2026-06-01 08:41 auto: code inspection brainstorm_app.py:5099-5101 emits Static hint 'space: expand/collapse · enter: jump to proposal' directly under the Dimensions header in _render_node_detail_widgets
- [x] [t873_4] `ait brainstorm` → session 635 → Actions → compare → select 2 nodes: dimension checklist shows only those nodes' dimensions (not the whole-graph union of 50). — PASS 2026-06-01 08:41 auto: data-driven on session 635 — whole-graph union=50 keys; _dimension_entries_for_nodes scoped to 2 nodes=3 keys (<<50). Wired via _on_cmp_node_changed->_refresh_compare_dimensions. DimensionEntriesForNodesTests (6) green
- [x] [t873_4] Dimensions are grouped by prefix (Requirements/Assumptions/Components/Tradeoffs) and each entry is labeled with its description, not just the raw key. — PASS 2026-06-01 08:41 auto: group_dimensions_by_prefix yields Requirements/Assumptions/Components/Tradeoffs subheaders; rows labeled 'key — description' (set_grouped_items + FuzzyCheckList). Verified on real nodes
- [x] [t873_4] `active_dimensions` are pre-checked by default; changing the node selection re-scopes the dimension list. — PASS 2026-06-01 08:41 auto: get_active_dimensions reads 26 active keys from br_graph_state.yaml; pre-check = full_key in active (active∩scoped); node-change triggers _refresh_compare_dimensions re-scope preserving _cmp_dim_checks toggles
- [x] [t873_4] Submitting the compare operation passes the correct raw dimension keys (verify the launched comparator config / resulting node). — PASS 2026-06-01 08:41 auto: _parse_dimension_label('key — desc — with dashes')->'key' (round-trips raw key even with em-dash in value); _actions_collect_config compare branch uses it so comparator receives raw keys. ParseDimensionLabelTests (4) green
