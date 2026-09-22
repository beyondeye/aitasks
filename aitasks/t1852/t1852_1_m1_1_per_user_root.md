---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: [testmap, install, ait_setup]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1852
created_at: 2026-09-22 17:27
updated_at: 2026-09-22 18:58
---

## Context

Child **M1.1 — Per-user root** of t1852 (test map feature, module M1 — Engine
foundation and distribution). Wave **A**. The test map engine is a Go binary
installed per user under `$AITASKS_HOME/engine/v<VERSION>/`; this child
delivers the one path resolver every bash piece of the feature sources, and
the setup lines that make the root visible. It has **no providers**: it is one
of the two roots of the whole dependency graph (with M1.2).

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
— Module Map `#### M1` row M1.1, component *Per-user root (M1.1)*,
*Architecture → Process map / Where state lives*, *Assumptions → Engine,
distribution and install (M1)* (`assumption_legacy_user_root_coexists`,
`assumption_home_symlink_compatibility`), *Tradeoffs → The per-user root (M1)*.
The parent plan `aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md`
records the decomposition, the repository reality anchors and the deviations
(the Go source directory is `goengines/`, not `engine/`).

**Coarse plan only.** The child plan `aiplans/p1852/p1852_1_m1_1_per_user_root.md`
records what the proposal fixes for M1.1. It does not design internals; its
**Step 0 — Reality check** (mandatory, executed before any code, outcome
recorded in the plan file) re-verifies every anchor against the merge target.

## Scope (from the proposal)

- `.aitask-scripts/lib/aitasks_home.sh` exports
  `AITASKS_HOME=${AITASKS_HOME:-$HOME/.aitasks}`, a function
  `aitasks_engine_dir <version|dev>` (→ `$AITASKS_HOME/engine/v<version>/`
  or `$AITASKS_HOME/engine/dev/`) and the lock path `$AITASKS_HOME/.home.lock`.
  It **never** falls back to `~/.aitask/` (the legacy root keeps venv,
  pypy_venv, python, bin, uv, dev_tier, update_check; the two roots coexist
  in this release).
- `ait setup` creates `$AITASKS_HOME/engine/` (0755) and prints
  `AITASKS_HOME:<path>` beside the `Python venv:` summary line so both roots
  are visible.
- `tests/test_aitasks_home.sh` pins: the default (`$HOME/.aitasks`), the env
  override, and that **no framework script of this feature names
  `~/.aitask/`** (a grep guard over the feature's scripts — pattern:
  `tests/test_no_raw_tmux.sh`).

## Key files to modify

- `.aitask-scripts/lib/aitasks_home.sh` — new (owned).
- `tests/test_aitasks_home.sh` — new (owned; M1.6 later adds migration cases
  as a named extension).
- `.aitask-scripts/aitask_setup.sh` — the `mkdir -p "$AITASKS_HOME/engine"`
  and the `AITASKS_HOME:` summary line only (a named extension of setup; the
  engine installer functions are M1.5's).
- `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` — add
  `aitasks_home.sh` to the copy list **if** any script on `./ait`'s or a
  helper's startup `source` chain sources it (rule:
  `aidocs/framework/shell_conventions.md` "System libs added to ./ait's
  source-on-startup chain"). The shim (M1.4) and `aitask_engine.sh` (M1.5)
  will; decide at the reality check whether `aitask_setup.sh` sources it at
  startup or lazily.

## Reference files for patterns

- `.aitask-scripts/lib/aitask_path.sh` — a tiny sourced lib with a
  double-source guard (`_AIT_PATH_LOADED`); mirror its shape.
- `.aitask-scripts/aitask_setup.sh` `main()` summary block (`Python venv:`
  line) and `setup_gate_logs_gitignore()` for the info/success idioms.
- `tests/test_claim_id.sh` for the test file skeleton (`scratch_cwd.sh`,
  `test_scaffold.sh`, `asserts.sh`, PASS/FAIL/TOTAL footer);
  `tests/test_no_raw_tmux.sh` for a grep-guard with a documented scope.
- `aidocs/framework/shell_conventions.md`, `aidocs/framework/sed_macos_issues.md`.

## Provides / consumes

- **Provides:** the `AITASKS_HOME` resolver sourced by the shim (M1.4),
  `install_engine_binary()` and `aitask_engine.sh` (M1.5), the migration
  verb (M1.6), and later the verifiers (M8) and `aitask_test.sh` (M5.1).
- **Consumes:** nothing.
- **Named extensions into this child's files:** M1.6 adds the migration
  cases to `tests/test_aitasks_home.sh`.

## Implementation plan (coarse)

1. Step 0 — Reality check (see the child plan).
2. Write `lib/aitasks_home.sh`; source it from the setup summary path.
3. Add the `mkdir` + `AITASKS_HOME:` line to `aitask_setup.sh`.
4. Write `tests/test_aitasks_home.sh` (default, override, grep guard).
5. Scaffold copy-list entry if the startup-chain rule applies.

## Verification

- `bash tests/test_aitasks_home.sh` passes; `shellcheck` clean on the new lib.
- `AITASKS_HOME=/tmp/x ./ait setup` (or the sourced function) prints
  `AITASKS_HOME:/tmp/x` and creates `/tmp/x/engine/` with mode 0755.
- `grep -rn '\.aitask/' .aitask-scripts/lib/aitasks_home.sh` → nothing.
