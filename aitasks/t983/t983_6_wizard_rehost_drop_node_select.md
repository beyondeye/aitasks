---
priority: medium
effort: medium
depends: [t983_5]
issue_type: refactor
status: Implementing
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-14 11:39
updated_at: 2026-06-16 16:34
---

## Scope (NARROWED 2026-06-16 — verify mode)
**Original AC was "re-host the wizard off `#actions_content` into a dedicated
Screen + drop the node-pick step."** Verify-mode analysis showed the *physical
re-host* is far larger/riskier than the original plan assumed (the plan's premise
that the ~16 query sites "work unchanged" is **false** — `App.query_one` does NOT
traverse a pushed screen; ~28 sites break, the key-nav block must relocate off
`on_key`, and background-thread refreshes need guarding). User decision (split):

- **This task (t983_6) = the SEEDING half only** (contained, well-tested): make
  the `node_select` step seed-aware and seed the contextual selection into the
  wizard so the node-pick step is skipped. The wizard **stays in its current
  `tab_actions` host** for now.
- **The physical Screen re-host is DEFERRED to [[t983_11]]** (depends on t983_6
  and t983_8), coordinated with t983_8's tab restructuring. All re-host findings
  are recorded there.

## Context
Child of t983. Every contextual op now launches the existing Actions wizard,
seeded from the Browse selection (Operations dialog t983_4 / Node Hub t983_5):
its "pick node(s)" step is redundant and must be dropped when a node is already
in context. This keeps the pure step model + its tests valid.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` —
  make the `node_select` step predicate (`_WIZARD_STEPS`, ~:1864) seed-aware;
  expose `pre_seeded_node` in `_wizard_ctx()`; seed `_wizard_config` from the
  contextual selection in `_on_node_action_result` (explore/module_decompose →
  set `_selected_node` + `pre_seeded_node`; compare/synthesize → pre-check their
  `FuzzyCheckList` from `self._selection.effective()`).
- `tests/test_brainstorm_wizard_steps.py` — ADD a seeded-path case.
- `tests/test_brainstorm_node_action_modal.py` (or a new wizard-seed pilot) —
  assert the launch routing seeds correctly.

## Reference Files for Patterns
- Pure step model: `_WIZARD_STEPS` (~:1854), resolvers (`active_step_ids` etc.),
  tested in `tests/test_brainstorm_wizard_steps.py`.
- Existing seeding precedent: `_on_node_action_result` (~:4578) already seeds
  `_wizard_config["_selected_node"]` and calls `_actions_advance_from_node_select`
  — generalize it to skip the step entirely via `pre_seeded_node`.
- `_NODE_SELECT_STEP_OPS` (explore, module_decompose). compare/synthesize already
  have NO node_select step (they pick in `_config_compare`/`_config_synthesize`,
  ~:7191) — seed by pre-checking their `FuzzyCheckList` (`cmp_nodes`/`syn_nodes`).

## Implementation Plan
1. Make the `node_select` predicate seed-aware:
   `lambda c: c.get("op") in _NODE_SELECT_STEP_OPS and not c.get("pre_seeded_node")`
   — do NOT delete the step (keeps existing `test_brainstorm_wizard_steps.py`
   cases green as a regression guard). Expose `pre_seeded_node` in `_wizard_ctx()`.
2. Seed from the contextual selection in `_on_node_action_result`:
   explore → set `_selected_node` + `pre_seeded_node`, advance past node-select;
   module_decompose / fast_track → set `pre_seeded_node` so step numbering drops
   node-select; compare/synthesize → pre-check the `FuzzyCheckList` from the
   marked set (`self._selection.effective()`) and re-run the dependent refreshes.

## Verification
- Pure unit: NEW seeded-path case in `tests/test_brainstorm_wizard_steps.py`
  (ctx with `pre_seeded_node: True` omits `node_select`); ALL existing cases stay
  green (guard).
- Pilot: launching explore via `_on_node_action_result` seeds `_selected_node` +
  `pre_seeded_node` and skips node-select; compare/synthesize pre-check the
  FuzzyCheckList from the marked set.
- Manual: `A` → choose explore/compare → wizard opens pre-seeded, no node-pick.
