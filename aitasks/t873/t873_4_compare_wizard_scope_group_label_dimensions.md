---
priority: high
effort: medium
depends: [t873_3]
issue_type: bug
status: Ready
labels: [brainstorming, ait_brainstorm, ui]
created_at: 2026-05-31 13:14
updated_at: 2026-05-31 18:43
---

Fix defects #4 and #5 of parent t873: the compare wizard's dimension list is too long to be usable and shows cryptic keys with no meaning.

## Context
The compare wizard's dimension step (`_config_compare` at `.aitask-scripts/brainstorm/brainstorm_app.py:5644`, dimensions at :5653-5658) builds its checklist from `_get_all_dimension_keys()` (:5749-5759), which **unions every node's dimensions across the whole graph** (50 unique keys in session `crew-brainstorm-635`; individual nodes carry 23–45), deduped only by exact key. There is no grouping, no scoping to the nodes selected for comparison, and `active_dimensions` (26 in session 635) is ignored (defect #4). The checklist labels are the raw keys (e.g. `component_profile_template_registry`); the descriptive **value is never surfaced** (defect #5), so picking meaningful dimensions is hard.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py`:
  - `_config_compare` (:5644-5669) — dimension checklist mounting.
  - `_get_all_dimension_keys` (:5749-5759) — replace/augment with a node-scoped, grouped variant.
  - A dimension-refresh path mirroring `_refresh_compare_sections` (:5671-5702), so the dimension list re-mounts when the checked-node set changes.
  - `_actions_collect_config` compare branch (:5816-5831, esp. :5823-5824 `config["dimensions"] = [str(cb.label) ...]`) — must recover the raw key from a now-descriptive label.
  - The `cmp_dims` FuzzyCheckList group and its Tab-nav registration (`_fcl_group("cmp_dims")` at :3711).

## Reference Files for Patterns
- `_sections_intersection` (:152-161) + `_refresh_compare_sections` (:5671-5702): the existing pattern for **scoping a checklist to the currently-checked nodes** and re-mounting on change (`call_after_refresh(self._refresh_compare_sections)`). Mirror it for dimensions (union/intersection of just the selected nodes).
- `_parse_section_label` (:164-166, `label.split(" ", 1)[0]`): the precedent for storing a raw value behind a descriptive label. Add a `_parse_dimension_label` (or reuse it) so the raw `component_foo` key is recovered from a `component_foo — <desc>` label.
- `group_dimensions_by_prefix` and `PREFIX_TO_LABEL` (`brainstorm_schemas.py:150-170, :24-29`): for grouping by `Requirements`/`Assumptions`/`Components`/`Tradeoffs`.
- `active_dimensions` lives in graph state; the only reader is the **private** `_read_graph_state(session_path)` (`brainstorm_dag.py:106`). Either import it or add a small public reader (e.g. `get_active_dimensions(session_path)`) to brainstorm_dag and import it (app currently imports from brainstorm_dag at :46-54). Note: `_get_all_dimension_keys`/`_config_compare` currently have no graph-state access at all.
- Existing tests: `tests/test_brainstorm_wizard_sections.py` covers `_sections_intersection`/`_parse_section_label` — extend it.

## Implementation Plan
1. Add a node-scoped dimension collector (e.g. `_dimension_entries_for_nodes(node_ids)`) returning `(full_key, suffix, value)` for the union (or intersection) of the selected nodes' dimension fields, grouped by prefix via `group_dimensions_by_prefix`.
2. Add `_refresh_compare_dimensions()` mirroring `_refresh_compare_sections`: on checked-node change, re-mount the `chk_dim` checkboxes scoped to those nodes, grouped under prefix subheaders, with labels `f"{full_key} — {truncated_value}"`. Default-check entries whose key is in `active_dimensions` (read via the graph-state reader); if `active_dimensions` is empty, fall back to current `default_checked=True`.
3. Wire the refresh: call it from `call_after_refresh` in `_config_compare` and on node-checkbox change (same hook `_refresh_compare_sections` uses).
4. Add `_parse_dimension_label(label)` and use it in `_actions_collect_config` so `config["dimensions"]` stores raw keys, not the descriptive label. Verify the comparator consumes the same keys it did before (no downstream change).
5. Preserve `cmp_dims` Tab-navigation grouping (`_fcl_group`), filtering, and selection-survives-filter behavior (`aidocs/tui_conventions.md`: filters keep checked rows visible).
6. Tests: `_parse_dimension_label` round-trips a descriptive label to the raw key; node-scoped collector returns only selected nodes' keys; active_dimensions drive default-checked.

## Verification Steps
- `bash tests/run_all_python_tests.sh`.
- Manual (no regeneration): `ait brainstorm` → session 635 → Actions → compare → select 2 nodes → the dimension checklist shows only those nodes' dimensions (not all 50), grouped by type, each labeled with its description, with `active_dimensions` pre-checked. Changing the node selection re-scopes the list. Submitting compare still passes the correct raw dimension keys to the operation.
