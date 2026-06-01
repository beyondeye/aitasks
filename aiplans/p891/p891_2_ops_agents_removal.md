---
Task: t891_2_ops_agents_removal.md
Parent Task: aitasks/t891_brainstorm_proposal_only_retire_plans.md
Sibling Tasks: aitasks/t891/t891_1_decision_docs_v2_architecture.md, aitasks/t891/t891_3_schema_data_tui_cleanup.md, aitasks/t891/t891_4_finalize_proposal_export.md
Worktree: (decide at pick time)
Branch: aitask/t891_2_ops_agents_removal
Base branch: main
---

# Plan — t891_2: retire detail/patch ops + detailer/patcher agents

> **⚠️ DEFERRED — gated on the t756 chain. Re-verify every anchor against the
> as-landed codebase (2026-06-01 pre-modules snapshot — line numbers WILL
> drift; locate by symbol name).** By execution time the module ops exist (built
> from detail/patch as the model), so this is pure removal, not a port.

## Code anchors (2026-06-01 snapshot — verify by name)

`.aitask-scripts/brainstorm/brainstorm_schemas.py`
- `GROUP_OPERATIONS` (~L56) — remove `"detail"`, `"patch"`.

`.aitask-scripts/brainstorm/brainstorm_app.py`
- `_NODE_SELECT_OPS` (~L138), `_WIZARD_OP_TO_AGENT_TYPE` (~L140, detail→detailer/
  patch→patcher), `_DESIGN_OPS` (~L191), `_OPERATION_HELP` (~L222; detail ~L331,
  patch ~L361).
- `_execute_design_op` (~L6243) — detail branch (~L6309 register_detailer +
  ~L6317 target wiring), patch branch (~L6323 register_patcher + ~L6331 source
  wiring).
- Poll infra: `_ensure_detailer_poll_timer`(~L4448), `_stop_detailer_poll_timer`
  (~L4455), `_poll_detailers`(~L4511), `_try_apply_detailer_if_needed`(~L4550),
  `_scan_existing_detailers`(~L4463); patcher equivalents
  `_ensure_patcher_poll_timer`(~L3909), `_stop_patcher_poll_timer`(~L3916),
  `_poll_patchers`(~L3970), `_try_apply_patcher_if_needed`(~L4009). State:
  `_detailer_targets`/`_detailer_poll_timer`(~L2888/2891),
  `_patcher_sources`/`_patcher_poll_timer`(~L2865/2868) + inits.
- The `_wizard_op == "detail"` confirm step (~L5628). (The patch-wizard
  `_node_has_plan` gate ~L5617 becomes dead — removed in t891_3.)

`.aitask-scripts/brainstorm/brainstorm_crew.py`
- `register_detailer`(~L632), `register_patcher`(~L673),
  `_assemble_input_detailer`(~L366), `_assemble_input_patcher`(~L415);
  `BRAINSTORM_AGENT_TYPES`(~L45) detailer/patcher keys. The comparator's
  `read_plan` use (~L311) — drop only that dead read (symbol removed in t891_3).

`.aitask-scripts/brainstorm/brainstorm_session.py`
- `apply_detailer_output`(~L1159), `apply_patcher_output`(~L719),
  `_detailer_needs_apply`(~L1118), `_patcher_needs_apply`(~L603),
  `_parse_patcher_output`(~L658), `_write_patcher_plan_file`(~L706),
  `_DETAILER_DELIMITERS`(~L1115), `_PATCHER_DELIMITERS`(~L498).

`.aitask-scripts/brainstorm/brainstorm_dag_display.py`
- `OP_BADGE_STYLES`(~L59) — remove detail(~L61)/patch(~L62).

Delete: `.aitask-scripts/aitask_brainstorm_apply_detailer.sh`,
`.aitask-scripts/aitask_brainstorm_apply_patcher.sh`,
`.aitask-scripts/brainstorm/templates/detailer.md`,
`.aitask-scripts/brainstorm/templates/patcher.md`.

## Preserve
Section/dimension machinery (t873, shared with proposals); explore/compare/
synthesize; the `plan_file`/`read_plan`/`PLANS_DIR`/Plan-tab/badge removal is
t891_3 (don't pre-empt — remove only the detail/patch consumers here).

## Steps
1. Verify symbol inventory against as-landed code (t756 may add module-op badge
   styles — leave those).
2. Remove ops from `GROUP_OPERATIONS`; then dispatch/wizard/poll infra in
   `brainstorm_app.py`; then crew registrations; then session apply fns; then
   badges/templates/helper scripts.
3. grep residual `detail`/`patch`/`detailer`/`patcher`; clean dead imports.

## Verification
- `grep -rn "detailer\|patcher\|\"detail\"\|\"patch\"" .aitask-scripts/brainstorm/`
  — only intentional matches.
- `.py` files parse; brainstorm tests pass.
- Manual `ait brainstorm`: menu has no Detail/Patch; explore/compare/synthesize
  work; no poll-timer errors.
