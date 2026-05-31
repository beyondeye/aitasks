---
Task: t873_4_compare_wizard_scope_group_label_dimensions.md
Parent Task: aitasks/t873_fix_brainstorm_dimension_proposal_linking_and_compare.md
Sibling Tasks: aitasks/t873/t873_5_manual_verification_fix_brainstorm_dimension_proposal_linkin.md
Archived Sibling Plans: aiplans/archived/p873/p873_1_glob_dimension_link_expansion_and_badge_count.md, aiplans/archived/p873/p873_2_section_scroll_to_position_accuracy.md, aiplans/archived/p873/p873_3_expandable_dimension_descriptions_detail_pane.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-05-31 18:22
---

# Plan: t873_4 — Compare wizard: scope, group, default-to-active, descriptive labels

## Context

Defects #4 and #5 of parent t873, in the `ait brainstorm` Actions → **compare**
wizard. The dimension step (`_config_compare`,
`.aitask-scripts/brainstorm/brainstorm_app.py:5676`) fills its checklist from
`_get_all_dimension_keys()` (`:5781`) — a **whole-graph union** of every node's
dimensions (50 keys in session `crew-brainstorm-635`), ungrouped, ignoring the
node selection and the session's `active_dimensions` (defect #4) — and labels
each row with the **raw key** (`component_profile_template_registry`), never the
descriptive value (defect #5). Picking a meaningful comparison is therefore hard.

The section sub-step already solves the analogous problem for sections
(`_refresh_compare_sections` + `_sections_intersection`), so dimensions should
follow that shape: scope to the selected nodes, group by prefix, default-check
`active_dimensions`, and show the description.

## Verification findings (this is the t873_4 verify pass)

Confirmed against current `main`. Anchors intact; line numbers drifted ~+25–32
lines from the original plan (t873_3 enlarged `DimensionRow`):

- `_config_compare` `:5676`; mounts `cmp_dims` as a **`FuzzyCheckList`**
  (`default_checked=True`, items = `_get_all_dimension_keys()`) at `:5685-5690`.
- `_refresh_compare_sections` `:5703`; `_sections_intersection` `:157`;
  `_parse_section_label` `:169` (`label.split(" ", 1)[0]`).
- `_get_all_dimension_keys` `:5781` — **only caller** is `:5686`, so it becomes
  dead after this change.
- `_actions_collect_config` compare branch `:5848-5863`; the offending line is
  `:5856` `config["dimensions"] = [str(cb.label) for cb in dim_cbs if cb.value]`.
- Node-selection hook: `_on_cmp_node_changed` (`@on(Checkbox.Changed, ".chk_node")`,
  `:6001`) already calls `self._refresh_compare_sections()`. This is the "same
  hook" to also drive dimensions.
- `group_dimensions_by_prefix` / `PREFIX_TO_LABEL` / `DIMENSION_PREFIXES`
  (`brainstorm_schemas.py:150 / :24 / :21`); `extract_dimensions` (`:145`).
  Both `extract_dimensions` and `group_dimensions_by_prefix` are **already
  imported** by the app (`:55`).
- The **detail pane already renders prefix-grouped dimensions with subheaders**
  (`_render_node_detail_widgets:5034-5067`: `group_dimensions_by_prefix(dims)` →
  `Static(classes="dim_subheader")` per group → rows). Exact reusable pattern;
  `group_dimensions_by_prefix` returns `[(prefix, human_label, [(suffix, value, full_key)])]`.
- `brainstorm_dag.py`: `_read_graph_state` `:106`; `get_active_dimensions` does
  **not** exist (must be added). App imports from `brainstorm_dag` at `:46-54`.

### Key gap found in the original plan (resolved here)

The original plan said both "**mirror `_refresh_compare_sections`**" and
"**preserve `cmp_dims` fuzzy filtering + Tab-nav** (`_fcl_group("cmp_dims")`)".
These conflict: `_refresh_compare_sections` re-mounts plain `Checkbox`es into a
plain `Container` (`#cmp_sections_box`) with **no filter Input** — mirroring it
literally would drop the fuzzy filter and break the `cmp_dims` Tab-nav group.
Meanwhile `FuzzyCheckList` (`:1585`) builds its rows once in `compose()` from a
fixed flat `items` list, has **no re-population method**, **no subheader support**,
and its `on_input_changed` filters against `self._items` — so it cannot be
re-scoped on node change as-is.

**Resolution:** extend `FuzzyCheckList` with a `set_grouped_items()` method that
re-mounts its inner list (subheaders + checkboxes) and resyncs `self._items`.
`_refresh_compare_dimensions` drives it. This preserves the filter + Tab-nav
(the Input survives, `_fcl_group("cmp_dims")` keeps working) **and** gives
node-scoped, grouped, descriptive rows. `FuzzyCheckList` is added to the
files-to-modify list (the original plan omitted it).

## Steps

1. **`get_active_dimensions` reader** (`brainstorm_dag.py`, next to
   `_read_graph_state` `:106`):
   ```python
   def get_active_dimensions(session_path: Path) -> list[str]:
       """Return the session's active dimension keys (or [] if none)."""
       gs = _read_graph_state(session_path)
       return [str(d) for d in (gs.get("active_dimensions") or [])]
   ```
   Add `get_active_dimensions` to the app's `from brainstorm.brainstorm_dag import (...)`
   block (`:46-54`).

2. **`_parse_dimension_label`** (module-level, next to `_parse_section_label`
   `:169`):
   ```python
   def _parse_dimension_label(label: str) -> str:
       """Recover the raw dimension key from a `key — value` checkbox label."""
       return label.split(" ", 1)[0]
   ```
   Safe because dimension keys never contain spaces and the label separator is
   `" — "`, so the key is always the first space-delimited token (even after the
   value is truncated).

3. **`FuzzyCheckList.set_grouped_items()`** (`:1585`). Add a method that rebuilds
   the inner `.fcl_list` `VerticalScroll` with subheaders + checkboxes and resyncs
   the filter backing list. Flat construction (`cmp_nodes`, `syn_nodes`) is
   unchanged — this is opt-in:
   ```python
   def set_grouped_items(self, groups) -> None:
       """Replace rows with grouped, subheadered items.

       `groups`: list of (subheader_text, [(label, checked), ...]). Resyncs
       `self._items` so the filter stays correct. Safe to call repeatedly
       (node-selection change), mirroring `_refresh_compare_sections`.
       """
       try:
           listview = self.query_one(".fcl_list", VerticalScroll)
       except Exception:
           return
       listview.remove_children()
       items: list[str] = []
       for subheader, rows in groups:
           listview.mount(Static(f"[bold $accent]{subheader}[/]",
                                  classes="fcl_subheader"))
           for label, checked in rows:
               listview.mount(Checkbox(label, value=checked,
                                       classes=f"{self._item_class} fcl_item"))
               items.append(label)
       self._items = items
   ```
   Add a `.fcl_subheader` style (reuse the existing `dim_subheader` rule at
   `:2459` for visual parity, or add a sibling rule). Subheaders are `Static`
   (not `Checkbox`), so `_navigate` skips them and `on_input_changed` leaves them
   visible — acceptable; the node-scoped list is short. *(Optional polish: hide a
   subheader whose group has no filter-matching checkbox.)*

4. **Node-scoped collector** `_dimension_entries_for_nodes(node_ids)` (app method,
   near `_get_all_dimension_keys`). Pure/testable — **union** of the selected
   nodes' dimensions, grouped by prefix:
   ```python
   def _dimension_entries_for_nodes(self, node_ids):
       """Union of the given nodes' dimensions, grouped by prefix.
       Returns group_dimensions_by_prefix output:
       [(prefix, label, [(suffix, value, full_key)])]."""
       merged: dict[str, str] = {}
       for nid in node_ids:
           try:
               data = read_node(self.session_path, nid)
           except Exception:
               continue
           for k, v in extract_dimensions(data).items():
               merged.setdefault(k, str(v))
       return group_dimensions_by_prefix(merged)
   ```
   **Union, not intersection** (decision): a dimension present in only one node
   is still a valid comparison axis; intersection risks an empty list when nodes
   carry divergent dimension sets (nodes hold 23–45 of 50 keys). Union scoped to
   the *selected* nodes still shrinks far below the whole-graph 50, and
   `active_dimensions` pre-checking handles "which matter".

5. **`_refresh_compare_dimensions()`** (app method, next to
   `_refresh_compare_sections`). Mirrors the section refresh's remount + state
   preservation; targets the `cmp_dims` FuzzyCheckList:
   ```python
   def _refresh_compare_dimensions(self) -> None:
       try:
           fcl = self.query_one("#cmp_dims", FuzzyCheckList)
       except Exception:
           return
       # Preserve current toggles across node-selection changes.
       for cb in fcl.query("Checkbox.chk_dim"):
           self._cmp_dim_checks[_parse_dimension_label(str(cb.label))] = bool(cb.value)

       checked_nodes = [str(cb.label) for cb in self.query("Checkbox.chk_node") if cb.value]
       if not checked_nodes:
           fcl.set_grouped_items([])
           return

       grouped = self._dimension_entries_for_nodes(checked_nodes)
       active = set(get_active_dimensions(self.session_path))
       groups = []
       for _prefix, label, entries in grouped:
           rows = []
           for _suffix, value, full_key in entries:
               v = str(value)
               trunc = v if len(v) <= 60 else v[:57] + "…"
               if full_key in self._cmp_dim_checks:
                   checked = self._cmp_dim_checks[full_key]
               elif active:
                   checked = full_key in active
               else:
                   checked = True          # fallback = old default_checked=True
               rows.append((f"{full_key} — {trunc}", checked))
           groups.append((label, rows))
       fcl.set_grouped_items(groups)
   ```

6. **Wire it up** in `_config_compare` (`:5685-5700`):
   - Replace the `all_dims = self._get_all_dimension_keys()` + conditional mount
     with an **empty** `cmp_dims` FuzzyCheckList (`FuzzyCheckList([], item_class="chk_dim", placeholder="Type to filter dimensions…", id="cmp_dims")`)
     so the filter Input + Tab-nav group exist before any node is checked.
   - Initialize `self._cmp_dim_checks = {}` alongside `self._cmp_section_checks = {}`.
   - Add `self.call_after_refresh(self._refresh_compare_dimensions)`.
   - **Delete** the now-dead `_get_all_dimension_keys` (`:5781`, only caller removed).
   In `_on_cmp_node_changed` (`:6001`), add `self._refresh_compare_dimensions()`
   after `self._refresh_compare_sections()`.

7. **Label parse-back** in `_actions_collect_config` compare branch (`:5856`):
   ```python
   config["dimensions"] = [_parse_dimension_label(str(cb.label))
                           for cb in dim_cbs if cb.value]
   ```
   The comparator receives the same raw key set as before — confirm no
   downstream change (the keys are identical; only the on-screen label gained a
   description).

8. **Tests** — extend `tests/test_brainstorm_wizard_sections.py` (reuses its
   `BrainstormApp.__new__` + temp-session harness; add a `br_nodes/` dir +
   `br_graph_state.yaml` in the new class's fixture):
   - `_parse_dimension_label`: `"component_foo — long desc"` → `"component_foo"`;
     bare key → key; value containing " — " still recovers the key.
   - `_dimension_entries_for_nodes(["n1","n2"])`: returns the grouped **union**
     of only those nodes' dimension fields (non-dimension keys excluded, other
     nodes excluded), in prefix order.
   - `get_active_dimensions`: reads `active_dimensions` from `br_graph_state.yaml`;
     `[]` when absent/empty.
   *(Confirm `read_node`'s on-disk path — `br_nodes/<nid>.yaml` — when writing the
   fixture.)*

## Files to modify

- `.aitask-scripts/brainstorm/brainstorm_app.py` — `FuzzyCheckList`
  (`set_grouped_items`), `_parse_dimension_label`, `_dimension_entries_for_nodes`,
  `_refresh_compare_dimensions`, `_config_compare`, `_on_cmp_node_changed`,
  `_actions_collect_config`; delete `_get_all_dimension_keys`; add `.fcl_subheader`
  style + the `brainstorm_dag` import line.
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — `get_active_dimensions`.
- `tests/test_brainstorm_wizard_sections.py` — new test classes.

No `.md.j2` / skill / golden changes (Python TUI only).

## Verification

- `bash tests/run_all_python_tests.sh` — brainstorm tests pass. (A pre-existing,
  unrelated `test_desync_state` failure — fake-repo fixture missing
  `python_resolve.sh` — may persist, per the t873_2/t873_3 archived notes; not
  touched here.)
- Manual (no regeneration): `ait brainstorm` → session `crew-brainstorm-635` →
  Actions → compare → select 2 nodes → the dimension checklist shows **only those
  nodes' dimensions** (not all 50), grouped under Requirements/Assumptions/
  Components/Tradeoffs subheaders, each row labeled `key — description`, with
  `active_dimensions` pre-checked. Changing the node selection re-scopes the list
  and keeps prior toggles. Filter box + Tab still work. Submitting compare passes
  the correct **raw** dimension keys to the operation.

## Post-implementation

Follow task-workflow Step 8 (review/commit) and Step 9 (archival/merge). Record
the `FuzzyCheckList.set_grouped_items` extension and the union-scope decision in
Final Implementation Notes, plus any upstream defect surfaced.
