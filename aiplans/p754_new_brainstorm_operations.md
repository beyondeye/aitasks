---
Task: t754_new_brainstorm_operations.md
Worktree: (current branch — fast profile, no worktree)
Branch: main
Base branch: main
---

# Plan: Design doc for ait brainstorm subgraph-per-module + decompose/sync/merge operations (t754)

## Context

`ait brainstorm` today produces a single proposal-graph per task: `br_session.yaml` carries a single `task_id`/`task_file`, `br_graph_state.yaml` tracks a single `current_head`, and the supported operations (`explore`, `compare`, `hybridize`, `detail`, `patch`) all evolve that one proposal as a whole. Three increasingly-common use cases push against this:

1. **Module decomposition** — a wide-ranging proposal we want to split into modules, each refined/implemented through the brainstorm machinery on its own track, with optional two-way links to per-module aitasks.
2. **Fluid implementation status** — within one proposal, some modules need fast progress, others should be deferred without losing the overall framework.
3. **Module extraction (fast-track)** — pull one module out of the proposal to run a focused use-case-driven brainstorm/implementation pass while the rest of the proposal stays intact for later.

`effort: low` is set on this task because the deliverable is a **design document**, not the implementation of any new operation. The actual op + data-model + UI work will be split into follow-up implementation tasks captured at the end of the design doc.

## Direction (confirmed with user)

**One brainstorm session per task stays the model.** The session's DAG grows *subgraphs per module*, each with its own HEAD recorded in `br_graph_state.yaml`. **Three new operations** mark the boundaries of the module lifecycle (existing ops continue to do the in-the-middle refinement work):

- **`decompose`** — splits a node (typically the umbrella HEAD) into N module subgraph roots, each with its own HEAD entry.
- **`sync`** — pulls the *as-implemented* design of a fast-tracked module back into its subgraph. Reads the linked aitask's plan file (live or archived) **plus** the actual code diff scoped to files the task touched, **plus** the historical plan/task context for those files via the existing `aitask_explain_context.sh` helper (which already does the "find aitasks/aiplans that touched these source files" sweep with a cache in `.aitask-explain/codebrowser/`). Produces a new HEAD node in the module subgraph that absorbs all of this drift, so a subsequent `merge` reflects reality rather than the original plan.
- **`merge`** — pushes a (typically synced) module subgraph's HEAD content back UP into its parent subgraph, producing a new parent revision that absorbs the refined module design. **Merge is only "up"** — never sibling-to-sibling, never down — which keeps the design process naturally evolving in the shape of the tree: branches grow, sync if implementation happened, merge back into the parent, then new branches sprout from the enriched parent.

This reuses the existing single-session/single-crew-worktree machinery (no per-module crew worktrees, no new agentcrew explosion) while granting each module true parallel evolution because each subgraph has its own HEAD that ops target independently.

Multi-task linkage is **optional per-module** — a subgraph can declare a `linked_task` (existing or freshly-created via `aitask_create.sh --batch`) when it gets fast-tracked for implementation. The umbrella session still has 1:1 linkage to its own task as today.

The lifecycle in one line: `decompose → (existing ops refine) → detail → fast-track to aitask → implementation → sync → merge`. Sync is optional (only needed when implementation happened); merge is optional (only when the user wants the umbrella to absorb the module's refined design).

## Doc Location

Write to `aidocs/brainstorming/module_decomposition_design.md` (under the existing `aidocs/brainstorming/` directory that already holds `brainstorm_engine_architecture.md`, `building_an_iterative_ai_design_system.md`, etc.). The user originally suggested `aidocs/brainstorm_module_decomposition.md` at the top level; the subdirectory placement is the recommendation, final path confirmed at Step 8 review.

## Doc Structure (what the writing step produces)

The design doc will have these sections, in this order. Each section ends with file-path/line-number anchors into the current code so future implementation tasks can land cleanly.

### 1. Context

Quote the three use cases verbatim from `aitasks/t754_new_brainstorm_operations.md`. For each, formalise into a UC-N block: scenario, inputs, expected outputs, acceptance signal.

### 2. Current state recap (terse, with anchors)

- Session schema: `.aitask-scripts/brainstorm/brainstorm_schemas.py:41` (`SESSION_REQUIRED`).
- Operation registry: `brainstorm_schemas.py:56` (`GROUP_OPERATIONS`).
- Graph state: `brainstorm_schemas.py:35` (`GRAPH_STATE_REQUIRED`) — single `current_head` only today.
- DAG: `brainstorm_dag.py` — multi-parent already supported per node.
- Agent registration / launch: `brainstorm_crew.py:468` ff. (`register_explorer` and siblings); `brainstorm_app.py:4408` (`_execute_design_op`).
- Wizard surfaces: `brainstorm_app.py:120` (`_NODE_SELECT_OPS`), `:122` (`_WIZARD_OP_TO_AGENT_TYPE`), `:156` (`_DESIGN_OPS`), `:179` (`_OPERATION_HELP`).
- Op input refs: `.aitask-scripts/brainstorm/brainstorm_op_refs.py:15` (`_OP_INPUT_SECTION`).
- Section-aware proposal infra: `brainstorm_sections.py` — existing `<!-- section: name [dimensions: ...] -->` markers (from p571 family).

### 3. Gap analysis

- (1→) No way to designate parts of a proposal as independent modules with their own evolution head.
- (2→) No per-module status — implementation progress is currently a session-wide property.
- (3→) No operation to fork off a module subgraph; no operation to fold a refined module's design back up. Today's `hybridize` merges two sibling proposals; it is **not** the same as merging a child subgraph back into its parent.
- (drift→) Once a module is fast-tracked into a real aitask and code lands, the brainstorm subgraph holds the original refined design while the aitask's plan file accumulates "Final Implementation Notes" and "Post-Review Changes" that diverge from it. Subsequent unrelated aitasks may also touch the same area. There is no operation to bring all that reality back into the brainstorm subgraph before merging.

### 4. Design

#### 4.1 Subgraph data model

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

Subgraph membership is recorded explicitly on the node (`module_label`) rather than recomputed via reachability — keeps queries cheap and lets ops filter `br_nodes/` by module without walking the DAG.

The `parents` list keeps current semantics: within-subgraph ancestry. Cross-subgraph parents appear only on `merge` output nodes (see §4.3).

#### 4.2 New op: `decompose`

- **Targets** the HEAD of any subgraph (typically `_umbrella` initially; nested decomposition allowed).
- **Inputs:** HEAD node + a list of module names. Names can be supplied manually OR identified by an agent (default mode: agent-driven from the proposal's existing `<!-- section: ... -->` markers and `component_*` dimensions).
- **Outputs:**
  - For each module `M`: a new subgraph root node `nXXX` with `module_label=M`, `parents=[<HEAD>]` (the umbrella HEAD becomes the in-DAG parent of every module subgraph root).
  - `current_heads[M] = nXXX` set in `br_graph_state.yaml`.
  - `history[M] = [nXXX]` initialized.
  - Each new root's `proposal_file` is seeded with the slice of the parent proposal scoped to that module (existing section-marker plumbing from `brainstorm_sections.py` is the natural cut-line).
  - `br_groups.yaml` gets one new entry: `operation: decompose`, `nodes_created: [nXXX_for_M1, nXXX_for_M2, ...]` (the existing `nodes_created: list` field already supports multi-output groups — no group-schema change needed).
- **Side effect:** the umbrella's HEAD does NOT change; only the per-module HEADs are added. The umbrella stays evolvable.

#### 4.3 New op: `sync` (pull as-implemented design back into the subgraph)

- **Targets** a module subgraph that has a `linked_task` (the fast-tracked aitask). Refuses to run on a subgraph without a linked task — there is nothing to sync from.
- **Inputs (assembled by `register_syncer`):**
  1. **Linked task plan file** — `aiplans/p<parent>/p<parent>_<child>_<name>.md` while implementing, `aiplans/archived/p<parent>/...` after archival. Especially the `## Final Implementation Notes` and `## Post-Review Changes` sections.
  2. **Code diff scoped to the linked task's commits** — `git log --grep "(t<child>)"` (or via `aitask_issue_update.sh`-style commit lookup that already powers issue-comment generation) → file list → `git diff` for each file across that commit range. Resulting per-file diffs are bundled into the syncer's input.
  3. **Historical plan/task context for the touched files** — call the existing helper:
     ```bash
     ./.aitask-scripts/aitask_explain_context.sh --max-plans <N> <file1> [file2...]
     ```
     where `<file1...>` is the touched-file list from input (2). The helper (built in t369) already orchestrates a codebrowser cache at `.aitask-explain/codebrowser/`, runs `aitask_explain_extract_raw_data.sh` to gather commit history + aitask/aiplan files for the inputs, and pipes through `aitask_explain_format_context.py` to produce formatted markdown on stdout. Its output is bundled directly into the syncer's input as the "subsequent aitasks context" section. **Reuse, do not reimplement.**
- **Outputs:**
  - A new node `nZZZ` in the module subgraph with `module_label=<module>`, `parents=[<previous module HEAD>]`, an updated `proposal_file` reflecting the as-implemented design, and an updated `plan_file` mirroring the aitask's final plan.
  - `current_heads[<module>] = nZZZ`; `history[<module>].append(nZZZ)`.
  - `br_groups.yaml` entry: `operation: sync`, `nodes_created: [nZZZ]`, `subgraph: <module>`, plus a new optional `sync_sources` field listing the input artifacts (linked task plan path, commit range, list of subsequent aitask plans consulted) for traceability.
- **Side effect on the subgraph:** the synced node becomes the new HEAD. If the user wants to re-refine after sync (e.g., `patch`), they build on top of the synced HEAD — the original pre-implementation design is still reachable in history.
- **No side effects** on the linked aitask, its plan file, or any of the subsequent aitasks consulted. Sync is read-only on the aitasks side.

#### 4.4 New op: `merge` (up only)

- **Targets** a module subgraph HEAD (the source) plus its parent subgraph (the destination — usually `_umbrella`, but in nested cases it can be the immediate ancestor module).
- **Inputs:** source subgraph HEAD + destination subgraph (resolved from the source's root node's `parents`).
- **Outputs:**
  - A new node `nYYY` in the destination subgraph with `module_label=<destination>`, `parents=[<destination HEAD>, <source HEAD>]` (a 2-parent node — DAG already supports this; the second parent records the merge provenance).
  - `current_heads[<destination>] = nYYY`.
  - `history[<destination>].append(nYYY)`.
  - The source subgraph's HEAD does **not** change. Future ops on the source subgraph would build on top of the pre-merge HEAD; if a re-merge is desired, a fresh `merge` op is run.
  - The merged proposal markdown is regenerated by an agent (template `merger.md`) that takes the destination's pre-merge proposal and the source's proposal as inputs and emits the new destination proposal absorbing the refined module content.
- **Side effect on `module_tasks`:** if the source had a `linked_task`, the linkage is preserved (it remains attached to the source subgraph). Whether the linked task auto-archives on merge is OUT OF SCOPE for this design — recorded as an open question.
- **"Only up" guard:** the op refuses to run if `<destination>` is not in the chain of `parents` of the source root. No cross-sibling merges, no descent. The validator runs at op-launch time.

#### 4.5 Existing ops become module-aware

`explore`, `compare`, `hybridize`, `detail`, `patch` all currently target the single `current_head`. They become module-scoped: the wizard gains a "subgraph selector" step (default: most-recently-touched subgraph) before the node-selection step. Behind the scenes:

- The wizard's step 2 (`_NODE_SELECT_OPS`) filters node candidates by `module_label == <selected_subgraph>`.
- The op's group entry in `br_groups.yaml` records the subgraph it ran inside (new optional `subgraph: <module>` field — defaults to `_umbrella` for back-compat with existing groups).
- Agent prompt templates get a header with the subgraph name and the constraint "stay within this module's scope" so the LLM does not blur boundaries.

This is the chunk of work that touches the most existing code; the design doc lists each op's wizard branch and template change as a checklist item under Phase B of the roadmap.

#### 4.6 Tree-shape evolution narrative (worked example)

Walk through the canonical lifecycle in the doc:

1. `explore` on n001 → n002 (umbrella refined).
2. `decompose` on n002 → spawns parser-root n010 and cache-root n014. State: `current_heads = {_umbrella: n002, parser: n010, cache: n014}`.
3. `explore` on parser HEAD (n010) → n011, n012. State: `current_heads[parser] = n012`.
4. `detail` on parser HEAD (n012) → adds plan file. Optional: `aitask_create.sh --batch --parent 754 --name parser_module ...` and link via `module_tasks[parser] = 754_1`.
5. parser implementation completes → t754_1 archives. Module is now "fast-tracked & implemented". During implementation, the aitask plan accumulated `Final Implementation Notes` and a few `Post-Review Changes` entries; another follow-up task t760 also touched files in the parser area.
6. `sync` on parser HEAD → reads t754_1's archived plan + git diff for the parser files + t760's plan & diffs (codebrowser-style sweep) → produces n013 (synced parser HEAD). State: `current_heads[parser] = n013`. Subgraph history: `[n010, n011, n012, n013]`.
7. `merge` parser → umbrella → new node n020 in `_umbrella` with `parents=[n002, n013]`. State: `current_heads[_umbrella] = n020`, `current_heads[parser] = n013` (unchanged, frozen).
8. `decompose` on n020 → can now fork *new* modules off the enriched umbrella, OR fork a `parser_v2` if more refinement is wanted on top of the merged design.

This narrative is the load-bearing visual of the doc — readers get the "branches grow, sync, merge back, regrow" mental model from this single example. The doc also notes that step 6 (sync) is **only** required when step 5 (implementation) happened; if a module is decomposed and merged purely as a design exercise without ever fast-tracking to implementation, sync is skipped.

#### 4.7 Fluid status (UC-2) is a derived view, not a new op

A module's status is computed from `(subgraph_state, linked_task_state)`:

- `unstarted` — only the subgraph root exists.
- `in_design` — subgraph has nodes beyond root, no linked_task or linked_task in `Ready`.
- `in_implementation` — linked_task in `Implementing`.
- `implemented` — linked_task in `Done` (archived).
- `merged` — appears in `parents` of any node in the destination subgraph (i.e., a `merge` op consumed it).
- `deferred` — explicit user marker (TUI binding); orthogonal to the others.

The doc enumerates these states and the existing data the TUI can read to compute them — no new fields required.

#### 4.8 UC-3 (extract / fast-track) is `decompose --modules=one + linked_task`

The "extract one module to fast-track" use case is just `decompose` invoked with a single module name plus an immediate `aitask_create.sh --batch --parent <task> --name <module>` call to seed a child task and write `module_tasks[<module>] = <new_task_id>`. The wizard surfaces this as a one-step flow ("Fast-track this module") in addition to the multi-module decompose path.

#### 4.9 Why THREE new ops, not one

The user's planning hint preferred a "best single op" answer. The doc explicitly addresses why three are needed and why none of them collapses cleanly into another:

- `decompose` is divergent (one node → many subgraph roots).
- `sync` is reconciliatory (external aitask reality → one new node in the subgraph). It runs only when implementation has happened, and only on a subgraph with a `linked_task`.
- `merge` is convergent (many subgraph descendants → one parent revision).
- The mental and lifecycle phases are distinct: decompose is at the start of branch growth, sync is mid-late (after fast-track-implementation), merge is at the end. Conflating any two would force one op to take a polymorphic input shape AND to make a lifecycle-stage decision implicitly.
- The "branches grow, sync if implemented, merge back, regrow" rhythm only stays clean if each phase is its own named op. Otherwise the round-trip becomes an opaque "manage modules" op with subcommands, which is worse than three small named ops.
- Specifically: auto-syncing inside merge would hide the synced state behind a black-box step, making it impossible to inspect "what did we absorb?" before the parent revision is created. Keeping sync explicit lets the user review the synced subgraph HEAD before triggering merge.

#### 4.10 Cross-cutting: agent prompts and templates

- New template: `.aitask-scripts/brainstorm/templates/decomposer.md` — input is a parent proposal + module list (optional, agent identifies if absent); output is one proposal-slice section per module, plus a brief "module summary" header.
- New template: `.aitask-scripts/brainstorm/templates/syncer.md` — input is the linked task's plan file + scoped git diff bundle + the subsequent-aitasks context bundle; output is the refined module proposal + plan reflecting as-implemented state.
- New template: `.aitask-scripts/brainstorm/templates/merger.md` — input is destination proposal + source module proposal; output is the destination proposal regenerated to absorb the source module's refined design.
- Existing templates (explorer, comparator, synthesizer, detailer, patcher) get a small front-matter addition: "subgraph context: <module_label>" so the agent stays in scope.

### 5. Touchpoint checklist for implementation

The "add a new op" 5-layer recipe (derived from Phase-1 exploration), expanded for each of the THREE new ops:

For `decompose`, `sync`, and `merge`:
- `brainstorm_schemas.py:GROUP_OPERATIONS` ← `decompose`, `sync`, `merge`.
- `brainstorm_app.py`: `_DESIGN_OPS` (3 new entries), `_NODE_SELECT_OPS` (decompose: yes, sync: yes — pick the module-HEAD node, merge: yes), `_WIZARD_OP_TO_AGENT_TYPE` (`decompose: decomposer`, `sync: syncer`, `merge: merger`), `_OPERATION_HELP` entries, `_execute_design_op` branches.
- `brainstorm_crew.py`: `BRAINSTORM_AGENT_TYPES` += {decomposer, syncer, merger}; `register_decomposer()`, `register_syncer()`, `register_merger()` modeled after `register_explorer()`. `register_syncer()` is the heaviest — it bundles the linked task plan, the scoped git diff, and the codebrowser-style sweep results into the agent input.
- `brainstorm_op_refs.py:_OP_INPUT_SECTION` += entries (`decompose: "Decomposition Plan"`, `sync: "Sync Sources"`, `merge: "Merge-Up Rules"` — note: `hybridize` already uses `"Merge Rules"`, so pick a distinct label for `merge` to avoid section-name collision).
- New templates: `templates/decomposer.md`, `templates/syncer.md`, `templates/merger.md`.

For the data-model layer (separate from the ops themselves):
- `brainstorm_schemas.py:GRAPH_STATE_REQUIRED` — extend to include `current_heads`, validate as map of `<module>: <node_id>`. Keep `current_head` as legacy alias of `_umbrella`.
- `brainstorm_schemas.py:NODE_OPTIONAL_FIELDS` — add `module_label`.
- `brainstorm_dag.py` — `set_head`, `get_head`, `get_node_lineage`, `next_node_id` all need a `module` parameter (default `_umbrella` for back-compat).
- `brainstorm_session.py:init_session` — initialize `current_heads = {_umbrella: <root>}` and `module_tasks = {}`.

For the merge guard:
- `brainstorm_dag.py` — new helper `is_ancestor_subgraph(source, destination)` to enforce "merge only up".

For the sync scan engine:
- **Reuse, don't reimplement.** The existing `aitask_explain_context.sh` family (built in t369) already does this exact job: given a list of source files, return the formatted historical-plan/task-context markdown. Sync's `register_syncer()` shells out to it, captures stdout, and bundles into the agent input. Specifically the family is:
  - `.aitask-scripts/aitask_explain_context.sh` — the orchestrator with `--max-plans N <files>` interface.
  - `.aitask-scripts/aitask_explain_extract_raw_data.sh` — raw git/aitask/aiplan extractor.
  - `.aitask-scripts/aitask_explain_format_context.py` — markdown formatter.
  - `.aitask-scripts/aitask_explain_process_raw_data.py` — internal processor.
  - `.aitask-scripts/aitask_explain_runs.sh`, `aitask_explain_cleanup.sh` — cache lifecycle helpers.
  - Cache lives at `.aitask-explain/codebrowser/` and is shared with codebrowser's TUI.
- Phase C's implementation task should NOT modify these helpers, only consume them. If the syncer needs a different output shape (e.g., per-file structured JSON instead of markdown), surface that as a follow-up task that adds a flag to `aitask_explain_context.sh` rather than forking the scan logic.

### 6. Open questions

- Agent-driven vs deterministic decomposition: default to agent-driven; offer a `--from-sections` flag for deterministic-from-section-markers when the parent proposal already has clean sections.
- Linked-task auto-archival on merge: should merging a module force-archive its linked_task? Recommend NO (orthogonal lifecycles).
- Nested decompose/sync/merge: a module subgraph can itself be `decompose`d. Recursion limit? Recommend none, but flag for review.
- `module_tasks` map: is it stored in `br_graph_state.yaml` or `br_session.yaml`? Recommend `br_graph_state.yaml` since it's lifecycle state, not session metadata.
- Conflict on merge when destination has evolved since the source was decomposed: the merger agent absorbs the conflict; record this as a behavior the agent prompt must address.
- Do existing groups (`subgraph` field absent) need a one-time migration to fill in `subgraph: _umbrella`? Recommend NO migration — make the field optional with `_umbrella` default.
- **Sync scan radius — what counts as "the same area"?** Files exactly matching the linked task's touched-file list, or anything in the same directory, or a file-rename-aware reachability set? Recommend exact-file-match for v1 (cheapest, most predictable), with directory-level expansion as a future flag.
- **Sync scan time horizon.** All aitasks that completed since the linked task archived, or only since the last `sync` ran on this module? Recommend "since last sync" so re-syncing later is cheap and only sees genuinely new context. Track `last_synced_at` per module in `br_graph_state.yaml` to support this.
- **Sync without a linked task?** Should `sync` also be runnable on a non-fast-tracked subgraph if the user manually pastes implementation context? Recommend NO for v1 — keep sync tied to `linked_task`. Free-form context absorption is what `patch` is for.
- **Sync-then-merge as a fused op?** Question explicitly raised and rejected (see §4.9) — sync's output node should be reviewable before merge fires.

### 7. Roadmap (out of scope here; recorded for follow-up)

Four follow-up implementation tasks suggested. Each is bounded enough to be a single aitask, ordered by dependency:

- **Phase A — data model.** `current_heads` map + `module_label` on nodes + `module_tasks` map + `last_synced_at` per module + `set_head(module=...)` / `get_head(module=...)` + `is_ancestor_subgraph` validator. No new ops yet. Existing ops continue to operate on `_umbrella`. Schema validators updated. Wizard step inserts a "subgraph selector" defaulting to `_umbrella` so existing flows are unchanged.
- **Phase B — `decompose` + `merge` ops.** Templates + `register_decomposer()` + `register_merger()` + wizard branches + help dict entries + op_refs entries + group entry's optional `subgraph` field + ancestry guard. Module subgraphs become creatable AND foldable back. Paired in one task because they share validators and the wizard subgraph-selector machinery — splitting them would force two passes through the same wizard plumbing.
- **Phase C — `sync` op (consumer of `aitask_explain_context.sh`).** Template + `register_syncer()` + wizard branch + `last_synced_at` guard + integration with the existing t369 helper family (NOT a re-implementation). The phase deliverable is a syncer that shells out to `aitask_explain_context.sh --max-plans <N> <files>`, bundles the resulting markdown plus the linked-task plan plus a scoped `git diff` into the agent input, and emits a new module-subgraph HEAD node. Since the heavy-lifting scan engine already exists, this phase is lighter than originally estimated — most of the work is glue + the syncer template + wizard plumbing.
- **Phase D — TUI surfaces & status views.** Per-module status badges (computed per §4.7), "fast-track this module" wizard preset (UC-3), dashboard showing the subgraph tree with merge/sync state per module, deferred-module marker. Built last because it depends on A/B/C data-model and ops being settled.

These are NOT created in this task — they will be spawned as follow-up aitasks at Step 8 review (or later, in a separate planning pass) once the design doc is approved.

## Implementation Steps (this task)

### Step 1 — Read sibling/related context for style alignment (~5 min)
- Skim `aidocs/brainstorming/brainstorm_engine_architecture.md` (top-level table of contents only) for tone and section-depth.
- Skim `aiplans/archived/p571/p571_3_section_aware_operation_infrastructure.md` for the existing `<!-- section: ... [dimensions: ...] -->` semantics — referenced in §4.2 of the doc.
- Read `.aitask-scripts/aitask_explain_context.sh` (top of file: usage block + flag handling) and `aitask_explain_extract_raw_data.sh` (top of file: `--mode` and `--source-key` semantics) so §4.3 and §5 cite the *correct interface* of the helper family from t369. The doc must show readers that sync's scan reuses these helpers — not codebrowser's Python internals — so Phase C scopes correctly.
- Re-read `aitasks/t754_new_brainstorm_operations.md` to ensure the three use cases are quoted **verbatim** in §1 of the doc.

### Step 2 — Write the design doc (single Write call)
- Path: `aidocs/brainstorming/module_decomposition_design.md`.
- Sections per §1–§7 above.
- Anchors: every code reference uses `path/to/file.ext:LINE` so editors with file-path linking can navigate.
- Length target: 600–900 lines of markdown — three new ops with full data-model + scan-engine + worked example needs more space than the original two-op estimate. Worked example (§4.6) is now eight numbered steps.

### Step 3 — No code edits in this task

Zero changes to `.aitask-scripts/brainstorm/`, `brainstorm_schemas.py`, `brainstorm_app.py`, etc. Implementation is captured as roadmap inside the doc and surfaced as follow-up tasks.

### Step 4 — Capture follow-up implementation tasks (deferred, not created here)

The Roadmap section names Phases A/B/C but does **not** create them. Creating concrete aitasks is left to Step 8 review or a later planning pass — avoids pre-committing to scope while the design might still shift.

### Step 5 — Verification (read-back)

After writing, re-read the doc end-to-end and confirm:
- All three use cases from the original task description are quoted and addressed; the post-implementation drift concern is addressed in §3 and §4.3.
- Every code reference points to a real file/line (spot-check 5 random anchors).
- §4.6 (worked example) walks through decompose → explore-within-subgraph → fast-track-implementation → sync → merge → regrow on the umbrella, and is concrete enough to run in someone's head.
- §4.9 (why three ops) explicitly addresses the "best single op" framing AND the "auto-sync-inside-merge" alternative.
- §5 (touchpoint checklist) mirrors the 5-layer recipe for all three new ops AND lists the data-model-layer changes AND the codebrowser-shared scan engine separately.
- §7 (Roadmap) names Phase A/B/C/D with bounded scope and clear ordering.

### Step 6 — Step 8 review with the user

Standard review flow. Likely review topics:
- Is the subgraph-membership stored as `module_label` (recommended) the right call vs reachability-derived? Trade-off discussed in §4.1.
- The merger agent's conflict-handling behavior (open question §6).
- Should follow-up Phase A/B/C tasks be created now or later?
- Doc location confirmation (`aidocs/brainstorming/...` vs `aidocs/brainstorm_module_decomposition.md`).

## Critical Files

**Read (reference only):**
- `aitasks/t754_new_brainstorm_operations.md` — source of the three use cases.
- `.aitask-scripts/brainstorm/brainstorm_schemas.py` — `GROUP_OPERATIONS`, `SESSION_REQUIRED`, `NODE_REQUIRED_FIELDS`, `GRAPH_STATE_REQUIRED`, `DIMENSION_PREFIXES`.
- `.aitask-scripts/brainstorm/brainstorm_app.py` lines 120, 122, 156, 179, 4408 — current op registry surfaces.
- `.aitask-scripts/brainstorm/brainstorm_crew.py:468` ff. — `register_*` pattern.
- `.aitask-scripts/brainstorm/brainstorm_op_refs.py:15` — `_OP_INPUT_SECTION`.
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — multi-parent support, head model, lineage walker.
- `.aitask-scripts/brainstorm/brainstorm_sections.py` — existing `<!-- section: ... -->` markers (proposal-slice cut-line for decompose).
- `.aitask-scripts/brainstorm/templates/explorer.md` — reference template style for sketched `decomposer.md` / `merger.md` snippets in the doc.
- `aidocs/brainstorming/brainstorm_engine_architecture.md` — style/tone reference.
- `aiplans/archived/p571/p571_3_section_aware_operation_infrastructure.md` — section-marker prior art.

**Write (single new file):**
- `aidocs/brainstorming/module_decomposition_design.md` (recommended). Alternative `aidocs/brainstorm_module_decomposition.md` per user's earlier preference — confirm at Step 8.

**No edits to existing files.**

## Verification

- `cat aidocs/brainstorming/module_decomposition_design.md | wc -l` → between 600 and 900 lines.
- `grep -c '^## ' aidocs/brainstorming/module_decomposition_design.md` → at least 7 (one per top-level section §1–§7).
- Manual read-back: spot-check 5 random `path:LINE` anchors with `sed -n '<LINE>p' <path>` to confirm the cited identifier is on that line.
- §4.6 (worked example) is concretely steppable through 8 numbered states.
- §7 (Roadmap) names Phases A, B, C, D with at least 3 bullets of deliverables each.

## Step 9 — Post-Implementation

Standard archival flow. No worktree to clean up (fast profile, current branch). Commit message uses `documentation: <description> (t754)` since the deliverable is a design doc — confirm at Step 8 if the user wants to keep `feature` instead (the task's current `issue_type`).

## Notes for Future Tasks (traceability only)

The design doc itself will be the **primary reference** for follow-up Phase A/B/C tasks. The plan to create those tasks is captured in §7 of the doc, not here, so the doc stays the single source of truth for the design.
