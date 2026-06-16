---
Task: t983_6_wizard_rehost_drop_node_select.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_10_manual_verification_brainstorm_ia.md, aitasks/t983/t983_11_wizard_rehost_actions_screen.md, aitasks/t983/t983_7_compare_overlay_drop_tab.md, aitasks/t983/t983_8_session_tab_split.md, aitasks/t983/t983_9_running_strip_deconflict_docs.md
Archived Sibling Plans: aiplans/archived/p983/p983_1_node_detail_panel_widget.md, aiplans/archived/p983/p983_2_node_selection_model.md, aiplans/archived/p983/p983_3_browse_tab_contentswitcher.md, aiplans/archived/p983/p983_4_operations_dialog_cardinality.md, aiplans/archived/p983/p983_5_node_hub_overlay.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-16 16:39
---

# p983_6 — Drop the wizard `node_select` step when the selection is contextual (seeding half)

## Context

Parent t983 redesigns the brainstorm TUI so every node operation is launched
**contextually** from the Browse selection — via the Operations dialog (`A`,
t983_4) or the Node Hub (`Enter`, t983_5). Both already route a chosen op into
the existing Actions wizard through `_on_node_action_result`. Now that a node (or
a marked set) is *always* known before the wizard opens, the wizard's own
"pick node(s)" step is redundant and should be skipped.

**Scope (narrowed in verify mode — user-confirmed split).** The original t983_6
AC also required *physically re-hosting* the wizard off the `tab_actions`
`TabPane` into a dedicated `Screen`. Verify-mode analysis proved that half is far
larger/riskier than the original plan assumed — the plan's premise that the ~16
`query_one("#actions_content")` sites "work unchanged" is **false**: empirically,
`App.query_one` does **not** traverse a pushed screen (textual 8.2.7 —
`app.query_one("#actions_content")` raises `NoMatches`; only
`app.screen.query_one(...)` finds it), so ~28 wizard-internal queries would
break, the key-nav block in `on_key` must relocate off the App (a `ModalScreen`
consumes keys), and 3 background-thread `_actions_show_step1` refreshes need
guarding. That physical re-host is deferred to **t983_11** (depends on t983_6 +
t983_8, coordinated with the tab restructuring). The task AC has been updated.

**This task = the seeding half only**, which is contained and well-tested. The
wizard stays in its current `tab_actions` host.

All changes are in `.aitask-scripts/brainstorm/brainstorm_app.py` + tests.

## How the wizard step model & launch routing work today (verified)

- `_WIZARD_STEPS` (`:1854`) is a pure, headless list of `_WizardStep(id, active(ctx), …)`
  resolved by `active_step_ids`/`step_position`/`next_step_id` (`:1888-1920`),
  unit-tested in `tests/test_brainstorm_wizard_steps.py`.
- The `node_select` step (`:1864`) is active for `_NODE_SELECT_STEP_OPS`
  (`= {"explore", "module_decompose"}`, `:163`).
- `_wizard_ctx()` (`:6765`) feeds the resolver: `{op, node_has_sections,
  subgraph_count}` — read from App state, no I/O.
- `_on_node_action_result(node_id, op_key)` (`:4578`) is the contextual launch
  callback. Today it branches by op:
  - `fast_track` (`:4593`) / `module_decompose|merge|sync` (`:4615`): seed
    `_wizard_subgraph`, `_wizard_config = {}`, render config directly
    (`_actions_show_config` + `_enter_actions_tab`) — these already skip
    node_select at *render* time, but `module_decompose` still **counts** a
    node_select step in `step_position` (over-count), since it is in
    `_NODE_SELECT_STEP_OPS`.
  - `compare|synthesize` (`:4627`): render config directly; the source nodes are
    picked *inside* the config step via a `FuzzyCheckList` (`#cmp_nodes` /
    `#syn_nodes`, `_config_compare`/`_config_synthesize`, `:7191`/`:7297`). No
    node_select step (they are not in `_NODE_SELECT_OPS`).
  - `explore` (the only op reaching the generic tail `:4644`): renders
    `_actions_show_node_select()`, seeds `_wizard_config["_selected_node"]`, marks
    the matching `OperationRow`, then `_actions_advance_from_node_select(node_id)`
    (`:6907`, → section_select or config) + `_enter_actions_tab`.
- `_actions_show_config` (`:6961`) does **not** reset `_wizard_config`, so a
  pre-seeded `_selected_node`/`pre_seeded_node` survives into the config step.
- `FuzzyCheckList` (`:2230`) renders one `Checkbox` per item with the caller's
  `item_class` (`chk_node`); `query("Checkbox.chk_node")` collects them and
  `.value` is the checked state. `_config_compare` schedules
  `_refresh_compare_sections`/`_refresh_compare_dimensions` (which read the
  *checked* nodes) via `call_after_refresh`.

## Implementation

### 1. Make `node_select` seed-aware (do NOT delete the step)

- `_WIZARD_STEPS` `node_select` predicate (`:1864`):
  ```python
  _WizardStep(
      "node_select",
      lambda c: c.get("op") in _NODE_SELECT_STEP_OPS
      and not c.get("pre_seeded_node"),
      True,
  ),
  ```
  Keeping the step (gated, not removed) keeps every existing
  `test_brainstorm_wizard_steps.py` case green as a regression guard (their ctx
  dicts have no `pre_seeded_node`, so the clause is falsy → step active as before).
- `_wizard_ctx()` (`:6765`) — expose the flag from wizard config:
  ```python
  "pre_seeded_node": bool(self._wizard_config.get("pre_seeded_node")),
  ```

### 2. Seed the contextual selection in `_on_node_action_result`

- **explore** (rewrite the generic tail `:4644-4669`): drop the
  `_actions_show_node_select()` render + `OperationRow` marking; instead seed and
  advance:
  ```python
  self._wizard_op = op_key            # "explore"
  self._set_total_steps()
  self._wizard_config = {"_selected_node": node_id, "pre_seeded_node": True}
  self._actions_advance_from_node_select(node_id)   # → section_select / config
  self.call_after_refresh(self._enter_actions_tab)
  ```
  `_actions_advance_from_node_select` already does the `_node_has_sections` disk
  read and renders the correct next step; with `pre_seeded_node` set, the step
  numbering omits node_select.
- **module_decompose / fast_track** (`:4601`, `:4620`): add `"pre_seeded_node":
  True` to the seeded `_wizard_config` so `step_position` stops over-counting a
  node_select step. (`module_decompose` is the only module op in
  `_NODE_SELECT_STEP_OPS`; setting the flag on the shared dict is harmless for
  merge/sync, whose node_select is already inactive.) i.e. change
  `self._wizard_config = {}` → `self._wizard_config = {"pre_seeded_node": True}`
  in both the fast_track and module-op branches.
- **compare / synthesize** (`:4627`): after `_actions_show_config()`, pre-check
  the source `FuzzyCheckList` from the marked set when 2+ are marked:
  ```python
  marked = sorted(self._selection.effective())
  if len(marked) >= 2:
      self.call_after_refresh(
          lambda op=op_key, m=marked: self._preseed_multi_node_checklist(op, m)
      )
  ```

### 3. New helper `_preseed_multi_node_checklist(op_key, marked)`

Beside the other wizard helpers (near `_focus_fcl_filter`, `:6997`):

```python
def _preseed_multi_node_checklist(self, op_key: str, marked: list[str]) -> None:
    """Pre-check the compare/synthesize source-node FuzzyCheckList from the
    contextual marked set (t983_6). The user can still adjust the selection."""
    fcl_id = "cmp_nodes" if op_key == "compare" else "syn_nodes"
    try:
        fcl = self.query_one(f"#{fcl_id}", FuzzyCheckList)
    except Exception:
        return
    wanted = set(marked)
    for cb in fcl.query("Checkbox.chk_node"):
        cb.value = str(cb.label) in wanted
    if op_key == "compare":
        # Section/dimension lists derive from the checked nodes; the refreshes
        # scheduled by _config_compare ran before the boxes were checked.
        self._refresh_compare_sections()
        self._refresh_compare_dimensions()
```

(Querying via `self.query_one` is correct here — the wizard still lives in the
App's default screen; the re-host that would change this is t983_11.)

## Verification

- **Pure unit — `tests/test_brainstorm_wizard_steps.py` (extend):** add a
  seeded case asserting `active_step_ids({"op": "explore", "pre_seeded_node":
  True, ...})` omits `node_select` (and `step_position` counts one fewer), and
  the same for `module_decompose`; assert the existing non-seeded cases are
  unchanged (regression guard).
- **Pilot — `tests/test_brainstorm_node_action_modal.py` (extend, or a small new
  `test_brainstorm_wizard_seed.py`):** drive `_on_node_action_result` (using the
  `BrainstormApp.__new__` + stubbed-method harness already used by
  `OnNodeActionResultTests`) and assert:
  - explore → `_wizard_config["_selected_node"] == node_id` and
    `_wizard_config["pre_seeded_node"] is True`, and the rendered step is
    section_select/config (not node_select);
  - module_decompose/fast_track → `_wizard_config["pre_seeded_node"] is True`;
  - compare/synthesize with a 2+ marked `self._selection` →
    `_preseed_multi_node_checklist` is invoked with the marked ids (assert via a
    bare-host pilot that the `#cmp_nodes`/`#syn_nodes` boxes for the marked nodes
    end up `value=True`).
- **Suite:** `bash tests/run_all_python_tests.sh` (`tests/test_brainstorm*.py`)
  green — confirms no wizard-filter/sections/subgraph regressions (those files
  need **no** host changes, since the wizard is not re-hosted here).
- **Manual:** `ait brainstorm <session>` → Browse → focus a node → `A` →
  **explore**: wizard opens at Configure (no "Select Base Node" step). `space`-mark
  2 nodes → `A` → **compare** / **synthesize**: the source `FuzzyCheckList` opens
  with those nodes pre-checked. `Enter` → Node Hub → Operations → same behavior.

## Risk

### Code-health risk: low
- The change is additive to a pure, exhaustively-tested step model + a single
  launch callback; no new state (the flag rides in the existing `_wizard_config`).
  · severity: low · mitigation: the kept-but-gated `node_select` step + the
  unchanged existing unit cases are the regression guard.
- `call_after_refresh` ordering for the compare pre-check: the section/dimension
  refreshes scheduled by `_config_compare` run *before* the pre-check, so the
  helper re-runs them after checking the boxes. · severity: low · mitigation:
  the helper calls both refreshes explicitly; covered by the pilot.

### Goal-achievement risk: low
- Approach reuses the proven seeding precedent (`_on_node_action_result` already
  seeds `_selected_node`) and the pure step resolver; every touch point is
  verified against the current source. · severity: low · mitigation: n/a.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_6`.
