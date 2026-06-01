---
Task: t756_2_phase_b1_module_aware_wizard_infra.md
Parent Task: aitasks/t756_brainstorm_modules.md
Sibling Tasks: aitasks/t756/t756_3_phase_b2_decompose_merge_ops.md, aitasks/t756/t756_4_phase_c_sync_op.md, aitasks/t756/t756_5_phase_d1_status_views.md, aitasks/t756/t756_6_phase_d2_fast_track_preset.md, aitasks/t756/t756_7_manual_verification_brainstorm_modules.md
Archived Sibling Plans: aiplans/archived/p756/p756_1_phase_a_data_model.md
Base branch: main
---

# t756_2 — Phase B1: module-aware wizard infrastructure

> **⚠️ SEQUENCING UPDATE (2026-06-01) — re-plan before implementing.**
> This task was started, then **paused and reverted**. Inserting the
> subgraph-selector as an in-wizard step fought the fragile integer-indexed
> `_wizard_step` machine (it touches ~6 hardcoded handlers). Rather than build a
> workaround, the wizard step machine is being refactored first under **t898**
> (now a hard dependency of this task — `depends: [t756_1, 898]`).
>
> When resuming after t898 lands: the **subgraph-selector becomes a declarative
> step descriptor** on t898's new step model — NOT the integer-ladder insertion
> described in "Design decisions" §1 below. The data-model plumbing parts
> (schema `GROUP_OPTIONAL` subgraph field, `list_subgraphs`/`_node_id_ordinal` in
> `brainstorm_dag.py`, the `subgraph` kwarg on `record_operation`, the
> `_nodes_for_subgraph` node-filter helper, and the crew "subgraph context"
> front-matter) were reverted with the pause and should be recreated — they are
> orthogonal to t898 and remain valid as designed. **Re-verify all anchors and
> re-plan the selector on the new step model before implementing.**

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.5 existing-ops-become-module-aware; §7 Phase A subgraph-selector note).
**Binding conventions:** `aiplans/p756_brainstorm_modules.md`. **TUI rules:**
`aidocs/tui_conventions.md`. **Depends on:** t756_1 (data model) — DONE.

## Context

`ait brainstorm` models a session as one DAG with per-subgraph HEADs after
Phase A (t756_1) landed the additive, back-compatible data model: `module_label`
on nodes, `current_heads` map, `get_head/set_head(module=...)`, and the
`_node_module` / `_subgraph_root` / `is_ancestor_subgraph` helpers. **No op yet
uses any of it** — every wizard op still operates on the `_umbrella` subgraph.

This task makes the *existing* ops (`explore`, `compare`, `synthesize`,
`detail`, `patch`) subgraph-scoped and adds the shared **subgraph-selector**
wizard step that the new ops (B2, t756_3) will reuse. **No new ops here.** §4.5
calls this "the chunk of work that touches the most existing code"; isolating it
keeps B2 thin and resolves the A/B boundary that t756_1 explicitly deferred here
("B1 owns the entire subgraph-selector step" — t756_1 Final Implementation Notes).

## Plan verification (2026-06-01, verify path)

Re-verified every anchor against live source before re-confirming. **The plan
HOLDS** — all Phase-A helpers exist and line references are current:

- `brainstorm_dag.py`: `UMBRELLA_SUBGRAPH` (30); `get_head(path, module=...)`
  (127–144) and `set_head(path, nid, module=...)` (147–178) both take the
  optional `module` kwarg with `_umbrella` default and legacy `current_head`
  fallback; `current_heads` map read at 156 (keys = subgraph names);
  `_node_module` (217–225), `_subgraph_root` (263–281),
  `is_ancestor_subgraph` (284–316).
- `brainstorm_schemas.py`: `NODE_OPTIONAL_FIELDS` includes `module_label` (20);
  `GROUP_REQUIRED` (65–68) = operation/agents/status/created_at/head_at_creation/
  nodes_created; `GROUP_OPERATIONS` (69); **no `GROUP_OPTIONAL` constant exists
  yet**; `GRAPH_STATE_MODULE_MAPS` (48) validated as dicts at 142–145.
- `brainstorm_app.py`: `_NODE_SELECT_OPS = {"explore","detail","patch"}` (138);
  step machine `_actions_show_step1` (5427) → `_actions_show_step2` (5540, routes
  to node-select for `_NODE_SELECT_OPS` else config) → `_actions_show_node_select`
  (5547, lists **all** `list_nodes()` unfiltered at 5573, `get_head` at 5574) →
  optional `_actions_show_section_select` (5635) → `_actions_show_config` (5668)
  → `_actions_show_confirm` (6003). `_run_design_op` worker calls
  `record_operation(...)` at ~6342 with `head_at_creation = get_head(...)` at 6265.
  `brainstorm_app.py` does **not** yet import `_node_module`/`UMBRELLA_SUBGRAPH`
  and has no subgraph concept.
- `brainstorm_session.py`: `record_operation` (220–245) writes the group entry
  (no `subgraph`); `update_operation(task_num, group_name, **fields)` (248–275)
  already exists for patching group fields.
- `brainstorm_crew.py`: six `_assemble_input_*` builders (explorer 192,
  comparator 278, synthesizer 306, detailer 366, patcher 415, initializer 464)
  assemble front-matter as a `lines = [...]` list; `register_*` at 499/549/590/
  632/673/718; templates in `.aitask-scripts/brainstorm/templates/`.

**Outcome:** approach and all anchors valid; no line-reference drift. Two design
refinements added below (step-machine blast radius; pure-logic helper extraction).

## Goal

Make the existing brainstorm ops subgraph-scoped and add the shared
subgraph-selector wizard step. Back-compat is load-bearing: a session with only
`_umbrella` behaves **exactly** as today (selector invisible/auto-selected).

## Design decisions (blast-radius notes — read before editing)

1. **The `_wizard_step` machine is integer-indexed and fragile.** Step numbers
   are hardcoded in the Esc handler (3105–3132), Enter handler (3137–3200), Back
   button (6118–6154), and advance (6196–6209). **Do NOT renumber existing
   steps.** Instead insert the selector as a *conditional pre-step* modeled on
   the existing optional section-select precedent (5635, conditionally inserted
   via `_node_has_sections`):
   - When `len(subgraphs) <= 1`: **no selector renders.** Set
     `self._wizard_config["subgraph"] = <the one subgraph or _umbrella>` and route
     straight into today's `_actions_show_step2()`. This is the only path any
     existing single-subgraph session ever takes → zero behavioral change, zero
     risk to the integer handlers.
   - When `len(subgraphs) >= 2`: render the selector between step 1 and node-
     select. On selection, store `subgraph` in `_wizard_config` and call
     `_actions_show_step2()`. Back from node-select returns to the selector when
     multi-subgraph, else to step 1 (mirror the existing Back logic).
2. **Extract pure-logic helpers for unit testing.** The TUI itself is verified
   interactively, but the *selectable-subgraph listing* and *node-filter-by-
   module* logic must be module-level pure functions (precedent: `_filter_labels`
   in `brainstorm_app.py`, unit-tested by `tests/test_brainstorm_wizard_filter.py`
   without a running App). This keeps the testable surface off the Textual event
   loop.
3. **Record `subgraph` at creation, not via a follow-up patch.** Add an optional
   `subgraph: str = UMBRELLA_SUBGRAPH` parameter to `record_operation` (keyword,
   defaulted → every existing caller is unaffected) rather than a second
   `update_operation` round-trip. Legacy groups without the field read back as
   `_umbrella` at the consumer side.

## Scope & changes

### `brainstorm_schemas.py`
- Add `GROUP_OPTIONAL = ["subgraph"]` (new constant) and accept `subgraph` as an
  optional string in the group validator (default `_umbrella` when absent). Keep
  `GROUP_REQUIRED` unchanged so legacy `br_groups.yaml` entries still validate.

### `brainstorm_dag.py` (helper, if not already trivially derivable)
- Add a small pure helper to enumerate selectable subgraphs from `current_heads`
  (keys of the map; `_umbrella` filtered/ordered with most-recently-touched
  first per §7). If `current_heads` ordering already suffices, expose it via a
  thin `list_subgraphs(session_path) -> list[str]` so `brainstorm_app.py` and the
  tests share one source of truth (do not re-walk graph state in the App).

### `brainstorm_app.py`
- Import `UMBRELLA_SUBGRAPH`, `_node_module`, and the subgraph-list helper.
- New pure helper near `_filter_labels`: `_nodes_for_subgraph(session_path,
  nodes, subgraph)` returning `[nid for nid in nodes if _node_module(...) ==
  subgraph]` — unit-testable.
- New `_actions_show_subgraph_select()` step (conditional, per Design decision 1),
  defaulting selection to the most-recently-touched subgraph (fallback
  `_umbrella`). Wire Esc/Back to return to it from node-select only in the
  multi-subgraph case.
- `_actions_show_node_select` (5573–5582): filter candidates through
  `_nodes_for_subgraph(...)` and read the head with
  `get_head(self.session_path, module=self._wizard_config.get("subgraph",
  UMBRELLA_SUBGRAPH))`.
- `_run_design_op` (~6265, ~6342): read `head_at_creation` with the selected
  module and pass `subgraph=` into `record_operation`.

### `brainstorm_session.py`
- `record_operation`: add `subgraph: str = UMBRELLA_SUBGRAPH` kwarg; write it into
  the group entry dict.

### `brainstorm_crew.py` + templates
- In each `_assemble_input_*` builder, add one front-matter line
  `f"subgraph context: {module_label}"` (resolved via `_node_module` on the op's
  base node, default `_umbrella`), threaded through the `register_*` input
  assembly. Add a matching one-line note to the five op templates
  (`explorer.md`/`comparator.md`/`synthesizer.md`/`detailer.md`/`patcher.md`) so
  the agent is told to stay within the named subgraph.

## Implementation steps
1. Schema: `GROUP_OPTIONAL = ["subgraph"]` + group-validator acceptance.
2. DAG/helper: `list_subgraphs` (most-recently-touched first, `_umbrella` fallback).
3. `record_operation`: optional `subgraph` kwarg written into the entry.
4. `brainstorm_app.py`: pure `_nodes_for_subgraph`; conditional
   `_actions_show_subgraph_select`; filter node-select; module-scoped `get_head`;
   pass `subgraph` into `record_operation`.
5. `brainstorm_crew.py` + templates: "subgraph context" front-matter line.

## Verification
- **Pure-logic unit tests** (new, no TUI): `_nodes_for_subgraph` filters by
  `module_label`; `list_subgraphs` orders most-recently-touched first and falls
  back to `_umbrella`; group entries round-trip `subgraph` and legacy entries
  default to `_umbrella`. Extend `tests/test_brainstorm_wizard_filter.py` (or a
  sibling `test_brainstorm_wizard_subgraph.py`) and `test_brainstorm_schemas.py`.
- **Back-compat:** single-subgraph (`_umbrella` only) session → selector never
  renders, every existing op behaves identically. Confirm
  `test_brainstorm_session.py`, `test_brainstorm_dag.py`,
  `test_brainstorm_wizard_sections.py` still pass.
- **Multi-module (Phase A fixture):** selector lists subgraphs, node-select
  filters by `module_label`, the recorded group carries the chosen `subgraph`.
- **Interactive (manual):** drive the wizard in a multi-subgraph session per
  `aidocs/tui_conventions.md`; selector flow + Esc/Back behave; agent input
  front-matter shows the "subgraph context" line.
- Run: `bash tests/test_brainstorm_schemas.py`, `tests/test_brainstorm_dag.py`,
  `tests/test_brainstorm_session.py`, `tests/test_brainstorm_wizard_filter.py`,
  `tests/test_brainstorm_wizard_sections.py`, `tests/test_brainstorm_crew.py`,
  `tests/test_brainstorm_groups_persist.py`.

## Step 9 (Post-Implementation)
Follow task-workflow Step 9: review, commit (`feature: … (t756_2)`), consolidate
this plan with Final Implementation Notes — **document the subgraph-selector
contract and `list_subgraphs`/`_nodes_for_subgraph` signatures so 756_3 can
reuse them** — then archive via `./.aitask-scripts/aitask_archive.sh 756_2`.
