---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [ait_brainstorm, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-14 15:52
updated_at: 2026-10-14 18:59
---

## Problem

In `ait brainstorm`, every new node adds "dimensions" to the proposal (keys with the
`requirements_` / `assumption_` / `component_` / `tradeoff_` prefixes), and no operation
removes them. The dimension metadata ends up as most of each node file, and the user
does not necessarily want to keep every dimension.

Measured on brainstorm session 1812 (`.aitask-crews/crew-brainstorm-1812/br_nodes/`):
dimension keys are about 94% of node YAML bytes at every depth. The count grows
monotonically: n000 has 32 keys (5 KB), n009 has 148 (139 KB), and n014 has 174
(201 KB of 214 KB). n014 keeps all 171 keys of its parent n013 and adds 3. The
session-wide `active_dimensions` list in `br_graph_state.yaml` has grown to 141 entries.

Why it only grows:
- No code copies dimensions from parent to child. The agent re-emits every key in its
  `NODE_YAML` block, and the templates require it: `templates/explorer.md:47-49,162`
  and `templates/synthesizer.md:72` both say "Every dimension from the baseline node
  must appear — never silently drop one".
- The explorer input lists every baseline key
  (`brainstorm_crew.py` "## Dimension Keys", around `:251-257`) and the
  `active_dimensions` list ("## Active Dimensions", around `:607-615`).
- `_merge_new_dimensions` (`brainstorm_session.py:952`) only appends to
  `active_dimensions`.
- Nothing removes dimensions. `update_node` (`brainstorm_dag.py:116`) only merges.

## Goal

Add a brainstorm operation, "prune dimensions", that creates a new node with fewer
dimensions. The op wizard offers two modes:
1. **Keep top N**: keep the N highest-ranked dimensions (N is entered in the wizard).
2. **Keep selected**: keep exactly the dimensions the user checks in the wizard.

## Design notes (from exploration)

- **Nodes are immutable.** Every op adds a child node, so prune must create a child
  node (`parents=[source]`, same `module_label`) and move that subgraph's HEAD to it.
  It must not edit the source node.
- **Deterministic, no agent.** Follow the existing deterministic path that creates a
  node directly: `module_decompose` "from sections"
  (`brainstorm_app.py` around `:5402-5418` →
  `apply_module_decompose_from_sections`, `brainstorm_session.py:1328-1406`). That path
  does `record_operation(agents=[])` → `next_node_id` → `create_node` → `set_head` →
  `update_operation(status="Completed")`. It already filters source dimension keys
  against a kept set, including glob tags (`:1363-1370`). Keep the `n###_` node-id
  prefix, because `_node_id_ordinal` (`brainstorm_dag.py:423`) parses it.
- **Proposal markdown must be rewritten.** Proposal sections carry
  `<!-- section: name [dimensions: k1, k2|prefix_*] -->` tags (parser:
  `brainstorm_sections.py`). n014 has 55 sections and 181 tags. If only the YAML keys
  are deleted, exact-key tags point at keys that no longer exist: `validate_sections(...,
  node_keys=...)` then fails a later from-sections decompose, and the
  dimension-to-section navigation goes stale. The minimum fix, which needs no agent, is
  to drop pruned exact keys from the open markers; glob tags can stay. Planning must
  decide what happens to sections whose every tag gets pruned (for example the leaf
  `component_<name>` sections): keep the prose, or remove the section. Note that
  `finalize` exports only the HEAD proposal `.md` (`brainstorm_session.py:375`), so the
  pruned proposal is what ships.
- **`active_dimensions` policy.** The list is session-wide and other branches use it.
  If it is not trimmed, later explores get the pruned keys in their input again and may
  bring them back. Planning must decide whether to trim it, or whether the explorer
  input should take keys from the baseline node rather than the session list. Also
  check whether the explorer/synthesizer "never drop" rules still hold once a node has
  been pruned on purpose. They should hold relative to the pruned baseline.
- **"Top N" needs a ranking signal.** None exists today. The only scores are the
  comparator's optional metric and `utils.py` `compare_matrix_rows` similarity.
  Deterministic candidates: membership in `active_dimensions`, how many proposal
  sections reference the key (`get_sections_for_dimension`), mentions in the proposal
  prose, and prefix order. An agent-ranked mode is a possible later extension. Planning
  should choose and document the ranking, and the wizard should show the resulting
  kept/dropped list before confirm. A possible combination: top N per prefix, or top N
  overall with the selected list pre-checked so the user can adjust it.
- **Wizard UI reuse.** The Compare config already builds a grouped dimension checklist:
  a `FuzzyCheckList` (`widgets.py:306`, `set_grouped_items`), filled by
  `_refresh_compare_dimensions` (`brainstorm_app.py:1438`) from
  `_dimension_entries_for_nodes`, with labels parsed by `_parse_dimension_label`
  (`utils.py:87`). Reuse it for one node. Add a mode selector and an N input
  (`CycleField`, `widgets.py:697`), and show the kept/dropped summary in
  `_build_summary`.

## Inventories a new op must be added to

- `constants.py`: `_DESIGN_OPS`, `_OP_LABELS`, `_OPERATION_HELP`,
  `_WIZARD_OP_TO_AGENT_TYPE` (or confirm the fallback for a no-agent op), the
  node-select sets, `_WIZARD_STEPS` (the `config` step's hard-coded op tuple), and the
  cardinality sets (`_SINGLE_NODE_OPS`). Without a cardinality set,
  `op_states_for_selection` (`utils.py:407`) never greys the op out.
- `brainstorm_schemas.py` `GROUP_OPERATIONS`
- `brainstorm_dag_display.py` `OP_BADGE_STYLES`
- `modals.py` `NodeActionSelectModal._OPS`
- `brainstorm_op_refs.py`, if needed (`list_op_inputs` already returns `[]` for groups
  with no agents)
- `brainstorm_app.py` `ActionsWizardScreen.on_mount` routing,
  `_actions_show_config` / `_config_<op>`, `_actions_collect_config`,
  `_build_summary`, and the `_run_design_op` dispatch

Tests that enumerate ops and need updating: `tests/test_brainstorm_node_action_modal.py`
(exact `_OPS` order), `tests/test_brainstorm_dag_op_badge.py`,
`tests/test_brainstorm_session_tab.py`, `tests/test_brainstorm_node_action_relevance.py`,
`tests/test_brainstorm_wizard_steps.py`. Model the new logic tests on
`tests/test_brainstorm_apply_module_ops.py`, `test_brainstorm_dag.py` and
`test_brainstorm_sections.py`. They should cover: the source node is unchanged; the
child has exactly the kept keys plus the structural fields; the section tags are
rewritten and `validate_sections(node_keys=...)` passes on the child; HEAD moves; the
`active_dimensions` policy is applied.

## Docs

- `website/content/docs/tuis/brainstorm/reference.md`: op colour legend,
  "Operations and agents" table, and the decompose-modes text ("forks rather than
  prunes").
- `website/content/docs/tuis/brainstorm/how-to.md`: add a "How to prune dimensions"
  section.
- `aidocs/brainstorming/brainstorm_engine_architecture_v2.md`: `active_dimensions`
  growth and the never-drop rules.
- Run `website/check_links.py --build` after editing the website.

## Out of scope / follow-ups

- Agent-based pruning that also rewrites the proposal prose about the pruned dimensions.
- An `ait brainstorm prune` CLI verb. No design op has a CLI verb today; a deterministic
  core makes adding one easy later.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-14T15:59:43Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-14T19:21:22Z status=pass attempt=1 type=human
