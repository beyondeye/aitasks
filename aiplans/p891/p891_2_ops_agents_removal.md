---
Task: t891_2_ops_agents_removal.md
Parent Task: aitasks/t891_brainstorm_proposal_only_retire_plans.md
Sibling Tasks: aitasks/t891/t891_3_schema_data_tui_cleanup.md, aitasks/t891/t891_4_finalize_proposal_export.md
Archived Sibling Plans: aiplans/archived/p891/p891_1_decision_docs_v2_architecture.md
Worktree: (current branch — profile 'fast')
Branch: main (current branch)
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-11 10:46
---

# Plan — t891_2: retire detail/patch ops + detailer/patcher agents

## Context

`ait brainstorm` is being simplified to a **proposal-only** design engine (parent
t891). The implementation-**plan** layer is retired and its value absorbed into the
**module** architecture from t756 (now landed). This child removes the first slice:
the `detail` and `patch` operations and the `detailer`/`patcher` agents that back
them. `ait brainstorm` is unshipped → remove outright, no back-compat.

**Gate status (re-verified 2026-06-11):** t756 is **archived (landed)** and t891_1
is **archived** — the deferral condition is satisfied. Module ops
(`module_decompose`/`module_merge`/`module_sync`) exist in `GROUP_OPERATIONS` and
have their **own fully separate infrastructure** (own agent types, `register_module_*`,
`_assemble_input_module_*`, templates, and a distinct `_module_poll_timer` /
`_poll_module_agents` chain). They do **not** share detailer/patcher poll/registration
code. So this is **pure removal, not a port** — confirmed.

## ⚠️ Verify-pass findings — anchors the 2026-06-01 snapshot MISSED

This plan's original anchor list was a useful skeleton but is materially incomplete
against the as-landed (post-t756) code. New/changed anchors found during
re-verification:

- **`ait` dispatcher** (NEW): lines 258–259 route `apply-patcher`/`apply-detailer`
  to the scripts being deleted; lines 274–275 (help) and 282 (error list) reference
  them. Must be removed or they `exec` deleted scripts.
- **`brainstorm_op_refs.py`** (NEW t756 file): `_OP_INPUT_SECTION` has `"detail": None`
  and `"patch": "Patch Request"` (lines 21–22).
- **`brainstorm_session.py` `_agent_to_group_name`**: `role_to_group` map has
  `"patcher": "patch"` and `"detailer": "detail"` keys (~611, 614).
- **app.py retry surface**: `ctrl+shift+r`/`ctrl+shift+d` bindings (3514–3521) +
  `action_retry_patcher_apply` (4987) / `action_retry_detailer_apply` (5823).
- **app.py state/widgets**: `_applying_patcher`/`_applying_detailer`,
  `_patcher_apply_errors`/`_detailer_apply_errors`, `_register_patcher_source` /
  `_register_detailer_target`, `_scan_existing_patchers`/`_scan_existing_detailers`,
  `patcher_impact_banner` widget (3697, 4973, 4981).
- **app.py wizard gates**: `config` `_WizardStep` tuple lists `"patch"` (~1966);
  node-select step labels (6937–6938), patch-unavailable disable (6981–6983),
  patch-no-plan guard (7009–7011), `_on_patch_request_changed`/`.ta_patch_request`
  (7982), `_config_patch_no_node` (7416).

### Shared-helper TRAPS — do NOT remove (would break explore/synthesize)

- **`_pick_completed_agent_for_retry(role)`** (app.py 5457) is **shared** — called by
  patcher, **explorer**, **synthesizer**, detailer. Remove only the patcher/detailer
  *callers*; keep the method.
- **`_PATCHER_INPUT_META_RE`** (app.py 4818): despite the name, it is consumed inside
  the shared `_pick_completed_agent_for_retry` (5503), so explorer/synthesizer retry
  depend on it. **KEEP it.**

### Grep false-positive TRAP

`grep detail` floods with **node-detail / op-detail UI** that is unrelated to the
`detail` op and must be preserved: `node_detail*`, `op_detail*`, `detail_pane`,
`dag_detail_pane`, `_show_node_detail`, `_render_node_detail_widgets`,
`status_agent_detail`, `delete_details`, `open_node_detail`, `"Open detail"`. Match by
OP semantics, not bare substring.

## Out of scope (sibling boundaries — do NOT pre-empt)

- `plan_file` field, `read_plan`/`PLANS_DIR`/`br_plans/`, NodeDetail **Plan tab**,
  `l`/`V` plan bindings, plan **badges**, and the patch-wizard `_node_has_plan` gate
  **machinery** → **t891_3**. Here we remove only the detail/patch *consumers*.
  - The op-availability dict entry `"patch": (not self._node_has_plan(node_id), ...)`
    (app.py 4117) is removed here because the `patch` op is going away; `_node_has_plan`
    itself stays for t891_3.
- Preserve all t873 section-marker / dimension-link machinery (shared with proposals)
  and the `explore` / `compare` / `synthesize` ops + agents.

## Removal inventory (by file — locate by symbol, line numbers are approximate)

### `brainstorm_schemas.py`
- `GROUP_OPERATIONS` (78): remove `"detail"` (82), `"patch"` (83). Keep module ops.

### `brainstorm_op_refs.py`
- `_OP_INPUT_SECTION` (15): remove `"detail"`/`"patch"` entries (21–22). Leave
  `node_plan` kind / `PLANS_DIR` import (t891_3).

### `brainstorm_app.py`
- Imports: `register_detailer` (104), `register_patcher` (109).
- `_NODE_SELECT_OPS` (158) → `{"explore"}` (drop detail/patch). Derived sets
  `_NODE_SELECT_STEP_OPS`/`_SUBGRAPH_SELECT_OPS` then resolve correctly.
- `_WIZARD_OP_TO_AGENT_TYPE` (171–172); `_DESIGN_OPS` (225–226); `_OPERATION_HELP`
  detail (364) + patch (394) entries and their source-trace comments (359, 389–393).
- `config` `_WizardStep` tuple: drop `"patch"` (~1966).
- Op list `("explore","detail","patch","fast_track",...)` (2390) and `op_key=="patch"`
  branch (2433) — drop detail/patch.
- Op-availability dict `"patch": (...)` entry (4117).
- Retry: bindings ctrl+shift+r/ctrl+shift+d (3514–3521); `action_retry_patcher_apply`
  (4987); `action_retry_detailer_apply` (5823).
- State inits: `_patcher_sources`/`_applying_patcher`/`_patcher_apply_errors`/
  `_patcher_poll_timer` (3572–3575); detailer equivalents (3595–3598). `patcher_impact_banner`
  widget (3697) + its updates (4973, 4981).
- Poll/apply infra: `_register_patcher_source`, `_ensure/_stop_patcher_poll_timer`,
  `_scan_existing_patchers`, `_poll_patchers`, `_try_apply_patcher_if_needed`
  (4822–5009); `_scan_existing_patchers()`/`_scan_existing_detailers()` calls in
  `on_mount` (4756, 4759); detailer equivalents `_register_detailer_target`,
  `_ensure/_stop_detailer_poll_timer`, `_scan_existing_detailers`, `_poll_detailers`,
  `_try_apply_detailer_if_needed` (5670–5844).
- Wizard: node-select labels (6937–6938), patch-unavailable disable (6981–6983),
  patch-no-plan guard (7009–7011), `_wizard_op=="detail"` (7027), `_config_patch_no_node`
  dispatch + method (7094, 7416) + `.ta_patch_request` TextArea, confirm text (7880–7885),
  Next-button routing (7964–7982), `_on_patch_request_changed` (7982).
- `_execute_design_op` detail branch (8156: `register_detailer` + `_register_detailer_target`
  wiring) and patch branch (8170: `register_patcher` + `_register_patcher_source` wiring).
- **KEEP:** `_pick_completed_agent_for_retry`, `_PATCHER_INPUT_META_RE`, all explorer/
  synthesizer/module infra, all node-detail/op-detail UI.

### `brainstorm_crew.py`
- `BRAINSTORM_AGENT_TYPES` (48): remove `"detailer"` (52), `"patcher"` (53) keys.
- `register_detailer` (830), `register_patcher` (871), `_assemble_input_detailer` (397),
  `_assemble_input_patcher` (447).
- Comparator dead read: the `plan_text = read_plan(...)` block + its `if plan_text:`
  body (281–289). Drop the now-unused `read_plan` import (40) **only if** no other crew
  consumer remains (the `read_plan` symbol itself stays in `brainstorm_dag.py` for t891_3).

### `brainstorm_session.py`
- `apply_detailer_output` (1808), `apply_patcher_output` (768), `_detailer_needs_apply`
  (1767), `_patcher_needs_apply` (652), `_parse_patcher_output` (707),
  `_write_patcher_plan_file` (755), `_DETAILER_DELIMITERS`/`_PATCHER_DELIMITERS` constants.
- `_agent_to_group_name` `role_to_group`: drop `"patcher"`/`"detailer"` keys (611, 614).
  Keep explorer/synthesizer/module keys.

### `brainstorm_dag_display.py`
- `OP_BADGE_STYLES` (60): remove `"detail"` (65), `"patch"` (66). Keep module badges.

### `ait` (dispatcher)
- Remove `apply-patcher` (258) + `apply-detailer` (259) cases, their help lines
  (274–275), and references in the unknown-subcommand error list (282).

### Delete files
- `.aitask-scripts/aitask_brainstorm_apply_detailer.sh`
- `.aitask-scripts/aitask_brainstorm_apply_patcher.sh`
- `.aitask-scripts/brainstorm/templates/detailer.md`
- `.aitask-scripts/brainstorm/templates/patcher.md`

### Tests
- **Delete** (test removed features): `tests/test_brainstorm_apply_detailer.py`,
  `tests/test_brainstorm_apply_detailer_cli.sh`, `tests/test_brainstorm_apply_patcher.py`,
  `tests/test_brainstorm_apply_patcher_cli.sh`.
- **Inspect & update** (assertions on detail/patch that should drop): `test_brainstorm_op_refs.py`,
  `test_brainstorm_wizard_steps.py`, `test_brainstorm_crew.py`,
  `test_brainstorm_node_action_modal.py`, `test_brainstorm_node_action_relevance.py`,
  `test_crew_template_includes.sh`, `test_brainstorm_apply_created_by_group.sh`,
  `test_brainstorm_group_progress_aggregate.sh`, `test_brainstorm_groups_persist.py`.
  (Other grep hits — `test_setup_python_install.sh`, `test_skill_render_task_workflow.sh`,
  task-workflow goldens, etc. — are unrelated `patch` substrings; confirm and leave.)

## Implementation order

1. `GROUP_OPERATIONS` + `_OP_INPUT_SECTION` (data sources of truth) first.
2. `brainstorm_app.py`: op maps → wizard gates → dispatch (`_execute_design_op`) →
   poll/apply/retry infra → state inits/widgets. Remove imports last.
3. `brainstorm_crew.py` registrations + assemblers + comparator dead read.
4. `brainstorm_session.py` apply fns + helpers + role map.
5. `brainstorm_dag_display.py` badges; `ait` dispatcher; delete templates + helper scripts.
6. Tests: delete the 4 dedicated tests, update the assertion tests.
7. grep sweep for residual live wiring; clean dead imports.

## Verification

- `grep -rn 'detailer\|patcher\|"detail"\|"patch"' .aitask-scripts/brainstorm/` — only
  intentional matches (node-detail UI, the kept `_PATCHER_INPUT_META_RE`, docstring
  examples like `n012_patcher`), no live op wiring.
- `python -c "import ast,glob;[ast.parse(open(f).read()) for f in glob.glob('.aitask-scripts/brainstorm/*.py')]"`
  parses cleanly; no NameError from removed symbols (grep for each removed symbol's
  remaining references before declaring done).
- `bash tests/test_no_raw_tmux.sh`-style: run the updated/kept brainstorm tests
  (`test_brainstorm_op_refs.py`, `test_brainstorm_wizard_steps.py`, `test_brainstorm_crew.py`,
  node-action tests) — all pass.
- `ait brainstorm --help` no longer lists apply-patcher/apply-detailer; `ait brainstorm
  apply-patcher` errors as unknown subcommand.
- `shellcheck` clean on the modified `ait` dispatcher.
- Manual (`ait brainstorm <num>`): operation menu has no Detail/Patch; explore/compare/
  synthesize and module ops still work; no poll-timer errors in logs.

## Risk

### Code-health risk: medium
- Wide multi-site deletion across the brainstorm subsystem (6 `.py` files + `ait` +
  4 deleted files + tests). A naive grep-and-delete would (a) strip the shared
  `_pick_completed_agent_for_retry` / `_PATCHER_INPUT_META_RE` that `explore`/
  `synthesize` retry depend on, or (b) delete node-detail/op-detail UI caught as
  grep false-positives — either breaks kept functionality. · severity: medium ·
  → mitigation: in-task (per-symbol KEEP markers in plan; AST-parse + targeted grep
  sweep for each removed symbol's residual refs; run kept brainstorm tests before done)
- Removing a dispatch/op entry while leaving a dangling reference (e.g. `ait` case
  vs. deleted script, or an op-list literal) yields a runtime NameError/exec failure
  only hit at use time. · severity: low · → mitigation: in-task (AST parse all
  brainstorm `.py`; `ait brainstorm --help` + unknown-subcommand check; shellcheck)

### Goal-achievement risk: low
- None identified. Approach re-verified (modules carry their own infra; pure removal),
  inventory expanded to cover the snapshot's gaps, sibling boundaries (t891_3) explicit.

## Post-implementation

Follows shared workflow **Step 8** (user review/approval) → **Step 9** (archival via
`./.aitask-scripts/aitask_archive.sh 891_2`). Record sibling-relevant notes in the
plan's Final Implementation Notes — t891_3 builds directly on this (plan_file/read_plan
removal), so flag any anchors it should re-verify.
