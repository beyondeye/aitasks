---
Task: t1912_2_shared_stats_read_path.md
Parent Task: aitasks/t1912_move_codeagent_stats_to_plumbing_branch.md
Sibling Tasks: aitasks/t1912/t1912_*_*.md
Archived Sibling Plans: aiplans/archived/p1912/p1912_*_*.md
Base branch: main
Output branch: main
---

# t1912_2 — Shared stats read path (plan)

Full spec: `aitasks/t1912/t1912_2_shared_stats_read_path.md`.

## Pre-phase (risk mitigations)

1. [characterize_reader_values] Build the fixture project: bucketed, flat,
   mixed and no-stats rows across claudecode, codex and opencode, plus a
   `review` key. Write a generator that captures, at `today=2026-11-04`:
   - the stats rankings;
   - the picker labels;
   - the settings labels and Models tab strings;
   - the `list-models` `VERIFIED:` / `STATS:` lines.

   Commit the golden **before** any reader edit.

## Steps

1. Overlay helper: registry rows + effective loader stats ⇒ today's row
   shape. `verified` passes through unchanged.
2. Convert `stats_data` loaders (thread `project_root`), the picker (stop
   re-reading `MODEL_FILES` in `_build_options_for_agent`),
   `config_utils.load_all_models`, the settings readers, and
   `aitask_codeagent.sh cmd_list_models` (the jq merge with
   `aitask_model_stats.py export`).
3. Confirm `cross_repo_settings._catalog_model_names` reads names only and
   needs no change. Record that here.
4. Update the tests that patch `MODEL_FILES` or in-memory models. Add the
   summed (no-marker) and branch-only (marker) cases.

## Verification

- The golden reproduces byte-for-byte.
- The listed Python and bash suites pass.
- No reader calls `refresh`.

## Step 9

Post-Implementation per task-workflow.
