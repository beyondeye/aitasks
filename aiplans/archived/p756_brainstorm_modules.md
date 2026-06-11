---
Task: t756_brainstorm_modules.md
Worktree: (none — planned on current branch)
Branch: main
Base branch: main
Status: RE-VERIFIED 2026-06-01 (t873 landed) — ready to create children
---

# t756 — Brainstorm Modules: Parent Decomposition Plan

## ✅ Re-verification — t873 landed, plan HOLDS (2026-06-01)

This plan was deferred behind
`t873_fix_brainstorm_dimension_proposal_linking_and_compare` (`depends: [873]`)
because t756's design rested on the proposal **dimension** model that t873
reworked. **t873 has now landed (archived).** Per the original deferral gate, the
three risk points were re-verified against the as-landed t873 source before
creating any children. Outcome:

1. **Phase A `active_dimensions` decision — HOLDS.** `active_dimensions` in
   `br_graph_state.yaml` is still a **flat session-wide list of strings**.
   `GRAPH_STATE_REQUIRED = ["current_head","history","next_node_id","active_dimensions"]`
   is unchanged; `validate_graph_state` still requires a `list`; `init_session`
   still seeds `[]`. t873 added **no** registry, per-module map, or dimension
   "full-name registry" field. The "modules do NOT fork the dimension axis list"
   decision is safe exactly as written.
2. **Phase B boundary-hint approach — HOLDS and is now better-supported.** t873_1
   shipped glob/prefix expansion of `<!-- section: name [dimensions: KEY*] -->`
   tags as first-class helpers. Phase B's `module_decomposer` should **consume**
   these (see helper-reuse note in 756_2) rather than reinvent exact-match.
3. **New t873 helpers to reuse (not reinvent) — recorded below.** No new
   frontmatter / section-syntax / node-YAML fields were added, so Phase A's
   additive data-model fields (`current_heads`, `module_label`, `module_tasks`,
   `last_synced_at`) do not collide with anything t873 introduced.

No `module_*` ops/agents exist yet (`GROUP_OPERATIONS` and `BRAINSTORM_AGENT_TYPES`
are still the pre-module set), so there is no partial implementation to
reconcile — the "Current state" baseline below remains accurate.

### t873 helpers the children must REUSE (CLAUDE.md "Reusable Helpers")
- `dimension_matches_tag(dim_key, tag)` — `brainstorm_sections.py:233` — exact-or-glob
  section↔dimension match. **Phase B** boundary hints.
- `get_sections_for_dimension(parsed, dim)` / `best_section_for_dimension(parsed, dim)`
  — `brainstorm_sections.py:247,263` — section lookup by dimension. **Phase B**.
- `validate_sections(parsed, node_keys=...)` — `brainstorm_sections.py:164` — opt-in
  validation of invented section tags against a node's real keys. **Phase B**.
- `extract_dimensions(data)` / `group_dimensions_by_prefix(dims)` —
  `brainstorm_schemas.py:145,150` — dimension extraction + prefix grouping. **Phase D** views.
- `get_active_dimensions(session_path)` — `brainstorm_dag.py:116` — read session
  active dimensions. **Phase B/D**.
- `FuzzyCheckList.set_grouped_items(groups)` — `brainstorm_app.py:1654` — reusable
  grouped/filterable checklist. **Phase D** subgraph selector / dashboard.

This plan keeps the settled decisions (`module_` op naming everywhere, the
4-phase split, session-wide dimensions) intact across the t873 redesign.

### t891 — proposal-only brainstorm (retire plans) runs AFTER t756

`t891_brainstorm_proposal_only_retire_plans` makes `ait brainstorm`
**proposal-only**: retire the implementation-plan layer (`detail`/`patch`,
`detailer`/`patcher`, `br_plans/`, `plan_file`, the `finalize` plan export) and
absorb its value into the module architecture.

**Sequencing reversed (2026-06-01): t891 is DOWNSTREAM of t756, not upstream.**
The plan-layer machinery is the **working reference model** for the module ops
this plan builds — `module_decompose`, `module_sync`, their wizards, and the
syncer's bottom-up reconciliation are modelled on `detail`/`patch`, the
detailer/patcher agents, the plan wizard flows, and the impact-analysis
escalation. So **keep the plan machinery intact while building t756**; t891's
children are gated on `depends: 756` and execute only after this lands.

When t891 *does* run, the relationship to this plan is:
- The patcher's bottom-up impact-analysis flow has by then been re-expressed as
  `module_sync` (observing as-implemented reality instead of hypothetical plan
  edits), so retiring `patch` is pure removal of the now-redundant model.
- `detail` is likewise redundant once `module_decompose` fast-track + the
  proposal slice + `/aitask-pick` Step 6 cover its role.

The retired-feature → module mapping and full motivation live in t891.
(Re-verification against the as-landed t873 design is complete — see the
"Re-verification" section at the top of this plan.)

## Context

`ait brainstorm` today models **one session = one task = one DAG = one HEAD**.
Every design op (`explore`, `compare`, `synthesize`, `detail`, `patch`) targets
the single `current_head` in `br_graph_state.yaml`. Three increasingly-common
use cases push against this (verbatim in the design doc): decomposing a wide
proposal into independently-evolvable **modules** (UC-1), tracking a **fluid
per-module implementation status** (UC-2), and **fast-tracking** one module into
a real aitask while leaving the rest for later (UC-3).

The design is already fully specified in
`aidocs/brainstorming/module_decomposition_design.md` (design-only; no code has
landed). It introduces three new ops — `module_decompose` (divergent), `module_sync`
(reconciliatory), `module_merge` (convergent) — plus additive data-model extensions
(per-subgraph HEADs, `module_label` on nodes, `module_tasks`, `last_synced_at`),
and a derived per-module status view. The doc's §7 roadmap defines four
dependency-ordered phases, each "bounded enough to be a single aitask".

**This task is a parent decomposition.** The deliverable of t756 itself is the
four child tasks + their implementation plans (per the user's task body: "this is
very complex task that require child decomposition"). The design doc is the
**primary reference** for all four children.

### Current state — validated against the live code

- Schema: `brainstorm_schemas.py` — `GRAPH_STATE_REQUIRED = ["current_head",
  "history", "next_node_id", "active_dimensions"]` (single head),
  `NODE_OPTIONAL_FIELDS = ["plan_file", "reference_files"]` (no `module_label`),
  `GROUP_OPERATIONS = ["explore","compare","synthesize","detail","patch"]` (no
  new ops). `validate_graph_state` treats `history` as a **list**.
- DAG: `brainstorm_dag.py` — `get_head/set_head/next_node_id` operate on the
  single `current_head`; `get_node_lineage` follows **first-parent only**;
  per-node multiple `parents` already supported (basis for `synthesize`).
- Session: `brainstorm_session.py::init_session` writes
  `{current_head: None, history: [], next_node_id: 0, active_dimensions: []}`.
- Crew: `brainstorm_crew.py` — `BRAINSTORM_AGENT_TYPES` (6 types), per-op
  `register_*()` functions all following one pattern (`_group_seq` → agent name
  → optional `next_node_id()` for node-creating ops → `_assemble_input_*` →
  `TEMPLATE_DIR/<type>.md` → `_run_addwork` → `_write_agent_input`). Node-creating
  ops: explorer, synthesizer, patcher. Read/enrich-only: comparator, detailer.
- TUI: `brainstorm_app.py` — `_DESIGN_OPS` (5 tuples), `_WIZARD_OP_TO_AGENT_TYPE`,
  `_NODE_SELECT_OPS = {"explore","detail","patch"}` (6 reference sites),
  `_OPERATION_HELP`, `_execute_design_op`/`_run_design_op` (per-op `elif`
  branches), wizard step machine (step1 op-picker → step2 node-select/config →
  optional section-select → config → confirm).
- Op refs: `brainstorm_op_refs.py::_OP_INPUT_SECTION` maps op → input section
  label.
- Reuse target for `sync`: the `aitask_explain_context.sh` helper family (t369)
  — "given a list of source files, return formatted historical plan/task
  context". **Consume, do not reimplement** (CLAUDE.md "Reusable Helpers").

All design-doc anchors verified present (line numbers drifted as the file grew;
symbols intact).

### Naming convention for the new ops (`module_` prefix everywhere)

`sync`/`merge` are overloaded (git, the `ait syncer` remote-desync TUI,
`synthesize`'s existing "Merge Rules" section). To disambiguate, **all three new
ops carry a `module_` prefix across every layer** — this is binding for all
children:

| Layer | Names |
|-------|-------|
| op-key (`GROUP_OPERATIONS`, persisted `operation:` in `br_groups.yaml`) | `module_decompose` · `module_sync` · `module_merge` |
| wizard label (`_DESIGN_OPS`) | "Module Decompose" · "Module Sync" · "Module Merge" |
| agent type (`BRAINSTORM_AGENT_TYPES`, `_WIZARD_OP_TO_AGENT_TYPE`) | `module_decomposer` · `module_syncer` · `module_merger` |
| template file | `templates/module_decomposer.md` · `module_syncer.md` · `module_merger.md` |
| register fn (`brainstorm_crew.py`) | `register_module_decomposer()` · `register_module_syncer()` · `register_module_merger()` |
| input section (`_OP_INPUT_SECTION`) | "Decomposition Plan" · "Sync Sources" · "Merge-Up Rules" |

(The design doc uses the bare names `decompose`/`sync`/`merge`; child plans note
that the implemented op-keys/agent-types take the `module_` prefix.)

### Modules × dimensions × sections (relationship — binding for children)

Three distinct partition concepts, coupled only at decompose time:

- **Dimensions** (`requirements_`/`assumption_`/`component_`/`tradeoff_` fields)
  = the *axes/vocabulary* of the design space. `active_dimensions` in
  `br_graph_state.yaml` is and **stays session-wide** (one shared list; grown via
  explorers' `--- NEW_DIMENSIONS ---`, merged by `_merge_new_dimensions`). Each
  node carries its own dimension *values* under the inherit-never-drop rule.
- **Sections** (`<!-- section: name [dimensions: …] -->`, parsed by
  `brainstorm_sections.py`) = named slices of *one proposal's markdown*, each
  optionally tagged with the dimensions it addresses.
- **Modules** (new) = subgraphs of the *DAG*, independently-evolvable, one HEAD
  each, `module_label` per node, optionally linked to an aitask.

**Decision (confirmed): dimensions remain a session-wide vocabulary; modules do
NOT fork the dimension axis list.** Consequences threaded into the children:
- **Phase A:** `active_dimensions` stays a single list (NOT a per-module map).
  `module_label` is an independent optional node field, orthogonal to dimension
  fields. No per-module dimension namespace is introduced.
- **Phase B:** the `module_decomposer` template uses existing
  `<!-- section: … -->` markers and `component_*` dimensions as **boundary
  hints** only. Each module subgraph root's proposal slice + node carries the
  *subset* of dimensions relevant to that module; the inherit-never-drop rule
  then operates *within* the subgraph. Cross-module compare/`module_merge` stay
  coherent because the axis vocabulary is shared.

> **t873 re-verification (2026-06-01):** confirmed against the as-landed t873
> source — `active_dimensions` is unchanged (flat session-wide list); this
> section stands exactly as written. See the "Re-verification" section at top.

## Decomposition (6 children + 1 manual-verification sibling, dependency-ordered)

> **Scope-split refinement (2026-06-01):** the original Phase B and Phase D were
> each judged too large during review and split: **B → B1** (module-aware wizard
> infra) **+ B2** (the two new ops); **D → D1** (status views) **+ D2** (fast-track
> preset). This yields 6 implementation children + 1 aggregate manual-verification
> sibling (756_7). The design doc's §7 roadmap still maps cleanly: A=§7-A,
> B1+B2=§7-B, C=§7-C, D1+D2=§7-D.

Children auto-depend on prior siblings, enforcing A→B1→B2→C→D1→D2→(MV). Each child
file gets the full per-child context required for fresh-context execution (Child
Task Documentation Requirements: Context, Key Files, Reference Patterns,
Implementation Plan, Verification). The design doc is referenced as primary
reference in every child.

### 756_1 — Phase A: data model (foundation)
**Scope (design doc §4.1, §5 "data-model layer" + "merge guard"):**
- `brainstorm_schemas.py`: extend `GRAPH_STATE_REQUIRED`/`validate_graph_state`
  for `current_heads` (map `<module>:<node_id>`) and back-compat with legacy
  `current_head`/`history` (repurposed as `_umbrella`). Add `module_label` to
  `NODE_OPTIONAL_FIELDS`. Keep `current_head` as legacy alias of
  `current_heads["_umbrella"]`. Handle `history` as either legacy list or new
  per-module map without breaking existing sessions.
- `brainstorm_dag.py`: add `module="_umbrella"` parameter (default = back-compat)
  to `set_head`, `get_head`, `get_node_lineage`, `next_node_id`. New helper
  `is_ancestor_subgraph(source, destination)` (walks parent-of-root chain) for
  the merge "only up" guard.
- `brainstorm_session.py::init_session`: initialize `current_heads={_umbrella:
  <root>}` and `module_tasks={}` (and `last_synced_at` map) alongside the legacy
  fields.
- `active_dimensions` stays a **single session-wide list** (do NOT convert to a
  per-module map) — see "Modules × dimensions × sections" above. `module_label`
  is orthogonal to dimension fields.
- No new ops; existing ops continue to operate on `_umbrella`. Wizard gains the
  subgraph-selector scaffolding only if cheap; otherwise the selector lands in B1
  (note this boundary in the child file).
**Verification:** unit-style checks that legacy single-head sessions still load
and validate; new map fields round-trip; `is_ancestor_subgraph` correctness;
existing brainstorm tests still pass.

### 756_2 — Phase B1: module-aware wizard infrastructure
**Scope (design doc §4.5, §7 Phase A subgraph-selector note):** the cross-cutting
wizard plumbing — split out of Phase B because §4.5 calls it "the chunk of work
that touches the most existing code". **No new ops.**
- `brainstorm_app.py`: insert the **subgraph-selector** wizard step before
  node-select (default = most-recently-touched subgraph; fallback `_umbrella`;
  auto-skip / invisible when only `_umbrella` exists). Filter `_NODE_SELECT_OPS`
  candidates by `module_label`. Record the chosen `subgraph` in the group entry.
- `brainstorm_schemas.py`: optional `subgraph` field on group entries (default
  `_umbrella` for back-compat).
- `brainstorm_crew.py` + existing templates (explorer/comparator/synthesizer/
  detailer/patcher): add "subgraph context: <module_label>" front-matter; thread
  module context through the `register_*()` input assembly.
**Verification:** with only `_umbrella`, existing ops behave exactly as before;
on a multi-module fixture the selector lists subgraphs and node-select filters by
`module_label`; legacy groups without `subgraph` default to `_umbrella`.

### 756_3 — Phase B2: `module_decompose` + `module_merge` ops (paired)
**Scope (design doc §4.2, §4.4, §4.8, §4.10, §5 op-recipe):** Paired in one task
because they share the ancestry-guard validator (built in A) and B1's
subgraph-selector machinery. Thin now that B1 made the wizard module-aware.
- New templates `templates/module_decomposer.md`, `templates/module_merger.md`.
- `brainstorm_crew.py`: add `module_decomposer`/`module_merger` to
  `BRAINSTORM_AGENT_TYPES`; `register_module_decomposer()` (multi-output: one
  subgraph-root node per module, `--from-sections` slice path vs agent-driven;
  optional `--link-to-task` fast-track via `aitask_create.sh --batch --parent
  <umbrella>`), `register_module_merger()` (2-parent output node in destination
  subgraph; ancestry guard at launch).
- `brainstorm_schemas.py`: add `module_decompose`,`module_merge` to
  `GROUP_OPERATIONS`.
- `brainstorm_op_refs.py`: `_OP_INPUT_SECTION` entries
  `module_decompose:"Decomposition Plan"`, `module_merge:"Merge-Up Rules"`
  (distinct from synthesize's "Merge Rules").
- `brainstorm_app.py`: `_DESIGN_OPS` (labels "Module Decompose"/"Module Merge"),
  `_WIZARD_OP_TO_AGENT_TYPE`, `_OPERATION_HELP`, `_execute_design_op` branches.
  **Reuse** B1's subgraph selector — do not re-add it.
- UC-3 fast-track = `module_decompose --modules=one + --link-to-task` (functional
  path here; the polished preset UI is Phase D2).
- **Reuse t873 section↔dimension helpers (do NOT reinvent):** boundary-hint logic
  uses `dimension_matches_tag` / `get_sections_for_dimension` /
  `best_section_for_dimension`, and validates the decomposer's emitted section
  tags with `validate_sections(parsed, node_keys=...)` (all in
  `brainstorm_sections.py`, landed by t873_1). Glob (`component_*`) expansion is
  already implemented — consume it for boundary hints.
**Verification:** decompose on `_umbrella` HEAD spawns per-module roots with
correct `module_label`/`parents`/`current_heads`; merge produces a 2-parent
destination node and refuses non-ancestor destinations; an existing op targeted
at a module changes only that subgraph.

### 756_4 — Phase C: `module_sync` op (consumer of `aitask_explain_context.sh`)
**Scope (design doc §4.3, §5 "sync scan engine", §7 Phase C):**
- New template `templates/module_syncer.md`.
- `brainstorm_crew.py`: add `module_syncer` to `BRAINSTORM_AGENT_TYPES`;
  `register_module_syncer()` — refuse if module has no `linked_task`; bundle (1)
  linked task plan (`aiplans/p<parent>/...` live or `aiplans/archived/...`),
  (2) scoped git diff via `git log --grep "(t<child>)"` + `git diff` per touched
  file, (3) `./.aitask-scripts/aitask_explain_context.sh --max-plans <N> <files>`
  stdout (REUSE — do not fork the helper family). Output node updates module
  HEAD; update `last_synced_at[<module>]`; group entry `operation: module_sync`
  + optional `sync_sources`.
- `brainstorm_schemas.py`: add `module_sync` to `GROUP_OPERATIONS`.
- `brainstorm_op_refs.py`: `module_sync:"Sync Sources"`.
- `brainstorm_app.py`: wizard branch (label "Module Sync") + `_OPERATION_HELP` +
  `_execute_design_op` branch; surface `last_synced_at` so the user sees the next
  sync's scan horizon.
**Verification:** sync refuses a subgraph with no `linked_task`; on a linked
module it consumes plan + scoped diff + explain-context and produces a synced
HEAD; `last_synced_at` advances so re-sync sees only newer context; the helper
family is unmodified (consumed via shell-out only).

### 756_5 — Phase D1: status views (badges + dashboard + deferred marker)
**Scope (design doc §4.7, §7 Phase D):** the status-visualization half; built
after A/B/C data + ops settle.
- Per-module **status badge** computed per §4.7 table (`unstarted`/`in_design`/
  `in_implementation`/`implemented`/`merged`/`deferred`) — a derived render, not
  a new op. Inputs are all existing data (per-subgraph history, `linked_task`
  frontmatter, `parents` walk for `merged`, new `deferred` marker).
- Dashboard showing the subgraph tree with per-module sync/merge state.
- Deferred-module marker (TUI binding to set `status.deferred=true`).
- **Reuse t873 TUI/dimension helpers:** `FuzzyCheckList.set_grouped_items` for the
  dashboard checklists, `group_dimensions_by_prefix` + `extract_dimensions` for
  grouped status views, `get_active_dimensions` for scope defaults (all landed by
  t873 — `brainstorm_app.py` / `brainstorm_schemas.py` / `brainstorm_dag.py`).
- Follow `aidocs/tui_conventions.md` for any Textual changes.
**Verification:** badges reflect mixed module states; deferred toggle persists;
dashboard renders the subgraph tree with per-module sync/merge state. (Covered by
the aggregate manual-verification sibling.)

### 756_6 — Phase D2: "Fast-track this module" wizard preset
**Scope (design doc §4.8, §7 Phase D):** the ergonomics half — a one-pass preset
over B2's functional `module_decompose --link-to-task` path. UC-3 is just
`module_decompose` parameterised — a presentation layer, **not** a new op.
- `brainstorm_app.py`: "Fast-track this module" wizard preset driving a
  single-module `module_decompose --link-to-task` in one pass; routes through the
  same `register_module_decomposer()` as the multi-module path.
- Reuse `FuzzyCheckList.set_grouped_items` for any grouped selection; follow
  `aidocs/tui_conventions.md`.
**Verification:** the preset creates a subgraph + linked task in a single pass and
reuses the B2 op logic (no fork). (Covered by the aggregate manual-verification
sibling.)

### Out of scope (design doc §6 open questions — recommendations stand)
Linked-task auto-archival on merge (recommend NO), nested-decompose recursion
limit (recommend none), one-time `subgraph` migration (recommend none — optional
field defaults to `_umbrella`), sync scan radius (exact-file-match for v1), sync
without a linked task (NO for v1). These are recorded as decided defaults in the
relevant child plans, not as separate tasks.

## Post-approval execution — COMPLETED (2026-06-01)

The child-creation flow ran after the t873 re-verification passed (task-workflow
Step 7 + planning.md §6.1 child-creation path). Children were first created as a
4-child set (A/B/C/D), then **re-decomposed** the same day after a scope review
split B→B1/B2 and D→D1/D2. Final state:

1. Six implementation children created via the Batch Task Creation Procedure
   (`issue_type: feature`, priority/effort per phase, full Child Task
   Documentation Requirements):
   - 756_1 Phase A · 756_2 Phase B1 · 756_3 Phase B2 · 756_4 Phase C ·
     756_5 Phase D1 · 756_6 Phase D2 (sequential auto-dep A→B1→B2→C→D1→D2).
2. Parent t756 reverted to `Ready`, `assigned_to` cleared, parent lock released —
   board auto-renders "Has children".
3. Six child plans written to `aiplans/p756/p756_<n>_<name>.md`.
4. Aggregate `manual_verification` sibling **756_7** created (verifies 756_1–756_6),
   covering the TUI/agent-launch behavior; depends on 756_6.
5. Child checkpoint: "Stop here" — children/plans written, picked later in fresh
   contexts; Satisfaction Feedback collected.

## Verification (of this decomposition task) — satisfied
- `aitask_ls.sh -v --children 756 99` lists the six children + the MV sibling
  (756_7) in dependency order (756_1→…→756_6→756_7).
- Each child file contains all five required documentation sections and references
  `aidocs/brainstorming/module_decomposition_design.md` as primary reference.
- `aiplans/p756/` contains a plan per implementation child (756_1–756_6) with
  correct metadata headers (the MV sibling is a checklist task, no plan file).
- t756 shows `status: Ready` with populated `children_to_implement`
  (`[t756_1 … t756_7]`); parent lock released.
- No source code under `.aitask-scripts/brainstorm/` is modified by this task —
  implementation is deferred to the children.
