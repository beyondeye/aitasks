---
Task: t756_2_phase_b1_module_aware_wizard_infra.md
Parent Task: aitasks/t756_brainstorm_modules.md
Sibling Tasks: aitasks/t756/t756_3_phase_b2_decompose_merge_ops.md, aitasks/t756/t756_4_phase_c_sync_op.md, aitasks/t756/t756_5_phase_d1_status_views.md, aitasks/t756/t756_6_phase_d2_fast_track_preset.md, aitasks/t756/t756_7_manual_verification_brainstorm_modules.md
Archived Sibling Plans: aiplans/archived/p756/p756_1_phase_a_data_model.md, .aitask-data/aiplans/archived/p898_refactor_brainstorm_wizard_step_machine.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-02 09:47
---

# t756_2 — Phase B1: module-aware wizard infrastructure (re-planned on t898 step model)

## Context

`ait brainstorm` makes existing ops (`explore`, `compare`, `synthesize`,
`detail`, `patch`) target the single session HEAD. Phase A (t756_1, DONE) landed
the additive, back-compatible data model: `module_label` on nodes, a
`current_heads` map, `get_head/set_head(module=...)`, and the `_node_module` /
`_subgraph_root` / `is_ancestor_subgraph` helpers in `brainstorm_dag.py`. **No op
consumes any of it yet.** This task (design doc §4.5 "existing ops become
module-aware") makes those ops subgraph-scoped and adds the shared
**subgraph-selector** wizard step the new ops (B2, t756_3) reuse.

**Why this was re-planned.** The task was paused/reverted once: inserting the
selector into the old **integer-indexed** `_wizard_step` machine fought ~6
hardcoded handlers. That machine was refactored first under **t898 (DONE,
commit 188d3e6f)** into a declarative step table + pure resolver. The old plan's
entire "Design decisions §1" (conditional pre-step + manual Back/Esc wiring) is
**obsolete** and is replaced below by t898's single-row model. t898's Final
Implementation Notes include an explicit "Notes for the gated resumer (t756_2)"
recipe — this plan follows it.

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
§4.5 (the four scope items), §4.6 (worked example — exploring inside a subgraph
advances *that* subgraph's head), §7 Phase A/B. **Binding conventions:**
`aiplans/p756_brainstorm_modules.md`. **TUI rules:** `aidocs/tui_conventions.md`.

## Plan verification (2026-06-02, verify path)

Re-verified every anchor against **live source** (the old plan's anchors all
pre-dated t898 and are stale). Current anchors:

- **`brainstorm_app.py`** — declarative step model present:
  `_NODE_SELECT_OPS = {"explore","detail","patch"}` (139); `_WizardStep` (1510);
  `_WIZARD_STEPS` (1516) **with the `subgraph_select` row already present but
  commented out** (1518-1523); resolvers `active_step_ids` (1541),
  `step_position` (1546), `next_step_id` (1558), `prev_step_id` (1567);
  `_filter_labels` pure-helper precedent (1485). App wiring: `_wizard_ctx`
  (5600, **I/O-free**), `_enter_wizard_step` (5607), `_render_wizard_step`
  (5614, id→renderer map), `_actions_show_step1` (5485), `_actions_show_step2`
  (5627, the op_select→next fork), `_actions_show_node_select` (5634, lists
  **all** `list_nodes()` unfiltered at 5660, `get_head` unscoped at 5661),
  `_actions_advance_from_node_select` (5694), `_run_design_op` (6330:
  `head_at_creation = get_head(self.session_path)` 6338, `record_operation(...)`
  6415). Dispatch is **resolver-driven**: Esc (3189) + Back (6206) call
  `prev_step_id`; Next (6213) dispatches on `_wizard_step_id`. Op_select advances
  via `_actions_show_step2()` from exactly **two** sites — Enter (3210) and
  mouse click (6281). Up/down OperationRow nav gates on `_wizard_step_id in
  ("op_select","node_select")` (3250). dag imports at 47-56 (need
  `_node_module`, `UMBRELLA_SUBGRAPH`, `list_subgraphs` added).
- **`brainstorm_dag.py`** — `UMBRELLA_SUBGRAPH` (30); module-aware `get_head`
  (127) / `set_head` (147); `current_heads` map (keys = subgraph names);
  `_node_module` (217); `create_node(...)` (38) has **no** `module_label` param;
  node ids are `f"n{num:03d}_{agent}"` (crew 531/616/700). **`list_subgraphs`
  does NOT exist — must add.**
- **`brainstorm_schemas.py`** — `GROUP_REQUIRED` (65), `GROUP_OPERATIONS` (69).
  **There is NO group validator and NO `GROUP_OPTIONAL`** — `GROUP_REQUIRED` is
  referenced by no validation code (only a test enumerates `GROUP_OPERATIONS`).
  The old plan's "wire `subgraph` into the group validator" is **moot** — no
  validator exists. (`record_operation` writes the group dict directly.)
- **`brainstorm_session.py`** — `record_operation(task_num, group_name,
  operation, agents, head_at_creation)` (220) writes the dict directly, no
  validation. The **apply/ingest** path creates nodes via `create_node(...)`
  (979) then `set_head(wt, new_node_id)` **unscoped** (993).
- **`brainstorm_crew.py`** — `_assemble_input_*` builders (explorer 192,
  comparator 278, synthesizer 306, detailer 366, patcher 415) build a
  `lines = [...]` list; each already holds the op's primary node id.

**Outcome:** approach **rewritten** onto the t898 step model; two findings
corrected (no group validator; `list_subgraphs`/`create_node` need additions).
Scope decision below (apply-path consumer) confirmed with the user.

## Goal

Make the existing brainstorm ops subgraph-scoped and add the shared
subgraph-selector wizard step. **Back-compat is load-bearing:** a session with
only `_umbrella` behaves **exactly** as today (selector invisible/auto-selected).
At t756_2 runtime there is no way to create a second subgraph yet (that is B2's
`decompose`), so every change is **infrastructure that activates once B2 lands** —
verified now against a constructed multi-module fixture.

## Design decisions (read before editing)

1. **The selector is one `_WIZARD_STEPS` row, not a hand-wired pre-step.** t898
   made step nav generic — Back/Esc/Next/up-down resolve from the active step
   list. Adding the selector is: uncomment the row, add its ctx key, add a
   renderer, register it, and route op_select through the resolver. No existing
   handler's logic changes.
2. **`subgraph_count` is a cached field, NOT a disk read inside `_wizard_ctx`.**
   `_wizard_ctx` is called on every nav event and t898 deliberately kept it
   I/O-free (predicates are pure; `node_has_sections` is the cached
   `_wizard_has_sections`, not the disk-reading `_node_has_sections`). Mirror
   that: cache `self._wizard_subgraph_count` once when op-select renders
   (`_actions_show_step1`, where the session is already loaded) and have
   `_wizard_ctx` read the field. **This is a deliberate, documented deviation
   from t898's note** ("from `list_subgraphs(...)`" read inline) — keeping ctx
   pure is cleaner and avoids a per-event disk read that could change mid-wizard.
3. **The selector mirrors `op_select` (immediate advance), not `node_select`
   (select-then-Next).** `op_select` advances on Enter/click with no Next button;
   `node_select` needs a Next button + selection state. Immediate-advance keeps
   touch points to 3 (Enter branch, click branch, up/down gate) and adds no Next
   button wiring. The chosen subgraph is stored in `_wizard_config["subgraph"]`.
4. **Record `subgraph` at creation, and CONSUME it at apply.** `record_operation`
   gains an optional `subgraph` kwarg (every existing caller unaffected). The
   apply/ingest path (`brainstorm_session.py` ~993) reads the new node's
   `created_by_group` → that group's `subgraph` → passes `module_label` to
   `create_node` and calls `set_head(module=subgraph)`. Without this consumer the
   recorded field is inert and §4.6's worked example fails — confirmed in-scope
   with the user. Default `_umbrella` everywhere → byte-identical behaviour for
   single-subgraph sessions.
5. **No `GROUP_OPTIONAL` plumbing into a validator (there is none).** Add
   `GROUP_OPTIONAL = ["subgraph"]` purely as a documentation sibling to
   `GROUP_REQUIRED` (same not-wired-to-a-validator status), so the optional-field
   set is discoverable and ready if a validator is ever added. Cheap, honest, no
   dead branching.
6. **Subgraph derivation for non-selector ops.** Only `_NODE_SELECT_OPS`
   (explore/detail/patch) get the selector. `compare`/`synthesize` (not in
   `_NODE_SELECT_OPS`) derive their recorded `subgraph` from their **first input
   node** via `_node_module(...)` (default `_umbrella`). This keeps the group
   field meaningful for them without a selector and matches the uniform
   "apply reads group.subgraph" consumer. Cross-subgraph compares (a B2-era
   edge case) default to the first node's subgraph — acceptable for v1.

## Scope & changes

### `brainstorm_dag.py`
- **`create_node`** (38): add optional `module_label: str | None = None` param;
  when non-None/non-`_umbrella`, set `node_data["module_label"] = module_label`
  (relies on Phase A's `NODE_OPTIONAL_FIELDS` already including `module_label`).
  Omit it for `_umbrella` so legacy/umbrella nodes stay byte-identical.
- **`list_subgraphs(session_path) -> list[str]`** (new, pure helper near
  `_node_module`): read `current_heads` keys; order **most-recently-touched
  first** by the ordinal of each subgraph's HEAD node id (extract leading digits
  of `n###_...`); always include `_umbrella`; return `["_umbrella"]` when
  `current_heads` is missing/empty. Single source of truth shared by the App and
  tests (no re-walking graph state in the App). Add a small private
  `_node_id_ordinal(node_id) -> int` helper for the sort key.

### `brainstorm_schemas.py`
- Add `GROUP_OPTIONAL = ["subgraph"]` immediately after `GROUP_REQUIRED`, with a
  one-line comment noting it is the canonical optional-field list (no validator
  consumes it today — symmetric with `GROUP_REQUIRED`).

### `brainstorm_session.py`
- **`record_operation`** (220): add `subgraph: str = UMBRELLA_SUBGRAPH` kwarg;
  write `groups[group_name]["subgraph"] = subgraph` into the entry dict.
- **Apply/ingest path** (the function around 956-993 that calls `create_node`
  then `set_head`): resolve the op's subgraph once via a small local helper
  `_group_subgraph(wt, group_name)` (reads `br_groups.yaml`, returns the group's
  `subgraph` or `_umbrella`), using `node_data["created_by_group"]`. Pass
  `module_label=<subgraph>` into `create_node(...)` and change
  `set_head(wt, new_node_id)` → `set_head(wt, new_node_id, module=<subgraph>)`.

### `brainstorm_app.py`
- **Imports** (47-56): add `_node_module`, `UMBRELLA_SUBGRAPH`, `list_subgraphs`
  from `brainstorm_dag`.
- **Uncomment the `subgraph_select` row** in `_WIZARD_STEPS` (1518-1523):
  predicate `lambda c: c.get("op") in _NODE_SELECT_OPS and
  c.get("subgraph_count", 1) >= 2`, `rows=True`.
- **`_wizard_ctx`** (5600): add `"subgraph_count": self._wizard_subgraph_count`.
  Initialise `self._wizard_subgraph_count = 1` in `__init__` (next to the other
  `_wizard_*` fields) and set it in `_actions_show_step1` via
  `len(list_subgraphs(self.session_path))`.
- **New pure helper** near `_filter_labels` (module level, unit-testable):
  `_nodes_for_subgraph(session_path, nodes, subgraph) -> [nid for nid in nodes
  if _node_module(session_path, nid) == subgraph]`.
- **New `_actions_show_subgraph_select()`**: model on `_actions_show_step1`'s
  OperationRow rendering; call `self._enter_wizard_step("subgraph_select")`;
  default the highlighted/selected subgraph to `list_subgraphs(...)[0]`
  (most-recently-touched); mount one `OperationRow` per subgraph. Register it in
  the `_render_wizard_step` map (5616).
- **Route op_select → resolver.** Rewrite `_actions_show_step2()` (5627) to
  `self._render_wizard_step(next_step_id(self._wizard_ctx(), "op_select"))` so it
  routes to `subgraph_select` (2+ subgraphs), else `node_select`, else `config`
  — automatically. (Both op_select advance sites already call
  `_actions_show_step2()`, so this is the single change point.)
- **Select-a-subgraph advance** (immediate, mirrors op_select): in `on_key`
  Enter handler add a `self._wizard_step_id == "subgraph_select"` branch that
  sets `self._wizard_config["subgraph"] = focused.op_key` and renders
  `next_step_id(self._wizard_ctx(), "subgraph_select")`; add the mirror branch in
  `on_operation_row_activated` (mouse, 6269); add `"subgraph_select"` to the
  up/down OperationRow-nav tuple (3250).
- **Filter node-select** (`_actions_show_node_select`, 5660-5661): resolve
  `subgraph = self._wizard_config.get("subgraph", UMBRELLA_SUBGRAPH)`; set
  `nodes = _nodes_for_subgraph(self.session_path, list_nodes(self.session_path),
  subgraph)` and `head = get_head(self.session_path, module=subgraph)`.
- **Scope the op at launch** (`_run_design_op`, 6330): resolve the op's subgraph
  — `cfg.get("subgraph")` for node-select ops, else `_node_module(...)` of the
  first input node (compare/synthesize), default `_umbrella`; read
  `head_at_creation = get_head(self.session_path, module=subgraph)` (6338) and
  pass `subgraph=subgraph` into `record_operation(...)` (6415).

### `brainstorm_crew.py` + templates
- In each `_assemble_input_*` builder (explorer/comparator/synthesizer/detailer/
  patcher), derive `module = _node_module(session_path, <primary_node_id>)` (the
  node each builder already holds — `base_node_id`, the compared/merged nodes'
  first, or the detail/patch `node`) and append a front-matter block
  `["", "## Subgraph Context", module]` to `lines`. No new function parameters —
  the builders compute it locally. Add a matching one-line note to the five op
  templates (`explorer.md`/`comparator.md`/`synthesizer.md`/`detailer.md`/
  `patcher.md`) telling the agent to stay within the named subgraph.

## Implementation steps
1. **dag:** `create_node(module_label=...)`; add `list_subgraphs` +
   `_node_id_ordinal`.
2. **schemas:** add `GROUP_OPTIONAL = ["subgraph"]` (doc constant).
3. **session:** `record_operation(subgraph=...)`; apply-path `_group_subgraph`
   helper → `create_node(module_label=...)` + `set_head(module=...)`.
4. **app:** imports; uncomment row; `_wizard_subgraph_count` field + ctx key +
   step1 set; `_nodes_for_subgraph`; `_actions_show_subgraph_select` + register;
   `_actions_show_step2` → resolver; Enter/click/up-down branches for
   `subgraph_select`; node-select filter + module-scoped head; `_run_design_op`
   subgraph resolution + `record_operation(subgraph=...)`.
5. **crew + templates:** "Subgraph Context" front-matter line per builder +
   one-line template note.

## Verification
- **Pure-logic unit tests (no TUI):**
  - `list_subgraphs`: most-recently-touched-first ordering by HEAD ordinal;
    `_umbrella` fallback for empty/missing `current_heads`.
  - `_nodes_for_subgraph`: filters by `module_label`; legacy/unlabeled nodes →
    `_umbrella`.
  - step model: with the row uncommented, `subgraph_count >= 2` makes
    `subgraph_select` active for explore/detail/patch and inactive for
    compare/synthesize and for `subgraph_count == 1`; `next_step_id("op_select")`
    routes op_select → subgraph_select (2+) / node_select (1) / config
    (compare/synth). Extend `tests/test_brainstorm_wizard_steps.py` and add
    `tests/test_brainstorm_wizard_subgraph.py`.
  - group round-trip: `record_operation(subgraph="parser")` writes it; legacy
    entries read back `_umbrella` via `.get`.
  - apply consumer (constructed Phase-A fixture: a `parser` subgraph): ingest of
    an agent node whose group recorded `subgraph=parser` stamps
    `module_label=parser` on the new node and advances `current_heads["parser"]`
    (not `_umbrella`). Extend `tests/test_brainstorm_dag.py` /
    `test_brainstorm_session.py`.
- **Back-compat:** single-subgraph (`_umbrella`) session → selector never
  renders, recorded `subgraph` is `_umbrella`, created nodes carry no
  `module_label`, umbrella head advances as before. Confirm
  `tests/test_brainstorm_wizard_filter.py`, `test_brainstorm_wizard_sections.py`,
  `test_brainstorm_wizard_steps.py`, `test_brainstorm_session.py`,
  `test_brainstorm_dag.py`, `test_brainstorm_crew.py`,
  `test_brainstorm_groups_persist.py` still pass.
- **Interactive (manual, per `aidocs/tui_conventions.md`):** in a constructed
  multi-subgraph session, drive explore/detail/patch — selector lists subgraphs,
  defaults to most-recently-touched, Enter/click/Back/Esc/up-down behave;
  node-select shows only the chosen subgraph's nodes; agent `_input.md` carries
  the "Subgraph Context" line. (Covered by the t756_7 aggregate manual-verify
  sibling.)
- Run: `bash tests/test_brainstorm_dag.py tests/test_brainstorm_session.py
  tests/test_brainstorm_schemas.py tests/test_brainstorm_wizard_steps.py
  tests/test_brainstorm_wizard_filter.py tests/test_brainstorm_wizard_sections.py
  tests/test_brainstorm_wizard_subgraph.py tests/test_brainstorm_crew.py
  tests/test_brainstorm_groups_persist.py` (each individually).

## Step 9 (Post-Implementation)
Follow task-workflow Step 9: review, commit (`feature: … (t756_2)`), consolidate
this plan with Final Implementation Notes — **document the `subgraph_select` row
contract, `list_subgraphs` / `_nodes_for_subgraph` signatures, the
`record_operation(subgraph=...)` + apply-path consumer contract, and the
`_node_module`-derived subgraph for compare/synthesize so t756_3 can reuse them**
— then archive via `./.aitask-scripts/aitask_archive.sh 756_2`.

## Cross-skill follow-up
Per CLAUDE.md ("Working on Skills / Custom Commands"): these are source-code
changes, not skill changes — no Codex/OpenCode skill port is needed.

## Final Implementation Notes

- **Actual work done (all as planned):**
  - `brainstorm_dag.py`: `create_node` gained `module_label: str | None = None`
    (written only for non-`_umbrella` → legacy/umbrella nodes byte-identical);
    new pure `list_subgraphs(session_path)` (most-recently-touched first by HEAD
    ordinal, `_umbrella` fallback) + `_node_id_ordinal(node_id)`.
  - `brainstorm_schemas.py`: `GROUP_OPTIONAL = ["subgraph"]` documentation
    constant (no validator consumes it — symmetric with `GROUP_REQUIRED`).
  - `brainstorm_session.py`: `record_operation(subgraph="_umbrella")` writes the
    field on every entry; new `_group_subgraph(wt, group_name)` reader; the apply
    path resolves the op's subgraph from the new node's `created_by_group` and
    passes `module_label=` to `create_node` + `set_head(module=)`.
  - `brainstorm_app.py`: uncommented the `subgraph_select` `_WIZARD_STEPS` row;
    cached `_wizard_subgraph_count` (set in `_actions_show_step1`) feeds the
    I/O-free `_wizard_ctx`; `_nodes_for_subgraph` pure helper;
    `_actions_show_subgraph_select()` (registered in `_render_wizard_step`);
    `_actions_show_step2` now resolver-driven (`next_step_id(..., "op_select")`);
    Enter/click/up-down wiring for `subgraph_select`; node-select scoped to the
    chosen subgraph (candidates + HEAD); `_run_design_op` resolves the subgraph
    and threads it into `head_at_creation` + `record_operation`.
  - `brainstorm_crew.py` + 5 templates: `_subgraph_context_lines()` appends a
    `## Subgraph Context` block (derived from each builder's primary node) to
    every op input; each template got a "Subgraph scope" agent note.
- **Deviations from plan (small, deliberate):**
  - **Selected subgraph held in `self._wizard_subgraph`, NOT
    `_wizard_config["subgraph"]`** as the plan first wrote. `_actions_show_node_select`
    resets `_wizard_config = {}` *after* the selector runs, which would wipe the
    key. A dedicated field (reset to `_umbrella` at op-select) survives the reset
    and is read by node-select filtering and `_run_design_op`.
  - **`create_node` omits `module_label` for `_umbrella`** (rather than always
    writing it) so single-subgraph sessions produce byte-identical node YAML.
    `record_operation`, by contrast, always writes `subgraph` (incl. `_umbrella`)
    — the field is the apply path's contract and tests assert its presence.
- **Issues encountered:** the new `tests/test_brainstorm_wizard_subgraph.py`
  initially failed because `create_node` does not `mkdir` `br_nodes`/`br_proposals`
  — fixed by pre-creating them in `setUp` (matches the apply-test fixture).
- **Key decisions:** (1) apply-path consumption included this task (user-confirmed)
  so the recorded `subgraph` is not inert — §4.6's "explore in a subgraph advances
  that subgraph's HEAD" holds now. (2) selector mirrors op-select (immediate
  Enter/click advance, no Next button) — 3 touch points, zero new button wiring.
  (3) `subgraph_count` cached, not read in `_wizard_ctx`, preserving t898's
  I/O-free-predicate contract.
- **Upstream defects identified:** None.
- **Notes for sibling tasks (t756_3 — decompose/merge):**
  - **Add an op to the selector** by adding it to `_NODE_SELECT_OPS`; the
    `subgraph_select` predicate (`op in _NODE_SELECT_OPS and subgraph_count >= 2`)
    and all nav are then automatic. The op's chosen subgraph is in
    `self._wizard_subgraph`; node-select is filtered via `_nodes_for_subgraph`.
  - **Record + consume contract:** call `record_operation(..., subgraph=<module>)`;
    the apply path (`brainstorm_session.py` ingest) already stamps
    `module_label`+module HEAD from the group's `subgraph` via `_group_subgraph`.
    `decompose` (which creates a NEW subgraph) must instead set the new node's
    `module_label` to the new module name and `set_head(module=<new>)` itself —
    `_group_subgraph` returns the *parent* op's subgraph, so decompose's
    node-creation is a special case, not the generic ingest path.
  - `list_subgraphs` is the single source of truth for the subgraph list/order;
    `is_ancestor_subgraph` (t756_1) is ready for the merge up-only guard.
  - compare/synthesize derive their recorded `subgraph` from the first input
    node (`_node_module`); no selector. Cross-subgraph compares default to the
    first node's subgraph (a v1 simplification — revisit if B2 surfaces a need).
