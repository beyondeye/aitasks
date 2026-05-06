# Module Decomposition for `ait brainstorm`

Design doc for three new operations (`decompose`, `sync`, `merge`) plus
supporting data-model extensions that let a single brainstorm session
grow per-module subgraphs, fast-track individual modules into their
own implementation aitasks, and absorb the as-implemented design back
into the broader proposal.

Status: design only — no implementation has landed. The follow-up
Phase A/B/C/D tasks are listed in §7. The plan that produced this
document is `aiplans/p754_new_brainstorm_operations.md`.

## 1. Context

`ait brainstorm` today produces a single proposal-graph per task:
`br_session.yaml` carries a single `task_id`/`task_file`,
`br_graph_state.yaml` tracks a single `current_head`, and the supported
operations (`explore`, `compare`, `hybridize`, `detail`, `patch`) all
evolve that one proposal as a whole.

Three increasingly-common use cases push against this model. They are
quoted verbatim from the originating task `aitasks/t754_new_brainstorm_operations.md`,
then formalised below.

### Verbatim use cases (from t754)

> 1. We have a wide ranging proposal that add a feature but it is also
>    a bit "abstract", and we have some specific use case that exercise
>    the feature of only a part of the proposal feature. It would be
>    good if it could be possible to "decompose" the proposal in
>    multiple module and evolve/implement each module using the
>    brainstorm machinery independently, so we could extract and evolve
>    the modules first that are most relevant to some use case, refine
>    their plans but keep a reference to the wider proposal, that we
>    will refine later onces specific modules are refined/or even
>    already implemented. This new angle conflicts with the current
>    one to one connection of a proposal to a task file, need to
>    rethink if can change the brainstorming to link (two way links)
>    to multiple tasks associated with each of the modules identified
>    in the proposal that evolve/implement independently although
>    still correlated.
>
> 2. A second use case that is related to 1) is when we have a wide
>    ranging proposal and we identify a specific module/part in it
>    that we currently want to refine/implement connect to specific
>    use cases, while other parts of the proposal we need to get back
>    to later and decide later if and how to implement. We want ait
>    brainstorm data to support keeping this fluid status of the
>    proposal with parts progressing faster other parts left for
>    later.
>
> 3. Connect part/modules of the proposal to specific use cases and
>    have an operation that help use extract the modules from the
>    proposal to fast track so that we can support the specific use
>    cases we want to support while keeping the general structure of
>    the proposal and more general scope for later (i.e. we dont want
>    to loose the general framework of the prposal, we want in
>    parallel to evolve part of the proposal that directly connect
>    to specific use cases).

### UC-1 — Module decomposition (formalised)

- **Scenario.** A wide-ranging proposal P contains several modules
  M1..MN that can be refined and implemented largely independently.
- **Inputs.** A single brainstorm session for an umbrella task (T) and
  its current proposal HEAD.
- **Expected output.** N independently-evolvable subgraphs (one per
  module), each with its own HEAD, optionally each linked to its own
  aitask. The umbrella subgraph remains evolvable for the framework
  parts not covered by any single module.
- **Acceptance signal.** After decomposition, running an op
  (e.g. `explore`) targeted at module Mi changes only Mi's subgraph,
  not the umbrella and not other modules' subgraphs.

### UC-2 — Fluid implementation status (formalised)

- **Scenario.** Within one proposal, some modules need fast progress
  (use-case-driven), others should be deferred without losing the
  overall framework.
- **Inputs.** A decomposed session with N module subgraphs in mixed
  states (some refined, some only sketched, some linked to live
  aitasks, some archived).
- **Expected output.** A queryable per-module status that the TUI can
  surface as a status badge (e.g. `unstarted`, `in_design`,
  `in_implementation`, `implemented`, `merged`, `deferred`).
- **Acceptance signal.** A user can scan the session and see at a
  glance which modules are progressing, which are blocked, which
  have already been merged back, and which are deferred — without
  reading proposal markdown.

### UC-3 — Module extraction / fast-track (formalised)

- **Scenario.** From an umbrella proposal, the user wants to
  fast-track exactly one module into a real implementation aitask
  while leaving the rest of the proposal intact for later refinement.
- **Inputs.** Umbrella proposal HEAD + a single module name + the
  intent to spawn a child aitask.
- **Expected output.** A new module subgraph with `linked_task` set
  to a freshly-created aitask, the umbrella unchanged, and the wizard
  flow finishing in a single user pass (one decompose-and-link step,
  not two).
- **Acceptance signal.** Running `decompose` with one module name plus
  the "create aitask" toggle produces both the subgraph and the linked
  task in a single op invocation.

### Why a design doc, not an implementation

The originating task has `effort: low` because the deliverable is this
document. Implementation is split into four follow-up phases (§7) so
each ships independently and reviewably.

## 2. Current state recap

Anchors for the load-bearing surfaces of today's brainstorm machinery:

- Session schema: `.aitask-scripts/brainstorm/brainstorm_schemas.py:41` (`SESSION_REQUIRED`).
- Node schema: `.aitask-scripts/brainstorm/brainstorm_schemas.py:13` (`NODE_REQUIRED_FIELDS`).
- Graph state schema: `.aitask-scripts/brainstorm/brainstorm_schemas.py:35` (`GRAPH_STATE_REQUIRED`) — single `current_head` only today.
- Operation registry: `.aitask-scripts/brainstorm/brainstorm_schemas.py:56` (`GROUP_OPERATIONS`).
- Dimension prefixes: `.aitask-scripts/brainstorm/brainstorm_schemas.py:21` (`DIMENSION_PREFIXES`) — `requirements_`, `assumption_`, `component_`, `tradeoff_`.
- DAG helpers: `.aitask-scripts/brainstorm/brainstorm_dag.py` — multi-parent already supported per node; lineage walker assumes first-parent only.
- Wizard surfaces in the TUI:
  - `.aitask-scripts/brainstorm/brainstorm_app.py:120` (`_NODE_SELECT_OPS`)
  - `.aitask-scripts/brainstorm/brainstorm_app.py:122` (`_WIZARD_OP_TO_AGENT_TYPE`)
  - `.aitask-scripts/brainstorm/brainstorm_app.py:156` (`_DESIGN_OPS`)
  - `.aitask-scripts/brainstorm/brainstorm_app.py:179` (`_OPERATION_HELP`)
  - `.aitask-scripts/brainstorm/brainstorm_app.py:2669` (`action_op_help`)
  - `.aitask-scripts/brainstorm/brainstorm_app.py:4383` (`_execute_design_op`)
- Agent registration / launch: `.aitask-scripts/brainstorm/brainstorm_crew.py:44` (`BRAINSTORM_AGENT_TYPES`),  `:468` (`register_explorer`), `:514`, `:555`, `:594`, `:635` (siblings).
- Op input refs: `.aitask-scripts/brainstorm/brainstorm_op_refs.py:15` (`_OP_INPUT_SECTION`).
- Section markers: `.aitask-scripts/brainstorm/brainstorm_sections.py:46` (`_SECTION_RE`) — existing `<!-- section: name [dimensions: dim1, dim2] -->` plumbing introduced in the p571 family of tasks.

The mental model today is one session = one task = one DAG = one HEAD.
Operations target HEAD. Agents launched by `register_*()` produce new
nodes, which become the new HEAD. Existing infrastructure that we want
to **reuse** without modification:

- Per-node multiple parents in `parents` list — already the basis for `hybridize`.
- Per-group `nodes_created: list` in `br_groups.yaml` — already supports
  multi-output ops.
- Section markers in proposal markdown — already let an agent address a
  named slice of a proposal.
- The `aitask_explain_*` helper family from t369 — already bundles
  "given a list of source files, return the formatted historical
  plan/task context for them" into one bash invocation.

## 3. Gap analysis

Mapping each use case (and the post-implementation-drift concern that
arose during planning) to the missing capability:

- **(UC-1 →)** No way to designate parts of a proposal as independent
  modules with their own evolution head. Today every op targets the
  single `current_head`; there is no mechanism to fork the DAG into
  per-module branches.
- **(UC-2 →)** No per-module status. Implementation progress is a
  session-wide property today — `br_session.yaml.status` is a single
  enum, and the TUI surfaces it once. There is no way to render
  "module A: implemented; module B: deferred" without inventing the
  state for it.
- **(UC-3 →)** No operation to fork off a module subgraph; no
  operation to fold a refined module's design back up. Today's
  `hybridize` merges two sibling proposals into one — it is **not**
  the same as merging a child subgraph back into its parent. Fast-track
  also has no native path: the user would have to manually create a
  child aitask and lose the brainstorm-side linkage.
- **(drift →)** Once a module is fast-tracked into a real aitask and
  code lands, the brainstorm subgraph holds the *original* refined
  design, while the aitask's plan file accumulates "Final
  Implementation Notes" and "Post-Review Changes" that diverge from
  it. Subsequent unrelated aitasks may also touch the same area. There
  is no operation today to bring all that reality back into the
  brainstorm subgraph before merging — without it, `merge` would
  absorb a stale module design and pollute the umbrella with
  out-of-date content.

## 4. Design

The direction confirmed during planning: **one brainstorm session per
task stays the model.** Inside that single session, the DAG grows
*subgraphs per module*, each with its own HEAD recorded in
`br_graph_state.yaml`. Three new operations bracket the module
lifecycle (`decompose`, `sync`, `merge`); existing operations continue
to do the in-the-middle refinement work, gaining a thin "subgraph
selector" prefix on the wizard.

The lifecycle in one line:

```
decompose → (existing ops refine) → detail → fast-track to aitask
          → implementation → sync → merge
```

`sync` is optional — only needed when implementation actually
happened. `merge` is optional — only when the user wants the umbrella
to absorb the module's refined design.

### 4.1 Subgraph data model

`br_graph_state.yaml` extension (additive, back-compat):

```yaml
current_head: n005          # legacy single field — kept as alias of _umbrella head
current_heads:              # NEW: per-subgraph HEAD map
  _umbrella: n005
  parser:    n012
  cache:     n014
history:                    # legacy linear list — repurposed as _umbrella history
  _umbrella: [n001, n002, n005]
  parser:    [n010, n011, n012]
  cache:     [n014]
active_dimensions: [...]
module_tasks:               # NEW: optional per-module task linkage
  parser: 754_1
last_synced_at:             # NEW: per-module sync timestamp (for sync scan horizon)
  parser: 2026-05-04 14:30
```

Node YAML extension (additive, optional):

```yaml
node_id: n012
parents: [n010]
description: ...
proposal_file: br_proposals/n012.md
module_label: parser        # NEW: subgraph membership (default _umbrella)
created_at: ...
created_by_group: ...
```

**Storage choice for subgraph membership.** Membership is recorded
explicitly on the node (`module_label`) rather than recomputed via
reachability from a subgraph root. Trade-off:

- *Explicit field (chosen).* Cheap queries (filter `br_nodes/` by
  field value); ops can list candidate nodes without walking the DAG;
  one extra optional field per node.
- *Reachability-derived.* Saves the field but every op walks the DAG
  to scope itself; ambiguous when a node has cross-subgraph parents
  (which `merge` outputs do — see §4.4).

The explicit field wins because `merge` deliberately creates
cross-subgraph parent links, and a reachability rule would have to
special-case them.

**`parents` semantics.** The `parents` list keeps current semantics:
within-subgraph ancestry. Cross-subgraph parents appear only on
`merge` output nodes (a node in the destination subgraph with one
parent in the destination and one in the source subgraph). The
`module_label` on a merge-output node names the *destination*
subgraph it joins.

### 4.2 New op: `decompose`

- **Targets** the HEAD of any subgraph (typically `_umbrella`
  initially; nested decomposition is allowed).
- **Inputs.**
  - HEAD node.
  - A list of module names. Names can be supplied manually OR
    identified by an agent. Default mode: agent-driven, with the
    agent prompted to use the proposal's existing
    `<!-- section: ... -->` markers and `component_*` dimensions as
    candidate module boundaries.
  - Optional `--from-sections` flag for deterministic-from-section-markers
    extraction when the parent proposal already has clean sections
    (skip the agent, slice the proposal directly).
  - Optional per-module `--link-to-task` toggle (UC-3 fast-track).
- **Outputs.**
  - For each module `M`: a new subgraph root node `nXXX` with
    `module_label=M`, `parents=[<HEAD>]`. The umbrella HEAD becomes
    the in-DAG parent of every module subgraph root.
  - `current_heads[M] = nXXX` set in `br_graph_state.yaml`.
  - `history[M] = [nXXX]` initialised.
  - Each new root's `proposal_file` is seeded with the slice of the
    parent proposal scoped to that module. The cut-line is the
    existing `<!-- section: M -->` marker pair when present;
    otherwise the agent generates a fresh module-scoped proposal.
  - `br_groups.yaml` gets one new entry: `operation: decompose`,
    `nodes_created: [nXXX_for_M1, nXXX_for_M2, ...]`. The existing
    `nodes_created: list` field already supports multi-output groups
    — no group-schema change is needed.
  - If `--link-to-task` was set for module M: a fresh aitask is
    created via `aitask_create.sh --batch --parent <umbrella_task> --name <M>`,
    and `module_tasks[M]` is set to the new task ID.
- **Side effect.** The umbrella's HEAD does **not** change; only the
  per-module HEADs are added. The umbrella stays evolvable so the
  user can keep refining the framework while modules diverge.

### 4.3 New op: `sync` (pull as-implemented design back into the subgraph)

- **Targets** a module subgraph that has a `linked_task` (the
  fast-tracked aitask). Refuses to run on a subgraph without a
  linked task — there is nothing to sync from.
- **Inputs (assembled by `register_syncer`).**
  1. **Linked task plan file** —
     `aiplans/p<parent>/p<parent>_<child>_<name>.md` while
     implementing, `aiplans/archived/p<parent>/...` after archival.
     Especially the `## Final Implementation Notes` and
     `## Post-Review Changes` sections.
  2. **Code diff scoped to the linked task's commits.** Use
     `git log --grep "(t<child>)"` (the same commit-suffix
     convention `aitask_issue_update.sh` uses to find a task's
     commits) to enumerate the commit range. Then `git diff` per
     file across that range. Resulting per-file diffs bundle into
     the syncer's input. The list of files touched is also captured
     for input (3).
  3. **Historical plan/task context for the touched files.** Call
     the existing helper:

     ```bash
     ./.aitask-scripts/aitask_explain_context.sh --max-plans <N> <file1> [file2...]
     ```

     where `<file1...>` is the touched-file list from input (2). The
     helper (built in t369) already orchestrates a codebrowser cache
     at `.aitask-explain/codebrowser/`, runs
     `aitask_explain_extract_raw_data.sh` to gather commit history
     plus aitask/aiplan files for the inputs, and pipes through
     `aitask_explain_format_context.py` to produce formatted
     markdown on stdout. Its output is bundled directly into the
     syncer's input as the "subsequent aitasks context" section.

     **Reuse, do not reimplement.** The helper family is the
     supported public interface for this query — see §5 for the
     full file list.
- **Outputs.**
  - A new node `nZZZ` in the module subgraph with
    `module_label=<module>`, `parents=[<previous module HEAD>]`, an
    updated `proposal_file` reflecting the as-implemented design,
    and an updated `plan_file` mirroring the aitask's final plan.
  - `current_heads[<module>] = nZZZ`;
    `history[<module>].append(nZZZ)`.
  - `last_synced_at[<module>]` is updated to `now()` so the next
    sync only sees genuinely-new context (see §6 "Sync scan time
    horizon").
  - `br_groups.yaml` entry: `operation: sync`,
    `nodes_created: [nZZZ]`, `subgraph: <module>`, plus a new
    optional `sync_sources` field listing the input artifacts
    (linked task plan path, commit range, list of subsequent aitask
    plans consulted) for traceability.
- **Side effect on the subgraph.** The synced node becomes the new
  HEAD. If the user wants to re-refine after sync (e.g. `patch`),
  they build on top of the synced HEAD — the original
  pre-implementation design is still reachable in history.
- **No side effects** on the linked aitask, its plan file, or any of
  the subsequent aitasks consulted. Sync is read-only on the aitasks
  side.

### 4.4 New op: `merge` (up only)

- **Targets** a module subgraph HEAD (the *source*) plus its parent
  subgraph (the *destination* — usually `_umbrella`, but in nested
  cases it can be the immediate ancestor module).
- **Inputs.** Source subgraph HEAD plus destination subgraph
  (resolved from the source's root node's `parents`).
- **Outputs.**
  - A new node `nYYY` in the destination subgraph with
    `module_label=<destination>`,
    `parents=[<destination HEAD>, <source HEAD>]` — a 2-parent node.
    The DAG already supports this (per-node multiple parents was
    introduced for `hybridize`); the second parent records the
    merge provenance.
  - `current_heads[<destination>] = nYYY`.
  - `history[<destination>].append(nYYY)`.
  - The source subgraph's HEAD does **not** change. Future ops on
    the source subgraph would build on top of the pre-merge HEAD;
    if a re-merge is desired, a fresh `merge` op is run.
  - The merged proposal markdown is regenerated by an agent
    (template `merger.md`) that takes the destination's pre-merge
    proposal and the source's proposal as inputs and emits the new
    destination proposal absorbing the refined module content.
- **Side effect on `module_tasks`.** If the source had a
  `linked_task`, the linkage is preserved — it remains attached to
  the source subgraph. Whether the linked task auto-archives on
  merge is OUT OF SCOPE for v1; recorded as an open question in §6.
- **"Only up" guard.** The op refuses to run if `<destination>` is
  not in the chain of `parents` of the source root. No cross-sibling
  merges, no descent. The validator
  (`is_ancestor_subgraph(source, destination)`) runs at op-launch
  time, before any agent input is assembled.

### 4.5 Existing ops become module-aware

`explore`, `compare`, `hybridize`, `detail`, `patch` all currently
target the single `current_head`. They become module-scoped: the
wizard gains a "subgraph selector" step (default: most-recently-touched
subgraph) before the node-selection step. Behind the scenes:

- The wizard's step 2 (`_NODE_SELECT_OPS`) filters node candidates by
  `module_label == <selected_subgraph>`.
- The op's group entry in `br_groups.yaml` records the subgraph it
  ran inside (new optional `subgraph: <module>` field — defaults to
  `_umbrella` for back-compat with existing groups).
- Agent prompt templates get a small front-matter addition:
  "subgraph context: <module_label>" so the LLM does not blur module
  boundaries.

This is the chunk of work that touches the most existing code; §5
lists each op's wizard branch and template change as a checklist item
under Phase B of the roadmap.

### 4.6 Tree-shape evolution narrative (worked example)

A canonical lifecycle, traced step-by-step. State is shown after each
step.

1. **Initial proposal.** `current_heads = {_umbrella: n001}`.
2. **`explore` on n001 → n002 (umbrella refined).**
   `current_heads = {_umbrella: n002}`.
3. **`decompose` on n002.** Spawns parser-root n010 and cache-root n014.
   `current_heads = {_umbrella: n002, parser: n010, cache: n014}`.
   `module_tasks = {}` (nothing fast-tracked yet).
4. **`explore` on parser HEAD (n010) → n011, n012.**
   `current_heads = {_umbrella: n002, parser: n012, cache: n014}`.
5. **`detail` on parser HEAD (n012).** Adds `n012_plan.md`. The user
   chooses to fast-track:
   `aitask_create.sh --batch --parent 754 --name parser_module ...`
   creates t754_1; `module_tasks[parser] = 754_1` is written.
6. **Implementation happens outside brainstorm.** t754_1 enters
   `Implementing`, then archives `Done`. Its plan file accumulates a
   `## Final Implementation Notes` section and a few
   `## Post-Review Changes` entries. Meanwhile, an unrelated
   follow-up task t760 also touches files in the parser area.
7. **`sync` on parser HEAD.** Reads t754_1's archived plan + git diff
   for the parser files (commits matching `(t754_1)`) +
   `aitask_explain_context.sh --max-plans 5 <parser files>` (which
   surfaces t760's plan and content). Produces n013 — a synced parser
   HEAD reflecting the as-implemented design.
   `current_heads[parser] = n013`. Subgraph history:
   `[n010, n011, n012, n013]`. `last_synced_at[parser] = now`.
8. **`merge` parser → umbrella.** New node n020 in `_umbrella` with
   `parents=[n002, n013]`. `current_heads[_umbrella] = n020`.
   `current_heads[parser] = n013` (unchanged, frozen).
9. **`decompose` on n020.** Can now fork *new* modules off the
   enriched umbrella, OR fork a `parser_v2` if more refinement is
   wanted on top of the merged design.

This narrative is the load-bearing visual of the design. Readers get
the "branches grow, sync, merge back, regrow" mental model from this
single example. Note that step 7 (sync) is **only** required because
step 6 (implementation) happened — if a module is decomposed and
merged purely as a design exercise without ever fast-tracking to
implementation, sync is skipped and step 8 follows step 5 directly.

### 4.7 Fluid status (UC-2) is a derived view, not a new op

A module's status is computed from
`(subgraph_state, linked_task_state)`:

| Status              | Computed from                                                                  |
|---------------------|--------------------------------------------------------------------------------|
| `unstarted`         | Only the subgraph root exists.                                                 |
| `in_design`         | Subgraph has nodes beyond root, no `linked_task` or `linked_task` is `Ready`.  |
| `in_implementation` | `linked_task` is `Implementing`.                                               |
| `implemented`       | `linked_task` is `Done` (archived).                                            |
| `merged`            | Source HEAD appears in `parents` of some node in the destination subgraph.    |
| `deferred`          | Explicit user marker (TUI binding); orthogonal to the others.                  |

All inputs to this table are already-existing data: subgraph node
counts come from the per-subgraph history list; `linked_task` status
comes from reading the task file's frontmatter; `merged` is detected by
walking `parents` lists on destination-subgraph nodes; `deferred` is a
new optional field. No new ops are introduced for status — the TUI's
status badge is a render of the computation above.

### 4.8 UC-3 (extract / fast-track) is `decompose --modules=one + linked_task`

The "extract one module to fast-track" use case is just `decompose`
invoked with a single module name plus the optional `--link-to-task`
toggle. The wizard surfaces this as a one-step flow ("Fast-track this
module") in addition to the multi-module decompose path. Internally
both paths go through the same `register_decomposer()` call;
`--link-to-task` adds the post-decompose `aitask_create.sh --batch`
step plus the `module_tasks` write.

This is why UC-3 does **not** need its own operation: it is a
parameterisation of `decompose`, not a new lifecycle phase.

### 4.9 Why THREE new ops, not one

The originating task hinted at "best single operation for most common
use cases". This design proposes three. Rationale:

- `decompose` is **divergent** (one node → many subgraph roots).
- `sync` is **reconciliatory** (external aitask reality → one new
  node in the subgraph). It runs only when implementation has
  happened, and only on a subgraph with a `linked_task`.
- `merge` is **convergent** (many subgraph descendants → one parent
  revision).
- The mental and lifecycle phases are distinct: decompose is at the
  start of branch growth, sync is mid-late (after
  fast-track-implementation), merge is at the end. Conflating any
  two would force one op to take a polymorphic input shape AND make
  a lifecycle-stage decision implicitly.
- The "branches grow, sync if implemented, merge back, regrow"
  rhythm only stays clean if each phase is its own named op.
  Otherwise the round-trip becomes an opaque "manage modules" op
  with subcommands, which is worse than three small named ops.
- Specifically: **auto-syncing inside merge** would hide the synced
  state behind a black-box step, making it impossible to inspect
  "what did we absorb?" before the parent revision is created.
  Keeping sync explicit lets the user review the synced subgraph
  HEAD before triggering merge.

UC-3 (fast-track) is the one place a single op suffices — it is just
`decompose` with one module and the `--link-to-task` toggle (§4.8).

### 4.10 Cross-cutting: agent prompts and templates

- **New template** `.aitask-scripts/brainstorm/templates/decomposer.md`.
  Input: parent proposal + module list (optional, agent identifies
  if absent). Output: one proposal-slice section per module, plus a
  brief "module summary" header.
- **New template** `.aitask-scripts/brainstorm/templates/syncer.md`.
  Input: linked task's plan file + scoped git diff bundle + the
  subsequent-aitasks context bundle (from
  `aitask_explain_context.sh`). Output: refined module proposal +
  plan reflecting as-implemented state.
- **New template** `.aitask-scripts/brainstorm/templates/merger.md`.
  Input: destination proposal + source module proposal. Output:
  destination proposal regenerated to absorb the source module's
  refined design.
- **Existing templates** (explorer, comparator, synthesizer,
  detailer, patcher) get a small front-matter addition: "subgraph
  context: <module_label>" so the agent stays in scope.

## 5. Touchpoint checklist for implementation

The "add a new op" 5-layer recipe (the recipe is induced from how
existing ops are wired today; it is not stored as a single source of
truth in the codebase). Expanded for each of the THREE new ops:

For `decompose`, `sync`, and `merge`:

- `.aitask-scripts/brainstorm/brainstorm_schemas.py:56` (`GROUP_OPERATIONS`)
  ← `decompose`, `sync`, `merge`.
- `.aitask-scripts/brainstorm/brainstorm_app.py`:
  - `:120` (`_NODE_SELECT_OPS`) — add decompose, sync, merge (all
    three need a node-selection step: decompose picks the HEAD to
    split, sync picks the module subgraph HEAD, merge picks the
    source subgraph HEAD).
  - `:122` (`_WIZARD_OP_TO_AGENT_TYPE`) — add
    `decompose: decomposer`, `sync: syncer`, `merge: merger`.
  - `:156` (`_DESIGN_OPS`) — three new tuples.
  - `:179` (`_OPERATION_HELP`) — three new dict entries (title,
    summary, reads_from_parent, produces, use_cases).
  - `:4383` (`_execute_design_op`) — three new `elif` branches
    calling `register_decomposer/syncer/merger`.
- `.aitask-scripts/brainstorm/brainstorm_crew.py`:
  - `:44` (`BRAINSTORM_AGENT_TYPES`) — add decomposer, syncer,
    merger.
  - New `register_decomposer()`, `register_syncer()`,
    `register_merger()` modeled after `register_explorer()`
    (`:468`). `register_syncer()` is the heaviest — it bundles the
    linked task plan, the scoped git diff, and the
    `aitask_explain_context.sh` output into the agent input.
- `.aitask-scripts/brainstorm/brainstorm_op_refs.py:15` (`_OP_INPUT_SECTION`)
  — add entries (`decompose: "Decomposition Plan"`,
  `sync: "Sync Sources"`, `merge: "Merge-Up Rules"`). Note:
  `hybridize` already uses `"Merge Rules"` — pick the distinct
  `"Merge-Up Rules"` label for `merge` to avoid section-name
  collision.
- New templates (one per new op):
  `.aitask-scripts/brainstorm/templates/decomposer.md`,
  `.aitask-scripts/brainstorm/templates/syncer.md`,
  `.aitask-scripts/brainstorm/templates/merger.md`.

For the **data-model layer** (separate from the ops themselves):

- `.aitask-scripts/brainstorm/brainstorm_schemas.py:35`
  (`GRAPH_STATE_REQUIRED`) — extend to include `current_heads`,
  validate as map of `<module>: <node_id>`. Keep `current_head` as
  legacy alias of `_umbrella`.
- `.aitask-scripts/brainstorm/brainstorm_schemas.py` `NODE_OPTIONAL_FIELDS`
  — add `module_label`.
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — `set_head`,
  `get_head`, `get_node_lineage`, `next_node_id` all need a
  `module` parameter (default `_umbrella` for back-compat).
- `.aitask-scripts/brainstorm/brainstorm_session.py`
  (`init_session`) — initialise `current_heads = {_umbrella: <root>}`
  and `module_tasks = {}`.

For the **merge guard**:

- `.aitask-scripts/brainstorm/brainstorm_dag.py` — new helper
  `is_ancestor_subgraph(source, destination)` to enforce "merge only
  up". Walks the parent-of-root chain.

For the **sync scan engine**:

- **Reuse, don't reimplement.** The existing helper family
  (built in t369) already does this exact job: given a list of
  source files, return formatted historical-plan/task-context
  markdown. Sync's `register_syncer()` shells out to it, captures
  stdout, and bundles into the agent input. The family is:
  - `.aitask-scripts/aitask_explain_context.sh` — orchestrator with
    `--max-plans N <files>` interface.
  - `.aitask-scripts/aitask_explain_extract_raw_data.sh` — raw
    git/aitask/aiplan extractor.
  - `.aitask-scripts/aitask_explain_format_context.py` — markdown
    formatter.
  - `.aitask-scripts/aitask_explain_process_raw_data.py` — internal
    processor.
  - `.aitask-scripts/aitask_explain_runs.sh`,
    `.aitask-scripts/aitask_explain_cleanup.sh` — cache lifecycle
    helpers.
  - Cache lives at `.aitask-explain/codebrowser/` and is shared with
    codebrowser's TUI.
- Phase C's implementation task should NOT modify these helpers,
  only consume them. If the syncer needs a different output shape
  (e.g. per-file structured JSON instead of markdown), surface that
  as a follow-up task that adds a flag to
  `aitask_explain_context.sh` rather than forking the scan logic.

## 6. Open questions

- **Agent-driven vs deterministic decomposition.** Default to
  agent-driven; offer a `--from-sections` flag for
  deterministic-from-section-markers when the parent proposal
  already has clean sections.
- **Linked-task auto-archival on merge.** Should merging a module
  force-archive its linked_task? Recommend NO (orthogonal
  lifecycles).
- **Nested decompose/sync/merge.** A module subgraph can itself be
  `decompose`d. Recursion limit? Recommend none, but flag for
  review.
- **`module_tasks` storage.** Stored in `br_graph_state.yaml` (this
  design) or `br_session.yaml`? Recommend `br_graph_state.yaml`
  since it is lifecycle state, not session metadata.
- **Conflict on merge when destination has evolved.** When the
  destination subgraph evolved while the source was being refined,
  the merger agent absorbs the conflict. Record this as a behaviour
  the agent prompt must address (otherwise the agent might
  silently drop destination-side updates).
- **Existing groups (`subgraph` field absent).** Need a one-time
  migration to fill in `subgraph: _umbrella`? Recommend NO migration
  — make the field optional with `_umbrella` default.
- **Sync scan radius — what counts as "the same area"?** Files
  exactly matching the linked task's touched-file list, anything in
  the same directory, or a file-rename-aware reachability set?
  Recommend exact-file-match for v1 (cheapest, most predictable),
  with directory-level expansion as a future flag.
- **Sync scan time horizon.** All aitasks that completed since the
  linked task archived, or only since the last `sync` ran on this
  module? Recommend "since last sync" so re-syncing later is cheap
  and only sees genuinely-new context. The
  `last_synced_at[<module>]` field in §4.1 enables this.
- **Sync without a linked task?** Should `sync` also be runnable on
  a non-fast-tracked subgraph if the user manually pastes
  implementation context? Recommend NO for v1 — keep sync tied to
  `linked_task`. Free-form context absorption is what `patch` is
  for.
- **Sync-then-merge as a fused op?** Question explicitly raised and
  rejected (see §4.9) — sync's output node should be reviewable
  before merge fires.

## 7. Roadmap (out of scope here)

Four follow-up implementation tasks. Each is bounded enough to be a
single aitask, ordered by dependency:

### Phase A — data model

- `current_heads` map and `module_label` on nodes.
- `module_tasks` map and `last_synced_at` per module.
- `set_head(module=...)` / `get_head(module=...)` plumbing in
  `brainstorm_dag.py`.
- `is_ancestor_subgraph(source, destination)` validator.
- Schema validators in `brainstorm_schemas.py` updated.
- Wizard step inserts a "subgraph selector" defaulting to
  `_umbrella` so existing flows are unchanged.
- No new ops yet. Existing ops continue to operate on `_umbrella`.

### Phase B — `decompose` + `merge` ops

- Templates: `decomposer.md`, `merger.md`.
- `register_decomposer()` and `register_merger()` in
  `brainstorm_crew.py`.
- Wizard branches and help-dict entries for both ops.
- Op refs entries.
- Group entry's optional `subgraph` field plumbed through.
- Ancestry guard wired into the merge wizard step.

These two ops are paired in one task because they share validators
and the wizard subgraph-selector machinery — splitting them would
force two passes through the same wizard plumbing.

### Phase C — `sync` op (consumer of `aitask_explain_context.sh`)

- Template: `syncer.md`.
- `register_syncer()` that:
  1. Resolves `linked_task` for the chosen module (refuses if
     absent).
  2. Reads the linked task's plan (live or archived).
  3. Resolves the touched-file list via
     `git log --grep "(t<child>)"` + `git diff`.
  4. Shells out to
     `aitask_explain_context.sh --max-plans <N> <files>`.
  5. Bundles all three input streams into the agent input.
  6. Updates `last_synced_at[<module>]` in `br_graph_state.yaml`.
- Wizard branch + help-dict entry.
- `last_synced_at` guard in the wizard so the user sees how much
  content the next sync would consume.

Since the heavy-lifting scan engine already exists, Phase C is
lighter than originally estimated — most of the work is glue + the
syncer template + wizard plumbing.

### Phase D — TUI surfaces and status views

- Per-module status badges (computed per §4.7) in the brainstorm
  dashboard.
- "Fast-track this module" wizard preset (UC-3) on top of
  `decompose`.
- Dashboard showing the subgraph tree with merge/sync state per
  module.
- Deferred-module marker (TUI binding to set
  `status.deferred=true`).

Built last because it depends on A/B/C data-model and ops being
settled. Trying to do it earlier would force it to track in-flight
schema changes.

---

This document is the **primary reference** for Phases A–D. Any
deviation from it during implementation must be recorded in the
phase task's "Final Implementation Notes" so this doc can be revised
or annotated rather than silently outgrown.
