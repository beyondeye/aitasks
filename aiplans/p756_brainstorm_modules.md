---
Task: t756_brainstorm_modules.md
Worktree: (none — planned on current branch)
Branch: main
Base branch: main
Status: DEFERRED — blocked on t873; re-verify before implementing
---

# t756 — Brainstorm Modules: Parent Decomposition Plan

## ⛔ Sequencing — DEFERRED, BLOCKED on t873 (re-verify before implementing)

**This plan is committed but NOT to be executed yet.** t756 is gated behind
`t873_fix_brainstorm_dimension_proposal_linking_and_compare` (`depends: [873]`,
status `Postponed`). The proposal **dimension** model that modules build on is
being actively reworked in t873, and t756's design rests directly on it:

- t873 #1 — glob/prefix expansion of `<!-- section: name [dimensions: KEY*] -->`
  tags + validation of section tags against a node's real dimension keys. This is
  exactly the `component_*` + section-marker machinery `module_decompose` relies
  on for boundary hints (§4.2 / Phase B).
- t873 #4/#5 — compare-wizard dimension scoping, default-to-`active_dimensions`,
  and a possible dimension "full-name registry" field. This can change the
  `active_dimensions` data model that Phase A's "session-wide vocabulary"
  decision rests on.

**On the next pick of t756 (after t873 lands), RE-VERIFY this entire plan against
the as-landed t873 design before creating any children.** Specifically:
1. "Modules × dimensions × sections" + Phase A's `active_dimensions` decision —
   does t873 keep it a flat session-wide list, or introduce a registry/new field?
2. Phase B's `module_decomposer` boundary-hint approach — does it now consume
   t873's glob-expanded section↔dimension linking instead of exact-match?
3. Whether t873 adds new fields/helpers the children should reuse rather than
   reinvent.

This plan is saved now so the settled decisions (`module_` op naming everywhere,
the 4-phase split, session-wide dimensions) are not lost during the t873 redesign.

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
**On the next pick of t756, re-verify this plan against the as-landed t873
design before creating any children.**

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

> **t873 caveat:** this section is the part most exposed to the t873 dimension
> redesign — re-verify it (per the Sequencing banner) before implementing.

## Decomposition (4 children, dependency-ordered)

Children auto-depend on prior siblings, enforcing A→B→C→D. Each child file gets
the full per-child context required for fresh-context execution (Child Task
Documentation Requirements: Context, Key Files, Reference Patterns,
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
  subgraph-selector scaffolding only if cheap; otherwise the selector lands in B
  (note this boundary in the child file).
**Verification:** unit-style checks that legacy single-head sessions still load
and validate; new map fields round-trip; `is_ancestor_subgraph` correctness;
existing brainstorm tests still pass.

### 756_2 — Phase B: `module_decompose` + `module_merge` ops (paired)
**Scope (design doc §4.2, §4.4, §4.5, §4.8, §4.10, §5 op-recipe):** Paired in
one task because they share the validators (ancestry guard) and the wizard
subgraph-selector machinery (design doc §7 Phase B rationale).
- New templates `templates/module_decomposer.md`, `templates/module_merger.md`.
- `brainstorm_crew.py`: add `module_decomposer`/`module_merger` to
  `BRAINSTORM_AGENT_TYPES`; `register_module_decomposer()` (multi-output: one
  subgraph-root node per module, `--from-sections` slice path vs agent-driven;
  optional `--link-to-task` fast-track via `aitask_create.sh --batch --parent
  <umbrella>`), `register_module_merger()` (2-parent output node in destination
  subgraph; ancestry guard at launch).
- `brainstorm_schemas.py`: add `module_decompose`,`module_merge` to
  `GROUP_OPERATIONS`; optional `subgraph` field on group entries (default
  `_umbrella`).
- `brainstorm_op_refs.py`: `_OP_INPUT_SECTION` entries
  `module_decompose:"Decomposition Plan"`, `module_merge:"Merge-Up Rules"`
  (distinct from synthesize's "Merge Rules").
- `brainstorm_app.py`: `_DESIGN_OPS` (labels "Module Decompose"/"Module Merge"),
  `_WIZARD_OP_TO_AGENT_TYPE`, `_OPERATION_HELP`, `_execute_design_op` branches;
  insert the **subgraph selector** wizard step before node-select; make existing
  ops module-aware (filter node candidates by `module_label`, record `subgraph`
  in group entry, prompt front-matter "subgraph context: <module_label>").
- UC-3 fast-track = `module_decompose --modules=one + --link-to-task` (one-step
  wizard preset; the polished preset UI is Phase D, the functional path is here).
**Verification:** decompose on `_umbrella` HEAD spawns per-module roots with
correct `module_label`/`parents`/`current_heads`; merge produces a 2-parent
destination node and refuses non-ancestor destinations; an existing op targeted
at a module changes only that subgraph.

### 756_3 — Phase C: `module_sync` op (consumer of `aitask_explain_context.sh`)
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

### 756_4 — Phase D: TUI surfaces & status views
**Scope (design doc §4.7, §4.8, §7 Phase D):** Built last; depends on A/B/C
data + ops being settled.
- Per-module **status badge** computed per §4.7 table (`unstarted`/`in_design`/
  `in_implementation`/`implemented`/`merged`/`deferred`) — a derived render, not
  a new op. Inputs are all existing data (per-subgraph history, `linked_task`
  frontmatter, `parents` walk for `merged`, new `deferred` marker).
- "Fast-track this module" wizard **preset** on top of `module_decompose
  --link-to-task`.
- Dashboard showing the subgraph tree with per-module sync/merge state.
- Deferred-module marker (TUI binding to set `status.deferred=true`).
- Follow `aidocs/tui_conventions.md` for any Textual changes.
**Verification:** manual TUI walk-through (covered by the aggregate
manual-verification sibling) — badges reflect mixed module states; fast-track
preset creates subgraph + linked task in one pass; deferred toggle persists.

### Out of scope (design doc §6 open questions — recommendations stand)
Linked-task auto-archival on merge (recommend NO), nested-decompose recursion
limit (recommend none), one-time `subgraph` migration (recommend none — optional
field defaults to `_umbrella`), sync scan radius (exact-file-match for v1), sync
without a linked task (NO for v1). These are recorded as decided defaults in the
relevant child plans, not as separate tasks.

## Post-approval execution (DEFERRED until t873 lands)

> These steps are the agreed child-creation flow, **to be run only after the
> Sequencing re-verification passes**. They are NOT executed in the current run.

Because planning runs in read-only plan mode, **all creation happens after
approval** (task-workflow Step 7 + planning.md §6.1 child-creation path):

1. For each child A–D, create via the **Batch Task Creation Procedure**:
   `aitask_create.sh --batch --parent 756 --name <phase_name> ...` with
   `issue_type: feature`, priority/effort per phase, and a full description
   meeting the Child Task Documentation Requirements.
2. Revert parent t756 to `Ready` and clear `assigned_to`
   (`aitask_update.sh --batch 756 --status Ready --assigned-to ""`); release the
   parent lock (`aitask_lock.sh --unlock 756`). The board auto-renders t756 as
   "Has children".
3. Write all four child plans to `aiplans/p756/p756_<n>_<name>.md` (metadata
   header per planning.md; leverage this exploration), then
   `./ait git add aiplans/p756/ && ./ait git commit -m "ait: Add t756 child
   implementation plans"`.
4. **Manual-verification sibling offer** (auto, ≥2 children): offer an aggregate
   `manual_verification` sibling covering the TUI/agent-launch behavior across
   children (very apt — Phase D + live agent ops). Created via
   `aitask_create_manual_verification.sh` if accepted.
5. **Child task checkpoint** (always interactive): "Start first child" →
   `/aitask-pick 756_1`; or "Stop here" → run Satisfaction Feedback and end.

## Verification (of this decomposition task, once executed)
- `aitask_ls.sh -v --children 756 99` lists the four children (plus MV sibling
  if added) in dependency order.
- Each child file contains all five required documentation sections and
  references `aidocs/brainstorming/module_decomposition_design.md` as primary
  reference.
- `aiplans/p756/` contains a plan per child with correct metadata headers.
- t756 shows `status: Ready` with populated `children_to_implement`; parent lock
  released.
- No source code under `.aitask-scripts/brainstorm/` is modified by this task —
  implementation is deferred to the children.
