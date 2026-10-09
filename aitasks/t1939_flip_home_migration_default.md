---
priority: medium
effort: medium
depends: [1931]
issue_type: enhancement
status: Ready
labels: [testmap, install, ait_setup, bash_scripts]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-09 15:58
updated_at: 2026-10-09 15:58
---

## Context

This is the named follow-up of t1852_6 (test map M1.6). t1852_6 shipped `ait engine home [--migrate]` (commit f26d94777) as an **explicit** verb. It moves the legacy per-user root `~/.aitask/` (venv, pypy_venv, python, bin, uv, dev_tier, update_check, engine) into `$AITASKS_HOME` (default `~/.aitasks`) and leaves `~/.aitask -> $AITASKS_HOME` behind. In that release `ait setup` only **hints**: `report_home_legacy()` in `aitask_setup.sh` prints the `HOME_LEGACY:` line after `AITASKS_HOME:` in the summary, and never migrates.

This task flips the default: `ait setup` (and the `ait upgrade` path through `install.sh`) runs the migration itself, with an opt-out.

Authoritative spec: `aidocs/testing_engine/n014_explorer_006_proposal.md`
- Component *Framework home report and migration verb (M1.6)*, the "flipping the default … is a named follow-up admitted when …" sentence.
- *Named follow-ups (not v1)*.
- `assumption_home_symlink_compatibility`.
- `tradeoff_home_migration_window`, `tradeoff_split_home_rejected`.

Prior work: the archived plan `aiplans/archived/p1852/p1852_6_m1_6_framework_home_migration.md`. Read its Step 0 reality-check table (D1–D8), its Final Implementation Notes and its four Post-Review change requests before planning.

## Depends on

t1931 (`real_host_migration_check`): manual verification of `--migrate` on a real Linux host and macOS. Do not make migration the default before it has run cleanly on a real home and on BSD userland.

## Scope (from the proposal)

- `ait setup` runs `ait engine home --migrate` by default when `HOME_LEGACY:` reports tenants. Opt-outs (names reserved by the proposal): `--no-home-migration` (setup flag, and an `install.sh` pass-through if the upgrade path should migrate too; decide and record) and `AIT_HOME_MIGRATE=0`.
- Setup must branch on the verb's protocol, never re-derive it:
  - exit 0: `HOME_MIGRATED:<n>` or `HOME_SKIPPED:no-legacy-root|already-migrated`.
  - exit 1: `HOME_SKIPPED:<refusal>` or `HOME_ROLLED_BACK:<n>`. Setup reports, keeps going, and the hint stays.
  - exit 2: `HOME_FAILED:rollback` + `HOME_STRANDED:` + `HOME_RESTORE:` lines. Setup surfaces these prominently, verbatim, and does not continue as if nothing happened.
  - 128+signo: interrupted.

  Setup itself never touches the legacy root's contents. A migration refusal must never fail the whole setup.
- Ordering: decide where in `main()` the migration runs relative to the steps that write legacy tenants (venv, pypy venv, python wrappers, uv, dev tier), so setup does not recreate `~/.aitask/<tenant>` right after moving it. The tenants still resolve through the symlink afterwards (`assumption_home_symlink_compatibility`).
- Update the 18 doc files that name `~/.aitask` (set measured 2026-10-09; re-measure at pick time):
  - `README.md`
  - `aidocs/framework/aitasks_extension_points.md`, `python_tui_performance.md`, `sed_macos_issues.md`, `tui_conventions.md`
  - `aidocs/packaging/packaging_distribution_status.md`
  - `aidocs/testing_engine/n014_explorer_006_proposal.md`
  - `website/content/docs/commands/board-stats.md`, `commands/setup-install.md`
  - `website/content/docs/development/_index.md`, `development/pypy.md`
  - `website/content/docs/installation/_index.md`, `installation/linux.md`, `installation/pypy.md`, `installation/windows-wsl.md`
  - `website/content/docs/tuis/codebrowser/_index.md`, `codebrowser/reference.md`
  - the v0190 blog post (historical, so probably leave as-is; decide).

  Follow `aidocs/framework/documentation_conventions.md` (current-state only). Run `python3 check_links.py --build` in `website/` afterwards.

## Admission criteria (proposal), verify which are already met

`tests/test_aitasks_home.sh`, through a real `install.sh --dir`, must cover:
- fresh install;
- migration with a working venv and PyPy venv afterwards;
- an idempotent re-run;
- a hostile pre-existing symlink;
- cross-device refusal;
- a destination collision refused with both trees unchanged;
- the `AITASKS_HOME` override.

t1852_6 covers most of these with direct-verb cases (H5, H7, H8, H11–H13) plus one real-install case (H-I). What is new here is **setup-driven** migration: the default path, both opt-outs, each exit class surfaced correctly, and a re-run of setup after migrating (no hint, no re-migration, tenants still resolve).

## Key files

- `.aitask-scripts/aitask_setup.sh`: `main()`, `report_home_legacy()` (registered in the T9 grep guard's `FEATURE_FUNCTIONS`; any new function that names the legacy root needs the per-line `# legacy-root-ok:` marker or must go through the engine verb), and the argument parser for `--no-home-migration`.
- `install.sh`, if the upgrade path migrates: its flag parser and the `aitask_setup.sh --source-only` call sequence.
- `tests/test_aitasks_home.sh`: the S-cases (`run_main` takes `RUN_MAIN_HOME` and a keep-list as `$3`) and the real-install harness (H-I).
- `.aitask-scripts/aitask_engine.sh`: should need no change. If it does, it is a deviation; record it.

## Gotchas carried from t1852_6

- Any `ait` command's update check runs `mkdir -p ~/.aitask` and writes `update_check` (`ait` `check_for_updates`). The verb already detects that race and rolls back, but setup-time migration makes it more likely; keep setup's own update check out of the migration window.
- The engine slot writers deliberately do not take `$AITASKS_HOME_LOCK` (D7 in the archived plan). Re-check that this still holds once setup calls `install_engine_binary` and the migration in the same run.
- Never run `--migrate` against the developer's real `~/.aitask` from a test. Every case uses a scratch HOME.
