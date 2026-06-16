---
priority: medium
effort: high
depends: [t983_5]
issue_type: refactor
status: Implementing
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-14 11:39
updated_at: 2026-06-16 15:32
---

## Context
Child of t983 — the **heaviest seam**. The Actions tab is removed in the target
IA, but its multi-step wizard must survive, launched (seeded) from the Operations
dialog (t983_4) / Node Hub (t983_5). The wizard mounts into `#actions_content`
(`.aitask-scripts/brainstorm/brainstorm_app.py:3569`) via ~16 live `query_one`
sites and its config collectors resolve widgets *through* that id — so the id is
load-bearing. This child re-hosts the wizard and drops its node-pick step (the
selection is now contextual), keeping the pure step model + its tests valid.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — host the wizard in a dedicated
  `Screen` that owns a `VerticalScroll(id="actions_content")` (KEEP the id);
  make the `node_select` step predicate (:1832) seed-aware; seed
  `_wizard_config["_selected_node"]` / node lists from the selection; sweep
  `tabbed.active == "tab_actions"` checks + `isinstance(self.screen, ModalScreen)`
  guards onto the new host.
- `tests/test_brainstorm_wizard_steps.py` — ADD a seeded-path case.
- `tests/test_brainstorm_wizard_filter.py` / `_sections.py` / `_subgraph.py` —
  update for the new host.

## Reference Files for Patterns
- Pure step model: `_WIZARD_STEPS` (:1822), resolvers (:1856-1887), tested in
  `tests/test_brainstorm_wizard_steps.py`.
- Existing seeding precedent: `_on_node_action_result` (:4102) already seeds
  `_wizard_config["_selected_node"]` and calls `_actions_advance_from_node_select`
  — generalize it to skip the step entirely.
- `_NODE_SELECT_STEP_OPS` (explore, module_decompose). compare/synthesize already
  have NO node_select step (they pick in `_config_compare`/`_config_synthesize`,
  :6515) — seed by pre-checking their `FuzzyCheckList`.

## Implementation Plan
1. Create the wizard host `Screen` mounting `VerticalScroll(id="actions_content")`
   so the ~16 query sites + config collectors work unchanged.
2. Change the `node_select` predicate to
   `lambda c: c.get("op") in _NODE_SELECT_STEP_OPS and not c.get("pre_seeded_node")`
   — do NOT delete the step (keeps existing `test_brainstorm_wizard_steps.py`
   cases green as a regression guard).
3. When launching from Operations dialog / Node Hub: set `pre_seeded_node` +
   `_selected_node` from the selection (explore/module_decompose); pre-check the
   FuzzyCheckList from the marked set (compare/synthesize).
4. Repoint every `tabbed.active == "tab_actions"` check and the
   `isinstance(self.screen, ModalScreen)` wizard-key guards to the new host.

## Verification
- Pure unit: NEW seeded-path case in `tests/test_brainstorm_wizard_steps.py`
  (seeded ctx omits `node_select`); ALL existing cases stay green (guard).
- Pilot: launching an op from the Operations dialog seeds the wizard and skips
  the node-pick step; `wizard_filter`/`_sections`/`_subgraph` updated + green.
- Manual: `A` → choose explore/compare → wizard opens pre-seeded, no node-pick.
