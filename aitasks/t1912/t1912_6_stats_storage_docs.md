---
priority: medium
effort: low
depends: [t1912_5]
issue_type: documentation
status: Ready
labels: [verifiedstats, models]
gates: [risk_evaluated]
anchor: 1599
created_at: 2026-11-12 19:43
updated_at: 2026-11-12 19:43
---

## Context

Child 6 of t1912. Parent plan:
`aiplans/p1912_move_codeagent_stats_to_plumbing_branch.md`. Depends on
t1912_1-5. After those land, the code-agent usage/verified counters live on
the orphan branch `aitask-stats`, one blob per agent: `<agent>.json` plus the
`migrations/<agent>.json` marker. They no longer live in
`aitasks/metadata/models_<agent>.json`.

What the docs need to say:
- **Readers** read `refs/heads/aitask-stats` via
  `lib/model_stats_store.py`.
- **Refresh** happens on `ait sync` and `pick --sync`, on every stats write,
  and on `aitask_model_stats.py refresh`. TUIs never fetch.
- **`verified`** stays in `models_*.json` as a static prior.
- **Migration** runs from `ait setup` / `ait upgrade`.
- **Config export** no longer carries stats.

## Pages to update (current-state prose only)

Follow `aidocs/framework/documentation_conventions.md` and
`aitasks/metadata/doc_update_guide.md`.

- `website/content/docs/tuis/settings/reference.md` (~L204-258): schema and
  bucket rules. Describe where counters live now; the bucket rules are
  unchanged.
- `website/content/docs/skills/verified-scores.md` (~L43, L60-66)
- `website/content/docs/skills/aitask-add-model.md` (~L37, L86)
- `website/content/docs/installation/updating-model-lists.md` (~L8-12, L59)
- `website/content/docs/commands/codeagent.md` (~L240-262): the
  `list-models` example is outdated; refresh it.
- `aidocs/framework/model_reference_locations.md` (~L22, L199-200, L325)
- `aidocs/framework/adding_a_new_codeagent.md` (~L315-318, L343-356, L422).
  A new agent's counters need no registry keys.
- If t1912_1 added a store section to `aidocs/framework/task_relations.md`
  or a new aidoc, cross-link it. Otherwise consider a short
  `aidocs/framework/model_stats_store.md` covering the layout, refresh
  routes, marker rule and migration protocol, for future maintainers.

## Verification

- `cd website && hugo build --gc --minify` passes.
- `python3 check_links.py --build` passes (mandatory after editing
  `website/content`).
- Offer `python3 check_link_relevance.py` if links were added or retargeted.

Step 9 (Post-Implementation) applies.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1912_4** id=2026-11-16T09:45:39Z.f39f73abd5df37cdc44bdc7d from=t1912_4 from_verified=yes at=2026-11-16T09:45:39Z base=51eca42a0f7479ea14f698828899bcdd751b17d4 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1912_4 (landed in main 51eca42a0). Doc facts that changed:
> | - aitask_usage_update.sh / aitask_verified_update.sh --help now states the contract. Counters live on `aitask-stats`, and the registry is only read. `UPDATED:<agent>/<model>:<skill>:<value>` always means recorded, and <value> is the effective total or the literal `unknown`. A failed write is `STATS_ERROR:<reason>` with a non-zero exit. UPDATED_REMOTE_ONLY is gone. The verified writer never writes `verified` (a static prior).
> | - aidocs/framework/adding_a_new_codeagent.md L315-316 still describes these writers as rolling-stats updaters of the registry file.
> | - aidocs/framework/model_reference_locations.md rows for tests/test_verified_update.sh (L113, line ranges now stale) and tests/test_verified_update_flags.sh (L114) need refreshing. tests/test_metadata_partial_sync_recovery.sh was deleted.

> **✉ note:t1912_5** id=2026-11-16T20:28:58Z.c893a23e7c52af3388fa1126 from=t1912_5 from_verified=yes at=2026-11-16T20:28:58Z base=7d9572c13ee2cafe6110a585c593c21f9990d7a4 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1912_5 (code commit 3d4a7472c on main). Context for the stats-storage docs; the full detail is in the archived p1912_5 "Final Implementation Notes" → "Notes for sibling tasks".
> | - One-time migration: `ait setup` (after the Python venv step) and `ait upgrade` (install.sh, existing installs) run `aitask_model_stats.py migrate`. Per agent it prints MIGRATED / MIGRATE_NOOP / MIGRATE_SKIPPED / MIGRATE_DEFERRED / MIGRATE_ERROR, plus STRIPPED_RESIDUE for counters an older framework wrote after the cutover (discarded, never absorbed). It is never fatal: deferrals are retried on the next setup/upgrade. AIT_STATS_MIGRATE=0 opts out. `migrate --dry-run` previews per agent (MIGRATE_PLAN lines) and writes nothing.
> | - After migration the registry (models_<agent>.json) keeps only `verified` priors; usagestats/verifiedstats live only on aitask-stats. The seeds carry no counters. `aitask_opencode_models.sh --sync-seed` strips them on copy. aitask-add-model and refresh-code-models no longer add `verifiedstats` to new rows.
> | - Config export (settings TUI) carries no counters once a project is migrated. Import never brings in a bundle's counters, and keeps the destination's own not-yet-migrated ones on same-named rows.
> | - After an OFFLINE (no-remote) migration whose strip origin's history lacks, ordinary counter writes print "stats recorded locally only …" and are held on the local aitask-stats ref until a validated migrate publishes them. The marker_not_in_source state fails closed and needs a manual, history-preserving repair (a plain reset plus re-run is NOT lossless).
> | - New files for the aidocs reference lists (model_reference_locations.md / adding_a_new_codeagent.md): .aitask-scripts/lib/model_stats_migrate.py, .aitask-scripts/lib/model_stats_strip.jq, .aitask-scripts/aitask_model_stats_strip.sh; tests/test_model_stats_migrate.py, tests/test_setup_model_stats_migration.sh.
> | - This repo was migrated on 2026-11-16 17:58 (claudecode 3237 runs, codex 109, opencode 4).

> **👁 note:read** id=2026-11-17T09:34:58Z.1c6bd96a555dc88753ce1c35 by=t1912_6 at=2026-11-17T09:34:58Z mode=explicit ids=2026-11-16T09:45:39Z.f39f73abd5df37cdc44bdc7d,2026-11-16T20:28:58Z.c893a23e7c52af3388fa1126
