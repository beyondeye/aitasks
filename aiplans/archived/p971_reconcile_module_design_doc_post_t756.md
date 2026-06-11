---
Task: t971_reconcile_module_design_doc_post_t756.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# Plan: Reconcile `module_decomposition_design.md` post-t756 / post-t891

## Context

`aidocs/brainstorming/module_decomposition_design.md` is stale on two
narrow points that t891_1 deliberately left for this task (a
"t756-as-built reconciliation" axis, distinct from the plan-layer
retirement t891_1/_2/_3 handled):

1. **L9 status header** still reads *"Status: design only — no
   implementation has landed"*. But t756 (and its children t756_1–t756_7)
   implemented the entire Phase A–D roadmap — `decompose`/`sync`/`merge`,
   the subgraph data model, status views, and the fast-track preset — and
   is **Done and archived** (`aitasks/archived/t756_brainstorm_modules.md`,
   `completed_at: 2026-06-11`).
2. **The node `plan_file` framing** for `sync`. t891_3 (commit
   `41bf99bab`) made `ait brainstorm` proposal-only and removed the node
   plan layer — `brainstorm_schemas.py` now has **zero** `plan_file`/`plan`
   references. Two spots still describe `sync` producing a node
   `plan_file`:
   - §4.3 outputs (L337–338): *"an updated `proposal_file` … and an
     updated `plan_file` mirroring the aitask's final plan."*
   - §4.10 syncer template note (L527): *"Output: refined module proposal
     + plan reflecting as-implemented state."*

Authoritative cross-reference confirming the target state:
`brainstorm_engine_architecture_v2.md:1057` — the implementation plan is
**not** produced inside brainstorm; a fast-tracked module's as-built
design is "synced back into the **proposal**." So `sync` produces an
updated **proposal** node only.

A grep for `plan_file|plan reflecting|design only|no implementation`
across the doc returns **exactly** these three lines (L9, L338, L527) —
the change surface is fully bounded.

Documentation convention applied (`aidocs/framework/documentation_conventions.md`):
current-state-only, state behavior positively — no "previously design-only,
now implemented" version-history prose.

## Changes — all in `aidocs/brainstorming/module_decomposition_design.md`

### Edit 1 — Status header (L9–11)

Replace:
```
Status: design only — no implementation has landed. The follow-up
Phase A/B/C/D tasks are listed in §7. The plan that produced this
document is `aiplans/p754_new_brainstorm_operations.md`.
```
with (positive current-state phrasing; keeps the §7 and originating-plan
cross-refs intact):
```
Status: implemented. The `decompose`, `sync`, and `merge` operations and
their supporting data-model extensions described here are live in
`ait brainstorm`, delivered across the Phase A–D tasks in §7. The plan
that produced this document is `aiplans/p754_new_brainstorm_operations.md`.
```

### Edit 2 — §4.3 `sync` outputs (L335–338)

Drop the node `plan_file` clause so the synced node is proposal-only:
```
  - A new node `nZZZ` in the module subgraph with
    `module_label=<module>`, `parents=[<previous module HEAD>]`, and an
    updated `proposal_file` reflecting the as-implemented design.
```
(removes the trailing `, and an updated `plan_file` mirroring the
aitask's final plan` and folds the comma into `proposal_file`).

### Edit 3 — §4.10 syncer template note (L523–527)

Change the syncer `Output:` line to proposal-only:
```
  ... Output: refined module proposal
  reflecting the as-implemented state.
```
(removes `+ plan reflecting as-implemented state`).

## Out of scope (intentional — narrow blast radius)

- §7 "Roadmap (out of scope here)" body is left as-is: it remains an
  accurate record of how delivery was split into phases, and the status
  line still points to it. "(out of scope here)" meant out of scope *of
  this design doc*, which stays true.
- The other `plan`/`plan file` mentions in the doc all refer to the
  **aitask's** plan file (sync input §4.3 #1, drift §3, Phase C §7) — not
  the node `plan_file` — and stay correct.
- The t891 proposal-only `> Note` block (L13–20) is already correct and
  is untouched.

## Verification

- `grep -n "plan_file\|plan reflecting\|design only\|no implementation" \
  aidocs/brainstorming/module_decomposition_design.md` → returns nothing.
- Re-read the edited L9 / §4.3 outputs / §4.10 syncer note: each reads
  cleanly as current state and matches `brainstorm_engine_architecture_v2.md`
  (proposal-only sync).
- Doc-only change: no scripts/tests touched; no build/test run required.
  `verify_build` (if any) is unaffected.

## Risk

### Code-health risk: low
- None identified. Documentation-only edit to three lines in one
  `aidocs/` file; no code, schema, or test surface touched; change surface
  bounded by grep.

### Goal-achievement risk: low
- None identified. The three stale lines named in the task map exactly to
  the three edits, and the target wording is corroborated by
  `brainstorm_engine_architecture_v2.md:1057`.

## Post-implementation (Step 9)

Doc-only, on `main` (no worktree/branch). Commit the doc with
`documentation: … (t971)`, then archive via
`./.aitask-scripts/aitask_archive.sh 971` and `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Applied the three planned edits to
  `aidocs/brainstorming/module_decomposition_design.md` exactly as
  designed — (1) status header rewritten to current-state "implemented"
  phrasing, (2) §4.3 `sync` outputs stripped of the node `plan_file`
  clause (proposal-only), (3) §4.10 syncer template output line
  proposal-only. Net 8 insertions / 8 deletions in one file. No code,
  schema, or test surface touched.
- **Deviations from plan:** None.
- **Issues encountered:** Plan externalization first returned
  `MULTIPLE_CANDIDATES` (several recent internal plans in the recency
  window); re-ran with explicit `--internal <path>` to disambiguate.
  No impact on the change itself.
- **Key decisions:** Kept §7 "Roadmap (out of scope here)" body and the
  closing "primary reference for Phases A–D" line untouched — they remain
  accurate records of how delivery was split into phases, and the new
  status line still cross-references §7. Narrow blast radius by design
  (the three stale lines were grep-bounded). Confirmed the proposal-only
  target wording against `brainstorm_engine_architecture_v2.md:1057` and
  that `brainstorm_schemas.py` has zero `plan_file`/`plan` references
  (t891_3 removed the node plan layer).
- **Upstream defects identified:** None.
