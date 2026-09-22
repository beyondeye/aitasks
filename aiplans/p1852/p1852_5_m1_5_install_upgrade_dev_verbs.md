---
Task: t1852_5_m1_5_install_upgrade_dev_verbs.md
Parent Task: aitasks/t1852_testmap_m1_engine_foundation_and_distribution.md
Sibling Tasks: aitasks/t1852/t1852_1_*.md, aitasks/t1852/t1852_2_*.md, aitasks/t1852/t1852_3_*.md, aitasks/t1852/t1852_4_*.md, aitasks/t1852/t1852_6_*.md
Archived Sibling Plans: aiplans/archived/p1852/p1852_*_*.md
Base branch: main
Output branch: main
---

# Coarse plan: t1852_5 — M1.5 Install, upgrade and developer verbs

## Context

Parent goal: M1 — Engine foundation and distribution. This submodule is
**M1.5 Install, upgrade and developer verbs**, wave **C**. After it, every host
that ran `ait setup` has an engine, and setup reports `TESTMAP:<state>`.
Providers: **M1.1 (t1852_1)**, **M1.3 (t1852_3)**, **M1.4 (t1852_4)**.

This coarse plan records what the proposal fixes for M1.5. It does not design internals against providers that do not exist yet;
the Reality check below does that when this child is picked.

## Proposal reading list

`aidocs/testing_engine/n014_explorer_006_proposal.md`:
- *Module Map* → `#### M1` row **M1.5** (owns cell incl. the installer flags
  and call); *Cross-module interfaces* (`onboard.yaml` phases → M1.5's
  `report_testmap_state`); *Suggested implementation order* (wave C).
- *Components* → *Engine install, upgrade and state report (M1.5; the
  `bootstrapping` state M6.1)*; *Binary distribution (M1.3, M1.4)*.
- *Architecture* → *Process map*, *Where state lives* (`.aitask-testmap/`).
- *Assumptions* → `assumption_release_asset_reachable`,
  `assumption_release_assets_reachable`, `assumption_one_engine_per_framework_version`.
- *Tradeoffs* → `tradeoff_setup_network_fetch`, `tradeoff_engine_version_skew`,
  `tradeoff_engine_absent_on_host`, `tradeoff_module_boundaries_cut_across_packages`.
- Framework rules: `aidocs/framework/aitasks_extension_points.md` ("Test the
  full install flow for setup helpers", "Adding a new helper script"),
  CLAUDE.md "CLI Conventions" (`ait setup` vs `ait upgrade` verbs),
  `shell_conventions.md`, `sed_macos_issues.md` (`shasum -a 256` on macOS).
- Parent plan: `aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md`
  (deviations 1, 2, 4, 8).

## Owned files / provides / consumes

- **Owns:** `install_engine_binary()` and `report_testmap_state()` in
  `aitask_setup.sh` plus the four engine flags in `main()`'s parser and the
  calls that reach them; the four engine flags, their pass-through and the
  `install_engine_binary` call after `install_global_shim` in `install.sh`
  (a named extension of the installer); `.aitask-scripts/aitask_engine.sh`
  (`build|test|cross|prune`; the `home` arm is M1.6's); the `engine)` arm in
  `ait`; `tests/test_install_engine_binary.sh`; the `packaging_strategy.md`
  paragraph naming `~/.aitasks/engine/`; the `CLAUDE.md` Engine block.
- **Provides:** an installed engine on every host that ran `ait setup`;
  `TESTMAP:<state>`; `ait engine build|test|cross|prune`.
- **Consumes:** M1.1 (`AITASKS_HOME`), M1.3 (asset names + sums), M1.4 (the
  shim, `platform_detect.sh`).
- **Named extensions into this child's files:** M6.1 adds the
  `bootstrapping|<next>` state to `report_testmap_state()`; M1.6 adds the
  `home` arm to `aitask_engine.sh`.

## Step 0 — Reality check (MANDATORY, before any code; record the outcome here)

1. Re-read the proposal rows above and the parent plan's anchors.
2. Inspect the actual current state on the merge target: the landed resolver
   (M1.1), asset names and sums file (M1.3), shim and `platform_detect.sh`
   (M1.4) — name each task and commit; `install.sh`'s `while` parser and its
   post-`install_global_shim` call site; `aitask_setup.sh::main()`'s flag
   parser and summary block; the release-asset URL family
   (`download_url()`, `github_release.sh`); the `.gitignore` helper idiom.
3. Tabulate every difference: *proposal says / coarse plan says / repository has*.
4. Decide per difference: adapt; revise this plan; or revise the proposal.
   Record the decision and reason.
5. Send `/aitask-note` to every downstream child a difference breaks
   (t1852_6 consumes `aitask_engine.sh`; M6.1's child consumes
   `report_testmap_state()`'s switch shape).
6. Re-confirm every file touched is owned here or is the owner's named
   extension.

**Outcome:** _(to be recorded when executed)_

## Implementation steps (coarse)

1. `install_engine_binary()` in `aitask_setup.sh`: source order
   `--local-engine <path>` > exact-version release asset (URL family
   `install.sh` already uses) > `--engine-from-source` (`goengines/build.sh`)
   > `ENGINE_MISSING` warning; `sha256sum -c` / `shasum -a 256` against the
   sums file with a `.sha256` sidecar short-circuit; atomic install to
   `$AITASKS_HOME/engine/v<V>/`; self-check `version --json` echoes `<V>`;
   `.dev`-marked binaries never overwritten without `--force-engine`;
   `--no-testmap` / `AIT_TESTMAP_FETCH=0` → `TESTMAP_BINARY:skipped`.
2. Setup adds `.aitask-testmap/` to `.gitignore` (pattern
   `setup_gate_logs_gitignore()`); `main()` parses the four flags.
3. `install.sh`: the four flags in its parser, passed through, and the
   `install_engine_binary` call after `install_global_shim`.
4. `aitask_engine.sh` with `build|test|cross|prune` (`prune` walks only
   `$AITASKS_HOME/engine/v*/` against the project registry); `engine)` arm.
5. `report_testmap_state()` — `TESTMAP:engine-missing` / `TESTMAP:absent`
   (+ `run /aitask-testmap-onboard`) / `TESTMAP:onboarded`; a comment marks
   where M6.1 adds `bootstrapping|<next>`. Setup reports, never onboards.
6. Docs: `packaging_strategy.md` paragraph; `CLAUDE.md` Engine block.
7. `tests/test_install_engine_binary.sh` through a real `install.sh --dir
   <scratch> --local-engine <bin>`.

## Verification / acceptance

- `bash tests/test_install_engine_binary.sh` passes: `$AITASKS_HOME/engine/v<V>/`
  path, checksum refusal, `.dev` protection, `--force-engine`,
  `TESTMAP_BINARY:skipped` via both `--no-testmap` and `AIT_TESTMAP_FETCH=0`,
  each `TESTMAP:` state.
- `ait setup --local-engine <bin>` accepted by `main()`; on this repository
  prints `TESTMAP:absent`.
- `.aitask-testmap/` gitignored; `ait engine build|test|cross|prune` smoke.

## Step 9 reference

Archival and cleanup follow the shared `task-workflow` Step 9. Current-branch
profile: no worktree, no merge.
