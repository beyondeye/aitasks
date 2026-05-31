---
Task: t873_4_compare_wizard_scope_group_label_dimensions.md
Parent Task: aitasks/t873_fix_brainstorm_dimension_proposal_linking_and_compare.md
Sibling Tasks: aitasks/t873/t873_*.md
Archived Sibling Plans: aiplans/archived/p873/p873_*_*.md
Worktree: aiwork/t873_4_compare_wizard_scope_group_label_dimensions
Branch: aitask/t873_4_compare_wizard_scope_group_label_dimensions
Base branch: main
---

# Plan: t873_4 — Compare wizard: scope, group, default-to-active, descriptive labels

Make the compare wizard's dimension step usable: scope candidate dimensions to
the selected nodes, group by prefix, default-check `active_dimensions`, and label
each entry with its description instead of the raw key.

## Root cause
`_config_compare` (`.aitask-scripts/brainstorm/brainstorm_app.py:5644`) fills its
checklist from `_get_all_dimension_keys()` (:5749-5759) — a whole-graph union (50
keys), ungrouped, ignoring node selection and `active_dimensions` (defect #4) —
and labels rows with raw keys (defect #5). The section sub-step already does the
right thing for sections (`_refresh_compare_sections` + `_sections_intersection`),
so dimensions should mirror it.

## Steps
1. **Node-scoped collector** `_dimension_entries_for_nodes(node_ids)` → grouped
   `(prefix, label, [(full_key, suffix, value)])` for the union (or intersection)
   of the selected nodes' `get_dimension_fields`, via `group_dimensions_by_prefix`
   (`brainstorm_schemas.py:150`).
2. **`_refresh_compare_dimensions()`** mirroring `_refresh_compare_sections`
   (:5671-5702): on checked-node change, re-mount `chk_dim` checkboxes scoped to
   those nodes, under prefix subheaders (`PREFIX_TO_LABEL`), labels
   `f"{full_key} — {truncated_value}"`. Default-check keys in `active_dimensions`;
   if empty, fall back to the current `default_checked=True`.
3. **active_dimensions plumbing** — only reader is private
   `_read_graph_state(session_path)` (`brainstorm_dag.py:106`). Add a public
   `get_active_dimensions(session_path) -> list[str]` to `brainstorm_dag` and
   import it (app imports from brainstorm_dag at :46-54).
4. **Wire refresh** — `call_after_refresh(self._refresh_compare_dimensions)` in
   `_config_compare`, plus on node-checkbox change (the same hook that drives
   `_refresh_compare_sections`).
5. **Label parse-back** — add `_parse_dimension_label(label)` (mirror
   `_parse_section_label` :164, split on first space → key) and use it in
   `_actions_collect_config` (:5823-5824) so `config["dimensions"]` stores raw
   keys. Confirm the comparator still receives the same key set as before.
6. **Preserve** `cmp_dims` Tab-nav grouping (`_fcl_group("cmp_dims")` :3711),
   fuzzy filtering, and "checked rows stay visible under filter"
   (`aidocs/tui_conventions.md`).
7. **Tests** (`tests/test_brainstorm_wizard_sections.py`): `_parse_dimension_label`
   round-trips a descriptive label → raw key; node-scoped collector returns only
   selected nodes' keys; active_dimensions drive default-checked.

## Verification
- `bash tests/run_all_python_tests.sh`.
- Manual (no regeneration): `ait brainstorm` → session `crew-brainstorm-635` →
  Actions → compare → select 2 nodes → dimension checklist shows only those nodes'
  dimensions (not all 50), grouped by type, each labeled with its description,
  with `active_dimensions` pre-checked; changing node selection re-scopes the
  list; submitting compare passes correct raw keys.

## Post-implementation
Follow task-workflow Step 8 (review/commit) and Step 9 (archival/merge). Record
any related upstream defect in the plan's Final Implementation Notes.
