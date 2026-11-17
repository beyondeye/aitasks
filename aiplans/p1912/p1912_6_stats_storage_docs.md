---
Task: t1912_6_stats_storage_docs.md
Parent Task: aitasks/t1912_move_codeagent_stats_to_plumbing_branch.md
Sibling Tasks: aitasks/t1912/t1912_*_*.md
Archived Sibling Plans: aiplans/archived/p1912/p1912_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-17 12:56
---

# t1912_6: Stats storage docs (verified plan)

## Context

t1912_1 through t1912_5 moved the code-agent `usagestats` / `verifiedstats` counters
off `aitasks/metadata/models_<agent>.json` and onto the plumbing-only orphan branch
`aitask-stats`, one `<agent>.json` blob per agent plus a `migrations/<agent>.json`
cutover marker. This repo was migrated on 2026-11-16. The website and aidocs still
describe the counters as living in the registry file, and `verified` as an automatic
mirror of the all-time average. This task brings them to the current state, using
current-state prose only (`aidocs/framework/documentation_conventions.md`,
`aitasks/metadata/doc_update_guide.md` prose rules).

### Facts checked against the code (2026-11-17, HEAD 7d9572c13)
- Store: `lib/model_stats_store.py` (docstring: layout schema 1, refs). Readers read
  only `refs/heads/aitask-stats` and never fetch. Readers add the branch counters to
  the registry rows through `overlay_rows`. A marker means "branch only"; with no
  marker, readers add the file counters to the branch counters. The store is
  agent-agnostic (`AGENT_RE = [a-z][a-z0-9]*`).
- Refresh: `ait_model_stats_refresh` (`lib/task_utils.sh:1399`) runs after the fetch
  in `aitask_sync.sh` and in `aitask_pick_own.sh` `sync_remote`. Every write
  re-reads origin. `aitask_model_stats.py refresh` does the same by hand.
- Writers `aitask_usage_update.sh` / `aitask_verified_update.sh` call
  `bump-usage` / `record-verified`. Output: `UPDATED:<agent>/<model>:<skill>:<value>`
  (an effective total, or `unknown`), or `STATS_ERROR:<reason>` with a non-zero exit.
  After an offline migration that has not been published, a write prints
  "stats recorded locally only …" (`HELD_LOCAL`).
- `verified` is a static prior. `list-models`, the picker and settings show the
  all_time average when that skill has runs, and the prior otherwise. No writer
  writes `verified`. `aitask_add_model.sh` writes `"verified": {}` only.
- Migration: `setup_model_stats_migration` (`aitask_setup.sh` ~L1528) runs from
  `ait setup` (after the venv) and from install.sh's upgrade block. It is never
  fatal, and `AIT_STATS_MIGRATE=0` opts out. Result lines are MIGRATED /
  MIGRATE_NOOP / MIGRATE_SKIPPED / MIGRATE_DEFERRED (retried next time) /
  MIGRATE_ERROR / STRIPPED_RESIDUE, and MIGRATE_PLAN for `migrate --dry-run`.
  `marker_not_in_source` fails closed, and repairing it means keeping the local
  history.
- Config import (`config_utils._registry_without_bundle_stats`) always drops a
  bundle's counters, whatever the project's state, and keeps the destination's own
  counters that are not yet migrated on same-named rows.
- Config export (`config_utils.export_all_configs`, ~L445) loads each matching file
  with `json.load` and bundles it unchanged; nothing is stripped. So whether a
  bundle carries counters depends only on the registry on disk:
  - A migrated registry holds no counters, so its export carries none.
  - A registry not stripped yet still holds its legacy counters, and the export
    includes them. That covers `AIT_STATS_MIGRATE=0`, a deferred migration, and a
    remote-mode migration whose stripped registry has not reached this checkout
    through `./ait sync` yet (p1912_5: remote mode never touches the local
    `.aitask-data` worktree).
- `--sync-seed` strips counters, and the seeds carry none.
- Some flat-format `{runs, score_sum}` counters still exist, and `bump_usage`
  still converts them to buckets, so that sentence stays.
- The Settings Models tab is read-only, so codeagent.md's "scores can be edited
  in the Models tab" is wrong.
- No store aidoc exists, and `task_relations.md` has no stats section, so a new
  aidoc is warranted.

## Steps

1. **New `aidocs/framework/model_stats_store.md`** (maintainer reference, about 120
   lines). It covers:
   - the layout (`<agent>.json` schema 1, `migrations/<agent>.json`) and the refs
     (`refs/heads/aitask-stats` only, fast-forward, `Stats-Write-Id` nonce);
   - the read rule (`overlay_rows` / `load_agent_stats`, no fetch, never the cwd);
   - the refresh routes;
   - the write path and output contract;
   - the marker rule, and `verified` as a prior;
   - the migration protocol summary: one baseline per agent, absorb from `S1^`,
     residue never absorbed, the publication gate / HELD_LOCAL, no-remote strip
     via `aitask_model_stats_strip.sh` + `lib/model_stats_strip.jq`, and the
     `marker_not_in_source` manual repair;
   - the setup/upgrade hook and `AIT_STATS_MIGRATE`;
   - the file and test inventory (store, windows, migrate, strip, CLI, bridge
     `lib/verified_update_lib.sh`, `test_model_stats_*.{py,sh}`,
     `test_stats_writers_leave_task_data.sh`,
     `test_setup_model_stats_migration.sh`, `test_stats_readers_golden.py`);
   - "adding a new agent needs no store change".

   It points at the module docstrings as the authoritative source rather than
   copying them.
2. **`website/content/docs/tuis/settings/reference.md`** (Model Entry Schema
   ~L204-258, Export Bundle ~L275-292):
   - Drop `verifiedstats` from the registry JSON example, and fix the field table
     (`verified` = static prior).
   - Add a "Usage and score counters" subsection: they live on `aitask-stats`, one
     `<agent>.json` per agent keyed by model name. Show the per-model
     `usagestats` / `verifiedstats` shape. The bucket table and rollover rules stay
     unchanged. Keep the condition here too: until an agent's migration marker
     exists, its registry may still hold legacy counters, and readers add them to
     the branch counters. Once the marker exists, readers use the branch only.
   - Replace the "`verified` maintained automatically" sentence with the
     prior / effective-score rule.
   - Export/import, keeping the condition: an export copies the registry files as
     they are on disk. Once a project's counters have moved to `aitask-stats` and
     the stripped registry has reached this checkout, the export carries no
     counters. A registry that has not been migrated (migration opted out with
     `AIT_STATS_MIGRATE=0`, deferred, or not yet synced) still holds legacy
     counters, and the export includes them. An import always discards the
     counters in a bundle, and keeps the destination's own not-yet-migrated
     counters on same-named rows. Never write "bundles hold no counters" without
     the condition.
3. **`website/content/docs/skills/verified-scores.md`**:
   - L43: drop "also stored in `verified`"; the prior rule replaces it.
   - Rewrite `## Storage`: the branch; refresh on `ait sync`, a pick's sync and
     every write; displays never fetch; "recorded locally only".
   - Add a short "Moving existing counters" part: setup/upgrade runs the move
     once, with a result-line table, `--dry-run`, `AIT_STATS_MIGRATE=0`, and
     deferral retry.
   - The schema link stays.
4. **`website/content/docs/skills/aitask-add-model.md`** L37, L86: the new row gets
   an empty `verified` only. Existing `verified` priors are preserved. The counters
   are on `aitask-stats` and the skill never writes them.
5. **`website/content/docs/installation/updating-model-lists.md`**:
   - L12-16 list, L44 opencode helper (it also strips counters from the seed
     copy), and the L59 table: the registry holds the model list and score priors,
     plus legacy counters only until the project is migrated.
   - Add one sentence with a relref to verified-scores#storage about the counters'
     location.
6. **`website/content/docs/commands/codeagent.md`**:
   - Refresh the `list-models` output example (~L94-102) to the real current
     format (`STATUS:`, a `STATS:` line, skill key `pick`), and explain VERIFIED
     as the effective score and STATS as all-time runs/avg.
   - In the Model Configuration example, `task-pick` becomes `pick`, and the
     `verified` field row says it is a prior.
   - Fix L276: the Models tab is read-only, and editing `verified` changes only the
     prior.
7. **`website/content/docs/concepts/git-branching-model.md`** branch table: add an
   `aitask-stats` row (code-agent usage / verified counters, written without a
   worktree, refreshed by `ait sync`).
8. **`aidocs/framework/model_reference_locations.md`**:
   - L22 note: the counters are on `aitask-stats` and neither skill edits them.
   - L79: aitask_verified_update.sh L41 becomes L48, and add an
     `aitask_usage_update.sh` L47 row.
   - L113-114: refresh the test rows (line lists → "many"). Add `test_usage_update.sh`,
     `test_stats_writers_leave_task_data.sh`, `test_model_stats_migrate.py` and
     `test_model_stats_parity.sh` fixture rows (informational_only), and drop
     anything about `test_metadata_partial_sync_recovery.sh` if it is there.
   - L199-200, L325 (add-mode contract / unit tests): `verified: {}` only,
     preserve priors.
   - Add a note that the store files hold no model names. Link the new aidoc.
9. **`aidocs/framework/adding_a_new_codeagent.md`**:
   - L315-316: the writers send their counters to `aitask-stats` through
     `aitask_model_stats.py`, and their registry check reads the registry only.
   - §3 (~L340-360): the registry rows carry no counters. The new agent's counters
     need no registry keys and no store change. The next `ait setup` / `ait upgrade`
     writes its migration marker. Readers go through
     `model_stats_store.overlay_rows`. Link the new aidoc.
   - §5c L422: keep the tuples, and note that they iterate agents for the overlay.
   - §20b: the seed carries no counters.
   - Grep the writers for `SUPPORTED_AGENTS` first, so the §2b row stays accurate.

### Post-phase (risk mitigations)
1. [claim_audit] For every concrete token the edited pages and the new aidoc name,
   `grep -n` the source and record a hit. The tokens are the result lines, the
   env var, the CLI verbs and flags, the "recorded locally only" message,
   `HELD_LOCAL`, the refresh call sites, function names, the ref names and the
   file paths. Reread each edited passage against the "Facts checked" list above.
   Fix any claim with no hit or that does not match before running Verification.
2. [claim_audit] A token hit does not establish a behavioural claim. For every claim
   about behaviour or state, read the function that implements it and confirm both
   the claim and the condition under which it holds, and keep that condition in
   the prose. Claims of this kind include "carries no counters", "never fetches",
   "always discards", "readers ignore", "retried on the next run" and "never
   fatal". The functions to read:
   - `export_all_configs` / `_registry_without_bundle_stats` for export and import;
   - `overlay_rows` / `load_agent_stats` for marker vs. no marker;
   - `ait_model_stats_refresh` and its two call sites for refresh;
   - `setup_model_stats_migration` for deferral, opt-out and never-fatal;
   - `HELD_LOCAL` in `model_stats_store.write` for "recorded locally only".

   Any unconditional wording over a conditional behaviour is a defect to fix.

## Verification
- `cd website && hugo build --gc --minify` passes.
- `cd website && python3 check_links.py --build` passes.
- Offer `python3 check_link_relevance.py` (new relrefs added).
- Grep the edited pages: no stale `models_<agent>.json`-as-counter-store wording
  remains (`grep -rn "verifiedstats\|usagestats" website/content aidocs/framework`
  reviewed hit by hit).

## Step 9
Post-Implementation per task-workflow (commit docs on main with plain `git` +
explicit pathspecs; plan via `./ait git`/task_commit; archive).

## Risk

### Code-health risk: low
- None identified. The change is docs only. It adds one new aidoc and touches no
  code paths.

### Goal-achievement risk: low
- The docs could misstate a subtle store behaviour, such as the pre-migration
  overlay, held-local writes or what import keeps, so readers act on wrong
  guidance · severity: low (residual — addressed by inline post-phase claim_audit) · → mitigation: inline post-phase claim_audit

### Planned mitigations
- timing: post-phase | name: claim_audit | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement: misstated store behaviour | desc: grep-confirm every documented token, and confirm every behavioural claim and its condition by reading the implementing function
