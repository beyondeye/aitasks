---
Task: t1852_6_m1_6_framework_home_migration.md
Parent Task: aitasks/t1852_testmap_m1_engine_foundation_and_distribution.md
Sibling Tasks: aitasks/t1852/t1852_1_*.md, aitasks/t1852/t1852_2_*.md, aitasks/t1852/t1852_3_*.md, aitasks/t1852/t1852_4_*.md, aitasks/t1852/t1852_5_*.md
Archived Sibling Plans: aiplans/archived/p1852/p1852_*_*.md
Base branch: main
Output branch: main
---

# Coarse plan: t1852_6 — M1.6 Framework home report and migration

## Context

Parent goal: M1 — Engine foundation and distribution. This submodule is
**M1.6 Framework home report and migration**, wave **H**. It delivers `ait
engine home [--migrate]`, the explicit verb that moves the legacy `~/.aitask/`
tenants into `$AITASKS_HOME` and leaves a symlink behind. In this release
setup only prints the `HOME_LEGACY:` hint; flipping the default is a named
follow-up (not v1). Providers: **M1.1 (t1852_1)**, **M1.5 (t1852_5)**.

This coarse plan records what the proposal fixes for M1.6. It does not design internals against providers that do not exist yet;
the Reality check below does that when this child is picked.

## Proposal reading list

`aidocs/testing_engine/n014_explorer_006_proposal.md`:
- *Module Map* → `#### M1` row **M1.6** (with the destination-collision
  preflight); *Named follow-ups (not v1)*; *Suggested implementation order*
  (wave H).
- *Components* → *Framework home report and migration verb (M1.6)*;
  *Per-user root (M1.1)*.
- *Assumptions* → `assumption_home_symlink_compatibility`,
  `assumption_legacy_user_root_coexists`.
- *Tradeoffs* → *The per-user root (M1)*: `tradeoff_two_user_roots`,
  `tradeoff_split_home_rejected`, `tradeoff_home_migration_window`.
- Framework rules: `shell_conventions.md`, `sed_macos_issues.md` (`mv`,
  `rmdir`, `ln -s`, device checks on macOS), `aitasks_extension_points.md`
  ("Test the full install flow for setup helpers").
- Parent plan: `aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md`
  (deviation 7 — the `destination-exists` preflight).

## Owned files / provides / consumes

- **Owns:** the `home` arm of `.aitask-scripts/aitask_engine.sh`; the
  `HOME_LEGACY:` hint in `aitask_setup.sh` (named extension of setup); the
  migration cases in `tests/test_aitasks_home.sh` (named extension of
  M1.1's file).
- **Provides:** the migration verb; the named follow-up that flips the
  default (`--no-home-migration` / `AIT_HOME_MIGRATE=0` reserved).
- **Consumes:** M1.1 (`AITASKS_HOME`, `.home.lock`); M1.5 (`aitask_engine.sh`).

## Step 0 — Reality check (MANDATORY, before any code; record the outcome here)

1. Re-read the proposal rows above and the parent plan's anchors.
2. Inspect the actual current state on the merge target: the landed
   `aitask_engine.sh` arm layout and `lib/aitasks_home.sh` (name tasks +
   commits); the current set of legacy tenants `aitask_setup.sh` creates
   (the known set once lacked `pypy_venv` — re-derive it from the scripts,
   not from memory); the framework files that dereference `~/.aitask`
   (8 files / 35 references on 2026-09-22) and confirm none compares the
   path (`==`, `-ef`, `realpath`, `samefile`); what `$AITASKS_HOME/` already
   contains after `ait setup` (at least `engine/`).
3. Tabulate every difference: *proposal says / coarse plan says / repository has*.
4. Decide per difference: adapt; revise this plan; or revise the proposal
   (a changed known set is a proposal edit). Record the decision and reason.
5. Send `/aitask-note` to every downstream task a difference breaks (the
   named follow-up that flips the default, once it exists).
6. Re-confirm every file touched is owned here or is the owner's named
   extension.

**Outcome:** _(to be recorded when executed)_

## Implementation steps (coarse)

1. `ait engine home`: print `HOME_ROOT:<path>`, `HOME_LEGACY:<path>|<tenants>`,
   `HOME_SYMLINK:none|<target>`, `HOME_NEXT:<what --migrate would do>`.
2. `ait engine home --migrate`: take `flock $AITASKS_HOME/.home.lock`
   (refuse while another `ait` holds it); **preflight over every present
   legacy entry before any move**, refusing with nothing moved and both trees
   intact on `no-legacy-root`, `already-migrated`, `foreign-symlink:<target>`,
   `cross-device`, `unknown-entry:<name>`, `destination-exists:<name>`; then
   move each present entry of the known set `{venv, pypy_venv, python, bin,
   uv, dev_tier, update_check, engine}` with a same-device `mv`; `rmdir` the
   emptied legacy root and immediately `ln -s $AITASKS_HOME ~/.aitask`;
   print `HOME_MIGRATED:<n>` or `HOME_SKIPPED:<reason>`.
3. Setup: print the `HOME_LEGACY:` hint when legacy tenants exist; never
   migrate.
4. Migration cases in `tests/test_aitasks_home.sh` (through a real
   `install.sh --dir` where a populated legacy root is needed).

## Verification / acceptance

- `bash tests/test_aitasks_home.sh` passes with: every refusal reason
  **including `destination-exists:engine` with a pre-created
  `$AITASKS_HOME/engine/`, asserting both trees byte-identical and nothing
  moved**; the known-set move incl. `pypy_venv`; the trailing symlink;
  `HOME_MIGRATED:<n>` / `HOME_SKIPPED:<reason>`; idempotent re-run
  (`already-migrated`); a hostile pre-existing symlink; cross-device
  refusal; the `AITASKS_HOME` override; the `ait engine home` report lines.
- After a successful migration on a scratch `HOME`, `~/.aitask` is a symlink
  and `~/.aitask/venv/bin/python` still runs (symlink compatibility).
- Setup prints `HOME_LEGACY:` when tenants exist and never migrates.

## Step 9 reference

Archival and cleanup follow the shared `task-workflow` Step 9. Current-branch
profile: no worktree, no merge.
