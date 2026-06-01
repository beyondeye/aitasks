---
priority: high
effort: medium
depends: [t756_2]
issue_type: feature
status: Ready
labels: [ait_brainstorm, brainstom_modules]
created_at: 2026-06-01 16:45
updated_at: 2026-06-01 16:45
---

Phase C of the `ait brainstorm` **module decomposition** feature (parent t756).
Adds the `module_sync` op — pulls the *as-implemented* design of a fast-tracked
module back into its subgraph before an eventual `module_merge`. Depends on Phase B
(t756_2). Lighter than it looks: the heavy scan engine **already exists** (t369's
`aitask_explain_context.sh` family) — this task is glue + template + wizard plumbing.

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.3 sync, §5 "sync scan engine", §6 sync open-question defaults, §7 Phase C).
**Binding conventions:** `aiplans/p756_brainstorm_modules.md`.

## Context
Once a module is fast-tracked into a real aitask and code lands, the brainstorm
subgraph holds the *original* refined design while the aitask's plan accrues "Final
Implementation Notes"/"Post-Review Changes", and unrelated follow-up tasks may touch
the same files. `module_sync` reconciles that drift into a new subgraph HEAD so a
later `module_merge` absorbs current reality, not a stale design. Sync is **read-only**
on the aitask side.

## IMPORTANT — `module_` prefix (binding, from parent plan)
Implemented identifiers: op-key `module_sync`; wizard label "Module Sync"; agent
type `module_syncer`; template `templates/module_syncer.md`; register fn
`register_module_syncer()`; input section "Sync Sources".

## v1 decided defaults (design doc §6 — do NOT re-litigate)
- Refuse `module_sync` on a subgraph with **no `linked_task`** (free-form context is
  what `patch` is for).
- Sync scan **radius** = exact-file-match to the linked task's touched files.
- Sync scan **time horizon** = "since last sync" via `last_synced_at[<module>]`.
- No sync-then-merge fusion (merge stays separately reviewable).

## Key Files to Modify
- New template `templates/module_syncer.md` (input: linked-task plan + scoped git
  diff bundle + explain-context bundle; output: refined module proposal + plan
  reflecting as-implemented state).
- `brainstorm_crew.py`: add `module_syncer` to `BRAINSTORM_AGENT_TYPES`;
  `register_module_syncer()` that:
  1. Resolves `linked_task` for the module (refuse if absent).
  2. Reads the linked task plan: `aiplans/p<parent>/p<parent>_<child>_<name>.md`
     live, `aiplans/archived/p<parent>/...` after archival.
  3. Resolves touched files via `git log --grep "(t<child>)"` (the same
     commit-suffix convention `aitask_issue_update.sh` uses) + `git diff` per file.
  4. **Shells out to** `./.aitask-scripts/aitask_explain_context.sh --max-plans <N>
     <files>` and captures stdout. **REUSE — do NOT fork the helper family.** If a
     different output shape is ever needed, add a flag to that helper in a follow-up,
     never reimplement the scan.
  5. Bundles all three input streams into the agent input.
  6. Output node updates the module HEAD; updates `last_synced_at[<module>]`; group
     entry `operation: module_sync` + optional `sync_sources` (traceability).
- `brainstorm_schemas.py`: add `module_sync` to `GROUP_OPERATIONS`.
- `brainstorm_op_refs.py`: `_OP_INPUT_SECTION` += `module_sync:"Sync Sources"`.
- `brainstorm_app.py`: wizard branch (label "Module Sync") + `_OPERATION_HELP` +
  `_execute_design_op` branch; surface `last_synced_at` so the user sees the next
  sync's scan horizon.

## Reusable helper interface (CLAUDE.md "Reusable Helpers")
`aitask_explain_context.sh --max-plans N <file1> [file2...]` → formatted markdown
on stdout, orchestrating the `.aitask-explain/codebrowser/` cache. Family:
`aitask_explain_context.sh` (orchestrator), `aitask_explain_extract_raw_data.sh`,
`aitask_explain_format_context.py`, `aitask_explain_process_raw_data.py`,
`aitask_explain_runs.sh`, `aitask_explain_cleanup.sh`. **Consume via shell-out only.**

## Reference Files for Patterns
- `brainstorm_crew.py::register_explorer` (and Phase B's `register_module_decomposer`)
  for register-fn structure and node-creating output.
- `aitask_issue_update.sh` for the `(t<id>)` commit-suffix grep convention.

## Implementation Plan
1. Add op-key + agent type + op-input section + wizard tuple.
2. Write `templates/module_syncer.md`.
3. Implement `register_module_syncer()` (refuse-if-no-linked-task → plan read →
   scoped diff → explain-context shell-out → bundle → node + `last_synced_at`).
4. Wizard branch surfacing `last_synced_at`.

## Verification Steps
- `module_sync` refuses a subgraph with no `linked_task`.
- On a linked module it consumes plan + scoped diff + explain-context and produces a
  synced HEAD; `last_synced_at` advances so re-sync sees only newer context.
- The `aitask_explain_*` helper family is unmodified (consumed via shell-out only).
- Existing brainstorm tests still pass.
