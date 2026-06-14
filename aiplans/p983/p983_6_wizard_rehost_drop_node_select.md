---
Task: t983_6_wizard_rehost_drop_node_select.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_*_*.md
Archived Sibling Plans: aiplans/archived/p983/p983_*_*.md
Worktree: aiwork/t983_6_wizard_rehost_drop_node_select
Branch: aitask/t983_6_wizard_rehost_drop_node_select
Base branch: main
---

# p983_6 — Wizard re-host + drop `node_select`

Child of t983 — **heaviest seam**. The Actions tab is removed; its wizard must
survive, launched seeded from the Operations dialog (t983_4) / Node Hub (t983_5).

## Goal
Re-host the wizard off `#actions_content`
(`.aitask-scripts/brainstorm/brainstorm_app.py:3569`, ~16 load-bearing query
sites) into a dedicated host, drop the node-pick step (selection is now
contextual), keep the pure step model + tests valid.

## Steps
1. Host the wizard in a dedicated `Screen` that owns a
   `VerticalScroll(id="actions_content")` — KEEP the id so the ~16 `query_one`
   sites + config collectors work unchanged.
2. Make `node_select` predicate (:1832) **seed-aware** (do NOT delete the step):
   `lambda c: c.get("op") in _NODE_SELECT_STEP_OPS and not c.get("pre_seeded_node")`.
3. Seed from the selection: explore/module_decompose → set `pre_seeded_node` +
   `_wizard_config["_selected_node"]` (generalize `_on_node_action_result`,
   :4102); compare/synthesize → pre-check their `FuzzyCheckList`
   (`_config_compare`/`_config_synthesize`, :6515).
4. Sweep `tabbed.active == "tab_actions"` checks + the wizard-key
   `isinstance(self.screen, ModalScreen)` guards onto the new host.

## Verification
- Pure unit: ADD a seeded-path case to `tests/test_brainstorm_wizard_steps.py`
  (seeded ctx omits `node_select`); ALL existing cases stay green = regression
  guard.
- Pilot: op launched from the Operations dialog seeds the wizard, skips node-pick;
  update + green `wizard_filter`/`wizard_sections`/`wizard_subgraph`.
- Manual: `A` → explore/compare → wizard opens pre-seeded, no node-pick step.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_6`.
