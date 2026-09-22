---
priority: medium
effort: medium
depends: [t1852_1, t1852_5]
issue_type: feature
status: Ready
labels: [testmap, install, ait_setup, bash_scripts]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-09-22 17:27
updated_at: 2026-09-22 17:27
---

## Context

Child **M1.6 — Framework home report and migration** of t1852 (test map
feature, module M1). Wave **H**. Delivers `ait engine home [--migrate]`, the
explicit verb that moves the legacy `~/.aitask/` tenants into `$AITASKS_HOME`
and leaves a symlink behind. In this release `ait setup` only prints the
`HOME_LEGACY:` hint; flipping the default is a named follow-up (not v1).
**Providers:** M1.1 (`t1852_1`, `AITASKS_HOME` and `.home.lock`), M1.5
(`t1852_5`, `aitask_engine.sh` — this child adds its `home` arm).

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
— Module Map `#### M1` row M1.6 (now naming the destination-collision
preflight — parent-plan Deviation 7), component *Framework home report and
migration verb (M1.6)*, *Assumptions → Engine, distribution and install (M1)*
(`assumption_home_symlink_compatibility`, `assumption_legacy_user_root_coexists`),
*Tradeoffs → The per-user root (M1)* (`tradeoff_two_user_roots`,
`tradeoff_split_home_rejected`, `tradeoff_home_migration_window`), *Named
follow-ups (not v1)*. Parent plan:
`aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md`.

**Coarse plan only.** The child plan `aiplans/p1852/p1852_6_m1_6_framework_home_migration.md`
records what the proposal fixes for M1.6 and does not design internals; its
**Step 0 — Reality check** (mandatory, before any code, recorded in the plan)
inspects the landed `aitask_engine.sh`, `lib/aitasks_home.sh`, the current set
of legacy tenants `aitask_setup.sh` creates (the known set once lacked
`pypy_venv`) and the 8 framework files / 35 references that dereference
`~/.aitask` (name the tasks and commits).

## Scope (from the proposal)

- `ait engine home` prints `HOME_ROOT:<path>`, `HOME_LEGACY:<path>|<tenants>`,
  `HOME_SYMLINK:none|<target>` and `HOME_NEXT:<what --migrate would do>`.
- `ait engine home --migrate` runs under `flock $AITASKS_HOME/.home.lock`
  and refuses while another `ait` holds the lock. It runs a **preflight over
  every present legacy entry before any move** and refuses — with nothing
  moved and both trees intact — reporting `no-legacy-root`,
  `already-migrated`, `foreign-symlink:<target>`, `cross-device`,
  `unknown-entry:<name>` or `destination-exists:<name>` (a present legacy
  entry whose `$AITASKS_HOME/<name>` already exists; `engine/` always does
  after `ait setup`, and a `mv` onto an existing directory would nest the
  source inside it). Only then it moves each present entry of the known set
  `{venv, pypy_venv, python, bin, uv, dev_tier, update_check, engine}` with a
  same-device `mv`, `rmdir`s the emptied legacy root and immediately leaves
  `ln -s $AITASKS_HOME ~/.aitask` behind; prints `HOME_MIGRATED:<n>` or
  `HOME_SKIPPED:<reason>`.
- Setup prints the `HOME_LEGACY:` hint when legacy tenants exist and never
  migrates; `--no-home-migration` / `AIT_HOME_MIGRATE=0` are reserved for the
  follow-up that flips the default.
- Migration cases in `tests/test_aitasks_home.sh` (a named extension of
  M1.1's file): every refusal reason including `destination-exists` with a
  pre-created `$AITASKS_HOME/engine/` asserting both trees byte-identical and
  nothing moved; the known-set move including `pypy_venv`; the trailing
  symlink; `HOME_MIGRATED:<n>` / `HOME_SKIPPED:<reason>`; idempotent re-run
  (`already-migrated`); a hostile pre-existing symlink; the `AITASKS_HOME`
  override; `ait engine home` report lines. Through a real `install.sh --dir`
  where the case needs a populated legacy root.

## Key files to modify

- `.aitask-scripts/aitask_engine.sh` — the `home` arm (owned arm; the rest
  is M1.5's).
- `.aitask-scripts/aitask_setup.sh` — the `HOME_LEGACY:` hint (named
  extension of setup).
- `tests/test_aitasks_home.sh` — the migration cases (named extension of
  M1.1's file).

## Reference files for patterns

- `.aitask-scripts/lib/stale_lock.sh` and `lib/registry_lock.sh` — the
  framework's flock idioms; `aidocs/framework/shell_conventions.md` on
  `sed_inplace()` and BSD/GNU portability (`sed_macos_issues.md`), since
  `mv`, `rmdir`, `ln -s` and `stat` device checks must work on macOS.
- `aitask_setup.sh` `setup_pypy_venv()`, `install_python_wrappers()` — the
  tenants being moved and the absolute paths that must keep resolving through
  the symlink (`assumption_home_symlink_compatibility`).

## Provides / consumes

- **Provides:** the migration verb; the named follow-up that flips the
  default.
- **Consumes:** M1.1 (`t1852_1`), M1.5 (`t1852_5`).

## Implementation plan (coarse)

1. Step 0 — Reality check.
2. `home` report arm.
3. `--migrate`: lock → preflight (all refusals, `destination-exists`) →
   moves → `rmdir` → symlink → report.
4. Setup `HOME_LEGACY:` hint.
5. Migration test cases including the both-trees-intact refusal assertion.

## Verification

- `bash tests/test_aitasks_home.sh` passes with the new cases.
- On a scratch `HOME` with a populated legacy root and a pre-created
  `$AITASKS_HOME/engine/`, `ait engine home --migrate` prints
  `HOME_SKIPPED:destination-exists:engine` and `diff -r` of both trees before
  and after is empty; after removing the collision, the migration completes,
  `~/.aitask` is a symlink and `~/.aitask/venv/bin/python` still runs.
