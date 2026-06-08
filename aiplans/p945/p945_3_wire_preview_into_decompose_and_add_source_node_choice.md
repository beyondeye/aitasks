---
Task: t945_3_wire_preview_into_decompose_and_add_source_node_choice.md
Parent Task: aitasks/t945_show_proposal_viewer_side_by_side_to_explore_and_decompose.md
Archived Sibling Plans: aiplans/archived/p945/p945_1_reusable_proposal_preview_pane.md, aiplans/archived/p945/p945_2_wire_preview_into_explore_wizard.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-08 17:51
---

# t945_3 — Wire preview into module-decompose + add source-node choice

## Context

Third and final child of t945 ("show proposal viewer side-by-side in the
explore and module-decompose wizards"). Siblings t945_1 (reusable
`ProposalPreviewPane` + `_mount_config_with_preview`) and t945_2 (explore
wizard wiring) have landed and are archived. This child delivers the same UX
for **module-decompose**, plus a new requirement the user raised:

1. **Source-node choice.** Today module-decompose has no node-select step — its
   collector silently uses the subgraph HEAD (`get_head`). Explore, by
   contrast, lets the user pick the base node. Add a source-node-select step to
   module-decompose, **defaulting to HEAD** so the user can advance immediately.
2. **Preview wiring.** Show the chosen source node's proposal side-by-side with
   the Decomposition Plan input, reusing `_mount_config_with_preview` /
   `ProposalPreviewPane` from t945_1 — mirroring exactly what t945_2 did for
   explore in `_config_explore_no_node`.

**Verification status (this re-pick):** the plan was re-verified against the
current `brainstorm_app.py`. All line numbers below were re-checked after
t945_1/t945_2 landed (they shifted from the original plan). The blast-radius
analysis holds and the approach is refined to the cleaner of the two options
the original plan floated.

All edits are in one file: `.aitask-scripts/brainstorm/brainstorm_app.py`.

## Reference patterns (reuse, do not reinvent)

- **`_config_explore_no_node`** (`brainstorm_app.py:7064`) — the t945_2
  template. It reads `_selected_node`, calls `read_proposal`, defines a
  `left_builder` that mounts the op's widgets, and hands off to
  `_mount_config_with_preview`. The decompose config is refactored to the same
  shape.
- **`_mount_config_with_preview`** (`:6970`) + **`ProposalPreviewPane`**
  (`:908`) — the t945_1 split-pane helper. The left builder mounts widgets into
  a `VerticalScroll` so the existing class-based collectors keep resolving them.
- **`_actions_show_node_select`** (`:6794`) + **`_actions_advance_from_node_select`**
  (`:6859`) — explore/detail/patch node-select machinery to extend.
- **`get_head`** (`brainstorm/brainstorm_dag.py:135`), **`read_proposal`**
  (`brainstorm/brainstorm_dag.py:514`).

## Blast-radius decision

`module_decompose` is in `_SUBGRAPH_SELECT_OPS` but **not** `_NODE_SELECT_OPS`
(`:157-160`). The `node_select` step (`:1867`) and the `section_select` step
(`:1868-1872`) are **both** gated on `_NODE_SELECT_OPS`. Naively adding
`module_decompose` to `_NODE_SELECT_OPS` would activate `section_select` for
decompose too — unwanted.

**Chosen approach (surgical):** introduce a dedicated set that includes
module-decompose for *node selection only*, leaving `section_select` on the
narrower set:

```python
_NODE_SELECT_OPS = {"explore", "detail", "patch"}
# Ops that get a source-node-select step. module_decompose picks a source node
# but, unlike the above, must NOT trigger the section_select step.
_NODE_SELECT_STEP_OPS = _NODE_SELECT_OPS | {"module_decompose"}
```

`grep` confirms `_NODE_SELECT_OPS` has exactly five consumers: the two step
predicates (`:1867`, `:1870`) and three node-select event handlers (`:3776`,
`:6348`, `:7807`). Switch the **node-select** sites to `_NODE_SELECT_STEP_OPS`;
**leave `section_select` (`:1870`) on `_NODE_SELECT_OPS`** — that single
untouched line is what keeps section-select off decompose.

## Implementation steps

### 1. Op-set + step predicate (`:157-160`, `:1867`)
- Add `_NODE_SELECT_STEP_OPS = _NODE_SELECT_OPS | {"module_decompose"}` after
  the two existing set defs.
- Change the `node_select` `_WizardStep` predicate (`:1867`) from
  `c.get("op") in _NODE_SELECT_OPS` to `... in _NODE_SELECT_STEP_OPS`.
- **Leave `section_select` (`:1870`) unchanged** (stays on `_NODE_SELECT_OPS`).

### 2. Node-select event handlers (`:3776`, `:6348`, `:7807`)
Switch each `self._wizard_op in _NODE_SELECT_OPS` guard in these three
node-select handlers (Enter key, `on_descendant_focus`, Next-button click) to
`_NODE_SELECT_STEP_OPS` so a decompose source node can be picked/clicked/
focused like an explore base node.

### 3. `_actions_show_node_select` — label + HEAD default (`:6794`)
- Add `"module_decompose": "Select Source Node"` to the `desc_map` (`:6803`).
  The patch-only disabled logic (`:6848`) is untouched.
- **Default to HEAD:** after mounting the rows + Next button, focus the HEAD
  row instead of the first row for module-decompose. `head` is already computed
  at `:6826` (`get_head(session, module=subgraph)`). Focusing the HEAD
  `OperationRow` makes `on_descendant_focus` (`:6345`) seed
  `_selected_node = head` and enable Next — exactly the path explore uses for
  its first row, so HEAD is pre-selected and the user can advance immediately.
  Concretely: replace the trailing
  `self.call_after_refresh(self._focus_first_operation)` with a small branch
  that, for `module_decompose` when `head in nodes`, focuses the HEAD row
  (falling back to first); otherwise calls `_focus_first_operation` as today.

### 4. `_actions_advance_from_node_select` — skip section check (`:6859`)
Guard the section-presence check (`:6880-6883`) so it only runs for
`_NODE_SELECT_OPS` (explore/detail/patch), not module-decompose:

```python
if self._wizard_op in _NODE_SELECT_OPS:
    self._wizard_has_sections = self._node_has_sections(node)
    if self._wizard_has_sections:
        self._actions_show_section_select()
        return True
if self._wizard_op == "detail":
    ...
else:
    self._actions_show_config()   # module_decompose lands here → config
```

This is belt-and-suspenders with step 1 (section_select predicate already
excludes decompose), but the advance helper bypasses the predicate by calling
`_actions_show_section_select()` directly, so the guard is required.

### 5. Collector — use chosen node (`:7465-7472`)
In the `module_decompose` branch of `_actions_collect_config`, replace:
```python
config["source_node"] = get_head(self.session_path, module=self._wizard_subgraph)
```
with the user-chosen node, falling back to HEAD:
```python
config["source_node"] = selected_node or get_head(
    self.session_path, module=self._wizard_subgraph
)
```
(`selected_node` is already read at `:7402`.) Keep the empty-HEAD warning
(`:7470-7472`) unchanged — it now also covers "no node chosen and empty HEAD".

### 6. Preview wiring — refactor `_config_module_decompose` (`:7226`)
Refactor to the `_config_explore_no_node` shape: move the existing widget
mounts (the `Source Subgraph`/`Source HEAD` labels, the `rs_decompose_mode`
`RadioSet`, the `.ta_module_decompose_modules` + `.ta_module_decompose_plan`
`TextArea`s, the `.chk_link_to_task` + `.chk_review_before_apply` checkboxes,
fast-track hint, and the Next button) into a `left_builder(left)` closure that
mounts them onto the passed `VerticalScroll`. Then:
```python
node_id = self._wizard_config.get("_selected_node") \
    or get_head(self.session_path, module=self._wizard_subgraph) or "?"
try:
    proposal = read_proposal(self.session_path, node_id)
except Exception:
    proposal = "*No proposal found.*"
...
self._mount_config_with_preview(container, left_builder, proposal)
```
Update the `Source HEAD:` label to reflect the chosen source node (e.g. show
`node_id`) so it stays accurate when the node differs from HEAD. Class-based
collectors in step 5 keep resolving the widgets through the new wrapper (same
guarantee t945_2 relied on).

### Express entry paths left intentionally unchanged
Two paths seed module-decompose from a focused DAG node and render config
directly, bypassing the wizard's op/subgraph/node steps:
- fast-track preset (`:4120-4135`)
- node-context decompose (`:4142-4153`)

Both leave `_wizard_config = {}`, so the step-5 collector falls back to
`get_head` — **HEAD behavior preserved**, matching the original plan's "default
to HEAD when unchanged". Adding `module_decompose` to the node-select step set
makes `step_position` count `node_select` in the total, so these express
renders' "Step X of Y" total bumps by one even though they skip that step. This
is cosmetic only (these entries already bypass op-select/subgraph indicators)
and `node_select` is never reachable via Back from config/confirm. Not worth
special-casing; noted for the reviewer.

## Verification

- Launch `ait brainstorm` on a session with proposals. Run module-decompose
  from the wizard: op-select → (subgraph-select if 2+ subgraphs) → **new
  source-node select (HEAD pre-highlighted, Next enabled)** → config. Confirm:
  - the chosen node's proposal renders in the right pane with a working minimap
    (cycle the split ratio with the preview keybinding);
  - `section_select` does **not** appear for decompose even on a node that has
    sections;
  - the decompose runs against the chosen node (pick a non-HEAD node and verify
    `source_node` in the resulting op/confirm reflects it).
- Re-run **explore** end-to-end to confirm the shared node-select / op-set
  changes did not regress its base-node selection, section-select, or preview.
- Run the brainstorm app tests under `tests/` that touch the wizard step
  machinery / config collection (e.g. `grep -l wizard tests/`), plus any
  `_WIZARD_STEPS` / `active_step_ids` / `step_position` unit tests.

## Risk

### Code-health risk: medium
- Shared node-select machinery (`_NODE_SELECT_OPS` consumers, the
  `node_select`/`section_select` predicates, `_actions_advance_from_node_select`)
  is also on explore/detail/patch's hot path; a mis-scoped predicate could
  regress those ops. · severity: medium · → mitigation: TBD (covered by the
  explore re-run in Verification; the new `_NODE_SELECT_STEP_OPS` set is
  additive and `section_select` stays on the untouched narrower set).
- Express decompose entries get a cosmetic off-by-one in the step total.
  · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Approach directly mirrors the already-landed, already-reviewed t945_2 explore
  wiring; both deliverables (source-node choice + preview) are concretely
  addressed against verified call sites. · severity: low · → mitigation: TBD

## Post-implementation
Follow task-workflow Step 8 (review) → Step 9 (archival). When this child
archives, all three t945 children are complete and parent t945 auto-archives.
