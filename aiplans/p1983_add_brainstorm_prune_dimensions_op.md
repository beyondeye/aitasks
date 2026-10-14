---
Task: t1983_add_brainstorm_prune_dimensions_op.md
Base branch: main
Output branch: main
---

# t1983 — Brainstorm "Prune Dimensions" operation

## Context

In `ait brainstorm` every node re-emits all of its baseline's dimension keys
(`requirements_` / `assumption_` / `component_` / `tradeoff_`). No operation removes
them, so on session 1812 the dimension keys are about 94% of node YAML (n014: 174 keys,
201 KB of 214 KB). This task adds a deterministic op that needs no agent. It creates a child node keeping
only the dimensions the user chooses, rewrites the proposal's section tags so they stay
valid, and moves the subgraph HEAD to the new node.

Decisions taken with the user:
- **Sections:** keep all prose. Only strip pruned exact keys from the
  `<!-- section: … [dimensions: …] -->` open markers. A section whose every tag is
  pruned becomes untagged (`<!-- section: name -->`). Glob tags (`component_*`) stay.
- **`active_dimensions`:** do not mutate the session list. In the explorer input,
  drop any dimension-shaped entry (`is_dimension_field`) the baseline node does not
  carry. Non-key entries pass through unchanged, which keeps the legacy bare-name
  fixture in `tests/test_brainstorm_crew.py` valid.
- **Top N:** all dimensions are ranked together by importance and the first N are
  kept, with **no per-kind quotas**; a kind can disappear entirely. The checklist
  stays adjustable and is shown as one flat list in ranked order.

Measured on 1812/n014: 100 of 174 keys are tagged by no section; prose mentions are
mostly 1. The ranking below is therefore a default the user adjusts in the wizard
checklist before confirming, not an oracle.

## Implementation

### 1. Core: section-tag rewrite — `.aitask-scripts/brainstorm/brainstorm_sections.py`

Add to the generation helpers:

```python
def strip_dimension_tags(text: str, kept_keys) -> str:
    """Drop exact dimension tags not in kept_keys from every open marker.
    Glob tags (ending in *) are kept; a marker left with no tags is written
    untagged. Lines that do not change are returned byte-identical; prose and
    close markers are never touched."""
```

Implementation: walk the lines. For each `_OPEN_RE.search(line)` with a non-empty
group(2), compute `new = [t for t in tags if t.endswith("*") or t in kept]`. If
`new != tags`, replace only the matched span with
`format_section_header(name, new)`, keeping `line[:m.start()]` and `line[m.end():]`.
Join with `"\n"` (same split/join convention as `parse_sections`). Invented and
invalid exact tags are dropped as well, because they are not in `kept`. That makes
`validate_sections(node_keys=kept)` pass by construction.

### 2. Core: ranking and apply — `.aitask-scripts/brainstorm/brainstorm_session.py`

Next to `apply_module_decompose_from_sections`:

- `rank_dimensions(dims: dict, proposal_text: str, active: list[str]) -> list[str]`.
  This is a pure function. The sort key is descending
  `(exact_tag_sections, prose_mentions, in_active)`, with a stable tie-break by node
  key order.
  - `exact_tag_sections` is the number of parsed sections whose `dimensions` contain
    the key exactly.
  - `prose_mentions` is the number of whole-token matches in non-marker lines, using
    `(?<![A-Za-z0-9_])key(?![A-Za-z0-9_])`. That way `component_agent_review` does not
    count `component_agent_review_pass`.
  - The docstring documents the ranking, because the wizard and docs refer to it.
  - Prefix plays no part in the order: one ranking covers all four kinds. "Top N" is
    simply `ranked[:N]`, so no separate helper is added.
- `apply_prune_dimensions(task_num, group_name, source_node_id, kept) -> str`. It
  mirrors the from-sections path:
  - `wt = crew_worktree(task_num)`; `source_data = read_node(...)`;
    `source_dims = extract_dimensions(source_data)`.
  - **Failure boundary.** Two exception types, both defined in
    `brainstorm_session.py`:
    - `PruneRefused(ValueError)` is raised **only** by the read-and-check phase below,
      which runs entirely before the first write. Nothing on disk has changed when it
      is raised.
    - `PrunePartialFailure(RuntimeError)` is raised when anything fails **after**
      writes began. It carries `group_name`, `new_node_id` (or `None`), `stage`
      (`counter_bumped` | `node_created` | `head_moved`) and the cause. Before raising
      it, best-effort `update_operation(task_num, group_name, status="Error",
      error=f"{stage}: {exc}")`, plus `nodes_created=new_node_id` once the node
      exists. That update is wrapped in its own `try`, so a failing record write does
      not mask the original error. `Error` is already in the group/agent status
      colour vocabulary (`AGENT_STATUS_COLORS`).

    No rollback is attempted; this is a narrow boundary, not a transaction. The
    surviving record plus the child's `created_by_group` keep a partial success
    diagnosable.
  - It refuses (`PruneRefused`) when:
    - `kept` is empty;
    - `kept` contains a key the source does not have;
    - `kept` covers every source key (nothing to prune).
  - `dims = {k: v for k, v in source_dims.items() if k in kept}`, in source order.
  - Read the proposal with `read_proposal(wt, source_node_id)`. A **missing** file
    raises `PruneRefused(f"source proposal missing for {source_node_id}: {path}")`.
    A missing or unreadable source node YAML is a `PruneRefused` as well.
    Never treat it as empty text: `finalize` exports HEAD's proposal, so a blank child
    at HEAD would ship a blank plan. An **existing empty** file is legitimate and
    passes through as `""`. The distinction is `read_text` raising
    `FileNotFoundError`, not the content being empty.
  - `new_text = strip_dimension_tags(text, kept)`. Guard:
    `validate_sections(parse_sections(new_text), node_keys=list(dims))` must report no
    unknown-key errors. Pre-existing structural errors are unchanged by a tag-only
    rewrite and do not block.
  - `subgraph = _group_subgraph(wt, group_name)` is also read in this phase.
  - **All reads and checks above run before the first write**, and every failure in
    this phase is a `PruneRefused`. `next_node_id` itself increments the counter in
    `br_graph_state.yaml`, so it is the first mutation. A refusal leaves no child node,
    no HEAD change, no counter bump, and the source untouched.
  - **Write phase**, inside one `try` that converts any exception into
    `PrunePartialFailure` with the stage reached:
    - `new_node_id = f"n{next_node_id(wt):03d}_{group_name}"`, e.g.
      `n015_prune_dimensions_001`, which keeps the `n###_` prefix that
      `_node_id_ordinal` parses. Stage → `counter_bumped`.
    - `create_node(..., parents=[source_node_id], description=f"Pruned {D} of {T}
      dimensions from {source}", dimensions=dims, proposal_content=new_text,
      group_name=group_name, reference_files=source_data.get("reference_files"),
      module_label=subgraph)`. Stage → `node_created`.
    - `set_head(wt, new_node_id, module=subgraph)`. Stage → `head_moved`.
    - `update_operation(..., nodes_created=new_node_id)` and
      `update_operation(..., status="Completed")`.
  - The source node and `br_graph_state.yaml` `active_dimensions` are not touched.
- `run_prune_operation(task_num, group_name, *, source_node, kept, head_at_creation,
  subgraph, **extras) -> str` is the single entry point the TUI calls; it owns the
  operation record's lifecycle:
  1. `record_operation(task_num, group_name, "prune_dimensions", agents=[],
     head_at_creation=…, subgraph=…, **extras)`.
  2. `apply_prune_dimensions(...)`:
     - on `PruneRefused`, `delete_group(task_num, group_name)` and re-raise. This is
       safe because nothing was written; it is the **only** path that deletes the
       record.
     - on `PrunePartialFailure` (or anything else), **keep the record** and re-raise.
       The record already says `status: Error`, the stage, and the created node.
  3. Return the new node id.

  Keeping this in `brainstorm_session.py`, not the `@work` thread, makes the boundary
  unit-testable without Textual.

### 3. Explorer input filter — `.aitask-scripts/brainstorm/brainstorm_crew.py`

In `_assemble_input_explorer`, compute `dims = extract_dimensions(node_data)` before the
"## Active Dimensions" block. Render
`[d for d in active_dimensions if not is_dimension_field(d) or d in dims]`, so a key
pruned from (or never on) this baseline is not offered back to the explorer. In
`templates/explorer.md` (next to the never-drop rule, lines ~47-49 and ~162), add one
sentence: "a dimension absent from the baseline may have been pruned on purpose — do
not re-add it unless your mandate calls for it". The never-drop rules stay correct,
because they are already relative to the baseline / parents.

### 4. Op inventories

- `constants.py`:
  - `_DESIGN_OPS`: add `("prune_dimensions", "Prune Dimensions", "Create a child node
    keeping only chosen dimensions")` after `synthesize`.
  - `_OPERATION_HELP["prune_dimensions"]`: title, summary, reads_from_parent,
    produces, use_cases.
  - Add it to `_NODE_SELECT_STEP_OPS`, so the op-select flow gets a source-node step
    defaulting to HEAD. Do not add it to `_NODE_SELECT_OPS`, so there is no
    section-select step.
  - Add it to the `config` step tuple in `_WIZARD_STEPS` and to `_SINGLE_NODE_OPS`, so
    it greys out at 2+ marked nodes.
  - Leave `_WIZARD_OP_TO_AGENT_TYPE` without an entry; the fallback is already
    `DEFAULT_LAUNCH_MODE`.
- `brainstorm_schemas.py` `GROUP_OPERATIONS`: append `prune_dimensions`.
- `brainstorm_dag_display.py` `OP_BADGE_STYLES`: `"prune_dimensions":
  Style(color="#BD93F9")` (purple, not yet used by an op).
- `modals.py` `NodeActionSelectModal._OPS`: insert after `synthesize`.
- `brainstorm_op_refs.py`: no change. `list_op_inputs` returns `[]` for agent-less
  groups; I will verify this while implementing.

### 5. Wizard — `.aitask-scripts/brainstorm/brainstorm_app.py` (`ActionsWizardScreen`)

- **`on_mount` routing:** add a branch for `op_key == "prune_dimensions"` that sets
  `_wizard_config = {"_selected_node": node_id, "pre_seeded_node": True}` and
  `_wizard_subgraph = _node_module(...)`, then calls `_actions_show_config()`.
- **`_actions_show_node_select`:** add `"prune_dimensions": "Select Source Node"` to
  `desc_map`. Default the focus to HEAD for prune, as `module_decompose` does.
- **`_actions_show_config`:** add a hint line ("Tab Switch group  Space Toggle  Type to
  filter") and dispatch to the new `_config_prune_dimensions`.
- **`_config_prune_dimensions(container)`:**
  - Source node: `_selected_node`, falling back to the subgraph HEAD. Read its dims,
    proposal and `get_active_dimensions`, and cache
    `self._prune_ranked = rank_dimensions(...)` and `self._prune_dims`.
  - **Initial state: restore or default.** The Back button on the confirm step
    rebuilds this step through `_on_actions_back` → `_actions_show_config`.
    `_actions_collect_config` has already replaced `_wizard_config` with the collected
    dict at that point. So:
    - If `_wizard_config` holds a prune `source_node` equal to the resolved source
      **and** a `kept` list, restore `mode`, `top_n` and the checked set
      (`kept ∩ current dims`).
    - Otherwise use the defaults: top-N mode, N = `min(40, T-1)`, and the first N
      ranked keys checked.

    Coming back via node-select (`_actions_show_node_select` resets `_wizard_config
    = {}`) or picking a different source therefore resets on purpose. Store the
    resolved state as `self._prune_mode`, `self._prune_applied_n` and the initial
    checked set before mounting.
  - Mount:
    - a "Source Node" label;
    - `RadioSet(classes="rs_prune_mode")` with "Keep top N overall" and "Keep
      selected", with the stored mode pressed;
    - `Input(value=str(<stored N>), type="integer", id="prune_top_n")`. The default
      is `min(40, T-1)`, where T is the source's dimension count (about a quarter of
      n014's 174 keys);
    - a `Label(id="prune_counts")` showing "Keeping K of T dimensions (D dropped)";
    - `FuzzyCheckList([], item_class="chk_prune_dim", id="prune_dims")`;
    - a Next button.
  - After refresh, fill the list with `set_grouped_items` as **one flat group in
    ranked order** (subheader "Dimensions — ranked by importance"; no prefix
    grouping). Each row's label is `f"{i}. {key} — {trunc(value)}"`, where i is the
    1-based rank. Checked means membership in the stored initial checked set
    (restored or default), never a fresh `i <= N` recomputation.
  - Add a `_parse_prune_label` helper in `utils.py` beside `_parse_dimension_label`.
    It strips the rank prefix, then delegates, so the rank is visible while collection
    still yields the bare key.
- **Handlers**, scoped by selector so other ops are unaffected. They are idempotent
  against the stored state, so the `Changed` events Textual may post while mounting
  the restored values cannot overwrite the restored checks:
  - `@on(Input.Changed, "#prune_top_n")`: parse N. Only when the mode is top-N **and**
    N is a valid int different from `self._prune_applied_n`, re-check `ranked[:N]` and
    set `_prune_applied_n = N`.
  - `@on(RadioSet.Changed, ".rs_prune_mode")`: act only when the pressed mode differs
    from `self._prune_mode`; then store it. Switching to top-N re-applies `ranked[:N]`.
    Switching to "Keep selected" keeps the current checks as the starting point to
    adjust.
  - `@on(Checkbox.Changed, ".chk_prune_dim")`: refresh the counts label only.

  A manual toggle in top-N mode is allowed; changing N overwrites it. The wizard
  hint says so.
- **Tab groups:** extend `_cycle_wizard_groups` and its `on_key` gate to prune. The
  groups are the radio set, the N input, the `prune_dims` filter, and Next.
- **`_actions_collect_config`, prune branch:** collect `source_node`, `mode`, `top_n`
  (int ≥ 1 in top-N mode), `kept` (checked keys) and `dropped` (in rank order). Warn
  and refuse when `kept` is empty, or when nothing would be dropped.
- **`_build_summary`:** show the source node, the mode (+N), "Keeping K of T", and
  per-kind kept/total counts. The counts are informational only: there are no quotas,
  but they make a kind that drops to 0 visible. Show the full "Dropped (D):" list and
  the "Kept:" list, both in rank order.
  Add one line: "Section markers lose the dropped tags; proposal prose is kept."
- **Confirm step:** prune has no agent, so skip the launch-mode `CycleField` and the
  launch-mode summary line. `_on_actions_launch` already falls back when the field is
  absent.
- **`_run_design_op`:** add a subgraph branch for prune
  (`subgraph = _node_module(session_path, cfg["source_node"])`, `head_at_creation`
  from it). Then add a branch that calls `run_prune_operation(..., source_node=…,
  kept=…, mode=…, top_n=…, kept_count=…, pruned_dimensions=dropped)` and notifies
  "Pruned D dimensions → <new node>". Exceptions flow into the existing `Operation
  failed: …` notify. For `PrunePartialFailure` the message names the stage, the
  created node (if any) and "operation record <group> kept", so the user knows HEAD
  may already point at the child. The TUI never calls `delete_group` itself. The
  UI refresh follows whatever the from-sections path relies on; if the DAG does not
  refresh by itself, call `self._load_existing_session` via `call_from_thread` (it is
  already used at `:5549`).

### 6. Docs

- `website/content/docs/tuis/brainstorm/reference.md`:
  - add a Prune Dimensions entry to the op colour legend;
  - add a row to the "Operations and agents" table (agent: none, deterministic);
  - extend the "forks rather than prunes" decompose text with a pointer to Prune
    Dimensions as the way to shrink a node.
- `website/content/docs/tuis/brainstorm/how-to.md`: add a new "How to Prune Dimensions"
  section after "How to Compare and Synthesize Nodes". It covers:
  - both modes;
  - the single overall ranking and its signals;
  - that top N overall has no per-kind quota, so a kind can drop out entirely;
  - the ranked, adjustable checklist;
  - what happens to section markers and prose;
  - the HEAD move, and that the source node is untouched.
- `aidocs/brainstorming/brainstorm_engine_architecture_v2.md`:
  - note that `active_dimensions` only grows;
  - note that the explorer input filters it to the baseline's keys;
  - state that the never-drop rules apply relative to a (possibly pruned) baseline;
  - describe the prune op.

  Current-state wording only.
- Run `cd website && python3 check_links.py --build`.

### 7. Tests

- **New `tests/test_brainstorm_prune_dimensions.py`** (unittest, fixture style of
  `tests/test_brainstorm_apply_module_ops.py`; patch `crew_worktree`):
  - `strip_dimension_tags`:
    - pruned exact tags are removed and glob tags are kept;
    - an all-pruned marker becomes untagged;
    - prose, close markers and unchanged lines stay byte-identical.
  - `rank_dimensions`:
    - the exact-tag count dominates, then prose mentions, then active membership;
    - a prefix-sharing key is not counted as a mention;
    - ties keep node order;
    - prefix plays no part: a highly tagged `tradeoff_` key outranks an untagged
      `requirements_` key, so `ranked[:N]` can leave a kind with zero keys.
  - `_parse_prune_label`: `"3. component_x — value"` gives `component_x`; a value
    that itself contains " — " or digits is still parsed correctly.
  - `apply_prune_dimensions`:
    - the source node YAML and proposal are byte-identical after the call;
    - the child has exactly the kept keys plus the structural fields, and
      `parents == [source]`;
    - `validate_sections(parse_sections(child proposal), node_keys=child keys) == []`;
    - HEAD moves on the umbrella and on a module subgraph (the child has
      `module_label`);
    - the group ends `Completed` with `nodes_created`;
    - `active_dimensions` is unchanged;
    - it raises on an empty `kept`, an unknown key, and a no-op prune;
    - **missing source proposal (regression):** delete the source's
      `br_proposals/<id>.md`, then call. It raises `ValueError`, no new node file or
      proposal exists, `get_head` is unchanged for the subgraph, `next_node_id` in
      graph state is unchanged, and the group is not `Completed`;
    - **existing empty source proposal:** succeeds, and the child proposal is `""`.
  - `run_prune_operation`, failure boundary (real temp session; only the named
    function is patched):
    - **Refusal before mutation** (missing proposal): `PruneRefused` propagates, the
      group entry is gone from `br_groups.yaml`, and no node, HEAD or counter changes.
    - **Fault after child creation:** patch `brainstorm.brainstorm_session.set_head`
      to raise. `PrunePartialFailure` propagates with `stage == "node_created"` and
      `new_node_id` set. The group entry **still exists** with `status: Error`, an
      `error` naming the stage, and `nodes_created == [new_node_id]`. The child files
      exist (no rollback), and HEAD is still the source.
    - **Fault after HEAD movement:** patch `update_operation` to raise on its
      `status="Completed"` call only. `PrunePartialFailure` has
      `stage == "head_moved"`, HEAD is the child, and the group record survives (not
      deleted).
    - **Negative control:** the same fault tests against a variant that calls
      `delete_group` on every exception would fail the "record survives" assertions.
      State this in the test docstring; it is not shipped code.
  - Explorer input: an `active_dimensions` entry `component_gone` absent from the
    baseline is not listed; a baseline key and a bare legacy name still are.
- **Pilot test of the config step**, in the style of the existing
  `tests/test_brainstorm_wizard_sections.py` / `test_brainstorm_node_action_integration.py`
  hosts:
  - the list is one flat group in ranked order;
  - the default N pre-checks exactly the first N rows;
  - changing N re-checks;
  - "Keep selected" keeps the manual toggles;
  - collect produces `kept` / `dropped`;
  - **configure → confirm → Back:** set N to a non-default value, switch to "Keep
    selected", toggle one row off and one below N on, press Next, then Back. Mode, N
    and the exact checked set are restored, and the counts label matches. A control
    run with the default state still shows the defaults;
  - re-entering via node-select with a different source resets to that source's
    defaults.
- **Updates:**
  - `tests/test_brainstorm_node_action_modal.py`: the exact `_OPS` order.
  - `tests/test_brainstorm_wizard_steps.py`: prune gets node_select, then config, then
    confirm; it never gets section_select; when seeded, node_select is omitted.
  - `tests/test_brainstorm_node_action_relevance.py`: `_SINGLE` gets prune, which greys
    at cardinality 2.
  - Check `test_brainstorm_dag_op_badge.py` and `test_brainstorm_session_tab.py`. They
    derive their sets from `GROUP_OPERATIONS` / `_DESIGN_OPS` and should pass
    unchanged.

### 8. Step 9 (Post-Implementation)

Commit the code with `feature: Add brainstorm prune-dimensions op (t1983)`, naming its
paths. Commit the plan via `aitask_task_commit.sh`. Then archive per task-workflow
Step 9.

### Post-phase (risk mitigations)

1. [ranking_real_data_check] Before committing, copy
   `.aitask-crews/crew-brainstorm-1812` to the scratchpad. Run
   `rank_dimensions(n014 dims, n014 proposal, active_dimensions)` and
   take `rank[:40]`. Print:
   - the kept keys in rank order with their kind and their
     `(exact_tag_sections, prose_mentions, in_active)` scores;
   - the kept/total count per kind;
   - the 5 highest-ranked dropped keys.

   Inspect it for plausibility. Heavily tagged components and the requirements named
   in the overview/run_surface sections should be kept; untagged, unmentioned keys
   should be dropped. Note whether any kind drops to zero at the default N. If the order is clearly wrong, adjust the tie-break inside
   `rank_dimensions` and its unit test before committing. Record the printed table
   and the verdict in the plan's Final Implementation Notes.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir <dir>` over the brainstorm tests;
  read only the last `PYTHON SUITE:` line. Also run the new and updated modules
  directly with `python -m pytest tests/test_brainstorm_prune_dimensions.py …`.
- Real-data check: on a scratch copy of `.aitask-crews/crew-brainstorm-1812`, call
  `apply_prune_dimensions` (with `crew_worktree` patched) on n014 with
  `rank[:40]`. Report the node YAML bytes before and after, and the
  section count of the child (55, unchanged). Report
  `validate_sections(node_keys=…) == []`. Confirm the source n014 file hashes are
  unchanged.
- `shellcheck` is not affected (no shell changes). Run `cd website && python3
  check_links.py --build` after the doc edits.

## Risk

### Code-health risk: medium
- The wizard edits land in `brainstorm_app.py` (5.8k lines), which is shared by six
  ops. New `Input.Changed` / `RadioSet.Changed` / `Checkbox.Changed` handlers and the
  Tab-group/confirm-step branches could leak into other ops' config steps if they are
  not scoped. · severity: medium · → mitigation: none (handlers are selector/op
  scoped; existing wizard tests cover the other ops)
- The explorer-input filter changes behaviour for **every** explore: dimension keys that
  only sibling branches carry are no longer listed under "## Active Dimensions" (the
  user chose this; the baseline's own keys are still listed under "Dimension Keys"). ·
  severity: low · → mitigation: none

### Goal-achievement risk: low
- The "top N" ranking is heuristic: on n014, 100 of 174 keys have no exact section tag,
  so most of the order comes from prose mentions and node order, which may not match
  what the user considers important. The wizard shows the full adjustable checklist,
  kept/dropped counts, and the dropped list before confirm, but the default may still
  feel arbitrary on real data. · severity: low (residual — addressed by inline
  post-phase ranking_real_data_check) · → mitigation: inline post-phase
  ranking_real_data_check
- "Top N overall" has no per-kind quota, so a default prune can remove every key of a
  kind (e.g. all `tradeoff_`). The user chose this; the confirm summary's per-kind
  counts make a kind that drops to 0 visible before launch. · severity: low ·
  → mitigation: none
- Keeping prose means the pruned proposal still describes dropped dimensions (accepted
  by the user; the agent-based prose rewrite is out of scope). · severity: low ·
  → mitigation: none

### Planned mitigations
- timing: post-phase | name: ranking_real_data_check | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — heuristic top-N ranking may give an arbitrary default on real data | desc: Run the ranking on a scratch copy of session 1812 n014, check the overall top-N kept/dropped plausibility (and per-kind counts), adjust the tie-break if clearly wrong, and record the table in Final Implementation Notes
