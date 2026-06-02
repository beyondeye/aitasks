---
Task: t756_4_phase_c_sync_op.md
Parent Task: aitasks/t756_brainstorm_modules.md
Sibling Tasks: aitasks/t756/t756_5_phase_d1_status_views.md, aitasks/t756/t756_6_phase_d2_fast_track_preset.md, aitasks/t756/t756_7_manual_verification_brainstorm_modules.md
Archived Sibling Plans: aiplans/archived/p756/p756_1_phase_a_data_model.md, aiplans/archived/p756/p756_2_phase_b1_module_aware_wizard_infra.md, aiplans/archived/p756/p756_3_phase_b2_decompose_merge_ops.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-02 12:17
---

# t756_4 — Phase C: `module_sync` op (VERIFIED & UPDATED 2026-06-02)

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.3 sync, §5 "sync scan engine", §6 sync defaults, §7 Phase C).
**Binding conventions:** `aiplans/p756_brainstorm_modules.md`. **Depends on:** t756_3 (landed/archived).

## Context

Once a brainstorm module is fast-tracked into a real aitask and code lands, the
brainstorm subgraph still holds the *original* refined design while the aitask's
plan accrues `## Final Implementation Notes` / `## Post-Review Changes`, and
unrelated follow-ups may touch the same files. `module_sync` reconciles that
drift into a new subgraph HEAD so a later `module_merge` absorbs current reality,
not a stale design. Sync is **read-only** on the aitask side. The heavy scan
engine already exists (t369's `aitask_explain_context.sh` family) — this task is
glue + template + wizard plumbing modelled on the `module_merge` op that t756_3
landed.

## Verification findings (this is the VERIFY path — what changed since the plan was written)

t756_1/2/3 have all landed. The plan's approach holds, but three concrete
corrections against the as-landed code:

1. **No `linked_task` field exists.** Phase A shipped a `module_tasks` map
   (`<module>:<task_id>`) in `br_graph_state.yaml`
   (`brainstorm_schemas.py:48 GRAPH_STATE_MODULE_MAPS`). "Refuse if no
   `linked_task`" ⇒ **refuse if `module_tasks` has no entry for the chosen
   subgraph.** Reuse the existing getter `_module_tasks_map(wt)`
   (`brainstorm_session.py:1223`). `last_synced_at` map already exists and is
   seeded `{}` by `init_session` (`brainstorm_session.py:133`).
2. **Auto-apply is poller-driven** (t756_3). Module agents launch interactively,
   write `<agent>_status.yaml`, and a background poller applies their output.
   `module_sync` must hook the same three sites — the original plan did not
   mention this layer.
3. **`module_sync` emits a single node** (like `module_merger`: `NODE_YAML` +
   `PROPOSAL`), so its `needs_apply` is the `_explorer_needs_apply` alias and its
   apply mirrors `apply_module_merger_output` — but single-parent (the module's
   own prior HEAD) and additionally stamps `last_synced_at`.

## IMPORTANT — `module_` prefix (binding, do NOT re-litigate)
op-key `module_sync`; wizard label "Module Sync"; agent type `module_syncer`;
template `templates/module_syncer.md`; register fn `register_module_syncer()`;
input section "Sync Sources".

## v1 decided defaults (design doc §6 — do NOT re-litigate)
- Refuse `module_sync` on a subgraph with **no `module_tasks` entry** (free-form
  context is `patch`'s job).
- Sync scan **radius** = exact-file-match to the linked task's touched files.
- Sync scan **time horizon** = "since last sync" via `last_synced_at[<module>]`.
- No sync-then-merge fusion (merge stays separately reviewable).

## Implementation

### 1. Schema + op-refs (one line each)
- `brainstorm_schemas.py:73 GROUP_OPERATIONS` += `"module_sync"` (after `module_merge`).
- `brainstorm_op_refs.py:16 _OP_INPUT_SECTION` += `"module_sync": "Sync Sources"`.

### 2. Crew (`brainstorm_crew.py`)
- `BRAINSTORM_AGENT_TYPES` (line 55–56) += `"module_syncer": {"max_parallel": 1, "launch_mode": "interactive"}`.
- `_assemble_input_module_syncer(session_path, module, source_head, assigned_node_id, sync_bundle, instructions)`
  — model on `_assemble_input_module_merger` (line 547). Sections: Source
  Subgraph, Source HEAD + node files, Assigned Node ID, **Sync Sources** (the
  bundled three streams), optional user instructions.
- `register_module_syncer(session_dir, crew_id, module, group_name, max_plans=N, instructions="", launch_mode=...)`
  — model on `register_module_merger` (line 882):
  1. `tasks = _module_tasks_map(session_dir)`; `task_id = tasks.get(module)`; if
     falsy → `raise ValueError("module_sync requires a linked task; "<module>" has no module_tasks entry")`.
  2. **Read the linked task plan.** Resolve child plan path
     `aiplans/p<parent>/p<parent>_<child>_<name>.md` (live) →
     `aiplans/archived/p<parent>/...` (after archival). Glob by `p<id>_*`.
     Emphasize the `## Final Implementation Notes` / `## Post-Review Changes`
     sections in the bundle.
  3. **Scoped git diff.** Touched files via
     `git log --grep "(t<task_id>)" --name-only` then `git diff` per file. Scope
     by horizon: append `--since "<last_synced_at[module]>"` when present (first
     sync = full task history). The `(t<id>)` grep convention matches
     `aitask_issue_update.sh:271` (parens delimit so `(t905)` ≠ `(t905_1)`).
  4. **Shell out** to `./.aitask-scripts/aitask_explain_context.sh --max-plans <N> <files>`
     and capture stdout. **REUSE — never fork the helper family.** Run via
     `subprocess.run` from the repo root (pattern already used elsewhere in
     crew/session for `aitask_create.sh`).
  5. Bundle the three streams into the agent input via `_assemble_input_module_syncer`.
  6. Reserve `assigned_node_id` (`next_node_id`), `_run_addwork(..., "module_syncer", ...)`,
     `_write_agent_input`, return `agent_name`.

### 3. Session apply (`brainstorm_session.py`)
- `_module_syncer_needs_apply(task_num, agent_name)` = alias of
  `_explorer_needs_apply` (single-node output), mirroring
  `_module_merger_needs_apply` (line 1217).
- `apply_module_syncer_output(task_num, agent_name)` — model on
  `apply_module_merger_output` (line 1461) but:
  - read `module` from the group's `subgraph` field;
  - `source_head = get_head(wt, module=module)`; parser sets
    `node_data["parents"] = [source_head]` (single parent — sync advances the
    module's own HEAD);
  - `_apply_node_output(... expected_role="module_syncer" ...)` advances that
    module's HEAD (its `set_head`/history append is handled by the shared apply
    helper, scoped to `module`);
  - after apply, stamp `last_synced_at[module] = <now>` via a new
    `_write_last_synced(wt, module, ts)` helper (mirror `_write_module_task`,
    line 1230); use the existing timestamp helper/format `YYYY-MM-DD HH:MM`;
  - `update_operation(..., status="Completed")`.

### 4. App wizard (`brainstorm_app.py`)
- Import `register_module_syncer` (near line 94).
- `_SUBGRAPH_SELECT_OPS` (line 146) += `"module_sync"` (subgraph selector, no
  node-select).
- `_WIZARD_OP_TO_AGENT_TYPE` (line 148) += `"module_sync": "module_syncer"`
  (this auto-wires `_brainstorm_launch_mode_default`).
- `_DESIGN_OPS` (line 201) += `("module_sync", "Module Sync", "Pull as-implemented design back into a linked module")`.
- `_OPERATION_HELP` (line 401) += `"module_sync"` entry (title/summary/
  reads_from_parent/produces/use_cases) — mirror the `module_merge` block.
- `OP_BADGE_STYLES` in `brainstorm_dag_display.py:60` += `"module_sync": Style(color="#FF79C6")` (pick an unused Dracula hue, e.g. pink/comment).
- `_config_design_op` dispatch (line 6068) += `elif op == "module_sync": self._config_module_sync(container)`.
- New `_config_module_sync(container)` — model on `_config_module_merge`
  (line 6250): show subgraph + its `module_tasks` id + `last_synced_at`
  (read-only labels); a "Sync Sources" instructions `TextArea`; optional
  max-plans field. **Disable Next** and show a warning when the selected
  subgraph has no `module_tasks` entry (mirror the no-ancestor guard).
- `_collect_config` (line 6409) += `module_sync` branch: set `subgraph`,
  validate `module_tasks` entry present (else `notify` + return False), collect
  instructions/max-plans.
- Confirm-summary `_build_*` (line 6559) += `module_sync` branch (subgraph,
  linked task, last_synced_at, instructions).
- `_run_design_op` (line 6844) += `elif op == "module_sync":` →
  `register_module_syncer(...)`, `agents_list.append(agent)`,
  `self.call_from_thread(self._register_module_agent, agent)`, set
  `operation_extra = {}` (subgraph already passed by `record_operation`).
  `subgraph`/`head_at_creation` already derive correctly via the
  `_SUBGRAPH_SELECT_OPS` branch (line 6762).
- Poller wiring (3 sites): add `("module_syncer_*_status.yaml", _module_syncer_needs_apply)`
  to the scan tuple (line 4413); add `module_syncer_` branches to
  `_module_agent_needs_apply` (line 4461) and `_try_apply_module_agent_if_needed`
  (line 4472, importing `apply_module_syncer_output`).

### 5. Template `templates/module_syncer.md`
Model on `templates/module_merger.md`. Input: source subgraph + HEAD node files,
assigned node id, and the **Sync Sources** bundle (linked-task plan w/ Final
Implementation Notes + Post-Review Changes, scoped git diff, explain-context
markdown). Output: single `NODE_YAML` + `PROPOSAL` (parents `[]`, orchestrator
overwrites to `[source_head]`). Rules: refine the module proposal to reflect the
*as-implemented* state; note where reality diverged from the original design.

## Reusable helper interface (CLAUDE.md "Reusable Helpers")
`aitask_explain_context.sh --max-plans N <file1> [file2...]` → formatted markdown
on stdout. Family: `aitask_explain_context.sh`,
`aitask_explain_extract_raw_data.sh`, `aitask_explain_format_context.py`,
`aitask_explain_process_raw_data.py`, `aitask_explain_runs.sh`,
`aitask_explain_cleanup.sh`. **Consume via shell-out only — do not fork.**

## Reference patterns (read before implementing)
- `brainstorm_crew.py::register_module_merger` (882) + `_assemble_input_module_merger` (547).
- `brainstorm_session.py::apply_module_merger_output` (1461), `_module_tasks_map` (1223), `_write_module_task` (1230).
- `brainstorm_app.py` module_merge sites: `_config_module_merge` (6250), `_collect_config` (6442), summary (6572), `_run_design_op` (6883), poller (4400–4500).
- `aitask_issue_update.sh:267-273` for the `(t<id>)` commit-grep convention.

## Verification
- `module_sync` **refuses** a subgraph whose module has no `module_tasks` entry
  (wizard disables Next; `register_module_syncer` raises).
- On a linked module it bundles plan + scoped diff + explain-context and produces
  a single synced node that becomes the module's new HEAD (single parent =
  prior HEAD).
- `last_synced_at[<module>]` advances after apply so a re-sync's `--since`
  horizon only picks up genuinely-newer commits.
- The `aitask_explain_*` family is unmodified (shell-out only).
- Op badge renders for `module_sync` nodes; launch-mode default resolves via the
  agent type.
- Existing brainstorm tests still pass (run the brainstorm test suite, e.g.
  `bash tests/test_brainstorm_*.sh` and `tests/test_brainstorm_module_ops_integration.py`).

## Step 9 (Post-Implementation)
Follow task-workflow Step 9: review, commit (`feature: … (t756_4)`), consolidate
this plan with Final Implementation Notes (syncer input-bundle shape + notes for
Phase D), archive via `./.aitask-scripts/aitask_archive.sh 756_4`.
