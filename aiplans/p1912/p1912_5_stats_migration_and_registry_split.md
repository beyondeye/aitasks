---
Task: t1912_5_stats_migration_and_registry_split.md
Parent Task: aitasks/t1912_move_codeagent_stats_to_plumbing_branch.md
Sibling Tasks: aitasks/t1912/t1912_*_*.md
Archived Sibling Plans: aiplans/archived/p1912/p1912_*_*.md
Base branch: main
Output branch: main
---

# t1912_5 — Stats migration + registry split (plan)

The full protocol (steps 1-6, the uniqueness argument, no-remote mode and
the transient window) and the test list are in
`aitasks/t1912/t1912_5_stats_migration_and_registry_split.md`. That text is
normative: it was hardened through three user review rounds, so do not
simplify it.

## Steps

1. Add `migrate` to the store library and CLI, with trailers
   `Stats-Migration-Agent` / `-Kind` / `-Id`:
   - pin O via `fetch_pinned`;
   - find the oldest baseline before looking at B;
   - leased baseline strip (jq pretty-print parity);
   - absorb from `S1^` plus the marker in one leased store commit;
   - residue strip, which is never absorbed.

   Add seam hooks for after-strip and before-absorb, and between pin and
   strip.
2. Implement no-remote mode: `ait_cas_rewrite` + scoped
   `aitask_task_commit.sh` with trailers, then `cas_local`.
3. Hook it into `ait setup` (next to `setup_lock_branch`) and into the
   install.sh existing-install block (`declare -F`). Report deferrals; never
   fail on them.
4. Registry split:
   - `aitask_add_model.sh`, `aitask_opencode_models.sh` (new-row defaults
     and `--sync-seed`), the refresh-code-models SKILL text, and the
     `seed/models_*.json` strips;
   - a defensive strip in `aitask_install_merge.py`;
   - an import-path check;
   - writer-inventory classification.
5. Tests: the full race / recovery / parity matrix from the task file, plus
   the updated suites.
6. Ask the user before running `migrate` on this repo (it pushes), then run
   it and record each agent's output.

## Verification

Per the task file: shellcheck, the Python verdict, and the full
`install.sh --dir` → `ait setup` flow under a scratch HOME.

## Step 9

Post-Implementation per task-workflow.
