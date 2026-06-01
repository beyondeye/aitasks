---
Task: t756_3_phase_c_sync_op.md
Parent Task: aitasks/t756_brainstorm_modules.md
Sibling Tasks: aitasks/t756/t756_1_phase_a_data_model.md, aitasks/t756/t756_2_phase_b_decompose_merge_ops.md, aitasks/t756/t756_4_phase_d_tui_status_views.md
Archived Sibling Plans: aiplans/archived/p756/p756_1_*.md, aiplans/archived/p756/p756_2_*.md (after they land)
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# t756_3 — Phase C: `module_sync` op

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.3 sync, §5 "sync scan engine", §6 sync defaults, §7 Phase C).
**Binding conventions:** `aiplans/p756_brainstorm_modules.md`. **Depends on:** t756_2.

## Goal
Add `module_sync` — pull the *as-implemented* design of a fast-tracked module back
into its subgraph (new HEAD) before an eventual `module_merge`, so merge absorbs
current reality, not a stale design. **Read-only** on the aitask side. Lighter than
it looks: the scan engine already exists (t369's `aitask_explain_context.sh` family)
— this is glue + template + wizard plumbing.

## IMPORTANT — `module_` prefix (binding)
op-key `module_sync`; wizard label "Module Sync"; agent type `module_syncer`;
template `templates/module_syncer.md`; register fn `register_module_syncer()`;
input section "Sync Sources".

## v1 decided defaults (design doc §6 — do NOT re-litigate)
- Refuse `module_sync` on a subgraph with **no `linked_task`** (free-form context is
  `patch`'s job).
- Sync scan **radius** = exact-file-match to the linked task's touched files.
- Sync scan **time horizon** = "since last sync" via `last_synced_at[<module>]`.
- No sync-then-merge fusion (merge stays separately reviewable).

## Scope
- New template `templates/module_syncer.md` (input: linked-task plan + scoped git
  diff bundle + explain-context bundle; output: refined module proposal + plan
  reflecting as-implemented state).
- `brainstorm_crew.py`: add `module_syncer` agent type; `register_module_syncer()`:
  1. Resolve `linked_task` for the module (refuse if absent).
  2. Read the linked task plan: `aiplans/p<parent>/p<parent>_<child>_<name>.md`
     live; `aiplans/archived/p<parent>/...` after archival. Emphasize its
     `## Final Implementation Notes` / `## Post-Review Changes`.
  3. Resolve touched files via `git log --grep "(t<child>)"` (the commit-suffix
     convention `aitask_issue_update.sh` uses) + `git diff` per file across the range.
  4. **Shell out to** `./.aitask-scripts/aitask_explain_context.sh --max-plans <N>
     <files>` and capture stdout. **REUSE — never fork the helper family.** If a
     different output shape is needed, add a flag to that helper in a follow-up task.
  5. Bundle all three input streams into the agent input.
  6. Output node updates module HEAD; update `last_synced_at[<module>]`; group entry
     `operation: module_sync` + optional `sync_sources` (traceability).
- `brainstorm_schemas.py`: add `module_sync` to `GROUP_OPERATIONS`.
- `brainstorm_op_refs.py`: `_OP_INPUT_SECTION` += `module_sync:"Sync Sources"`.
- `brainstorm_app.py`: wizard branch ("Module Sync") + `_OPERATION_HELP` +
  `_execute_design_op` branch; surface `last_synced_at` so the user sees the next
  sync's scan horizon.

## Reusable helper interface (CLAUDE.md "Reusable Helpers")
`aitask_explain_context.sh --max-plans N <file1> [file2...]` → formatted markdown on
stdout (orchestrates the `.aitask-explain/codebrowser/` cache). Family:
`aitask_explain_context.sh`, `aitask_explain_extract_raw_data.sh`,
`aitask_explain_format_context.py`, `aitask_explain_process_raw_data.py`,
`aitask_explain_runs.sh`, `aitask_explain_cleanup.sh`. **Consume via shell-out only.**

## Reference patterns
- `brainstorm_crew.py::register_explorer` and 756_2's `register_module_decomposer`.
- `aitask_issue_update.sh` for the `(t<id>)` commit-suffix grep convention.

## Implementation steps
1. Add op-key + agent type + op-input section + wizard tuple.
2. Write `templates/module_syncer.md`.
3. `register_module_syncer()`: refuse-if-no-linked-task → plan read → scoped diff →
   explain-context shell-out → bundle → output node + `last_synced_at` update.
4. Wizard branch surfacing `last_synced_at`.

## Verification
- `module_sync` refuses a subgraph with no `linked_task`.
- On a linked module it consumes plan + scoped diff + explain-context and produces a
  synced HEAD.
- `last_synced_at[<module>]` advances so a re-sync sees only genuinely-newer context.
- The `aitask_explain_*` family is unmodified (consumed via shell-out only).
- Existing brainstorm tests still pass.

## Step 9 (Post-Implementation)
On completion follow task-workflow Step 9: review, commit (`feature: … (t756_3)`),
consolidate this plan with Final Implementation Notes (record the syncer input-bundle
shape + notes for 756_4), then archive via `./.aitask-scripts/aitask_archive.sh 756_3`.
