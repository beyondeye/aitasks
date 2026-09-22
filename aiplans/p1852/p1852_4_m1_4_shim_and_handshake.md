---
Task: t1852_4_m1_4_shim_and_handshake.md
Parent Task: aitasks/t1852_testmap_m1_engine_foundation_and_distribution.md
Sibling Tasks: aitasks/t1852/t1852_1_*.md, aitasks/t1852/t1852_2_*.md, aitasks/t1852/t1852_3_*.md, aitasks/t1852/t1852_5_*.md, aitasks/t1852/t1852_6_*.md
Archived Sibling Plans: aiplans/archived/p1852/p1852_*_*.md
Base branch: main
Output branch: main
---

# Coarse plan: t1852_4 — M1.4 Shim and handshake

## Context

Parent goal: M1 — Engine foundation and distribution. This submodule is
**M1.4 Shim and handshake**, wave **B**. It delivers `ait testmap <verb>`, the
entry every later bash caller uses (M5.1, M6.5, M7.4, M7.5, M8.2, M8.3, M9.3).
Providers: **M1.1 (t1852_1)** and **M1.2 (t1852_2)**.

This coarse plan records what the proposal fixes for M1.4. It does not design internals against providers that do not exist yet;
the Reality check below does that when this child is picked.

## Proposal reading list

`aidocs/testing_engine/n014_explorer_006_proposal.md`:
- *Module Map* → `#### M1` row **M1.4**; *Cross-module interfaces*;
  *Suggested implementation order* (wave B).
- *Components* → *Binary distribution (M1.3, M1.4)* (the handshake paragraph);
  *Per-user root (M1.1)*; *Engine binary identity and budget (M1.2)*
  (`version --json`).
- *Architecture* → *Process map* (the shim line under `ait test`).
- *Tradeoffs* → `tradeoff_strict_version_handshake`, `tradeoff_engine_absent_on_host`.
- Framework rules: `aidocs/framework/aitasks_extension_points.md` ("No global
  PATH override", "Adding a new helper script", "The `ait` dispatcher is
  user-facing only"), `shell_conventions.md`, `sed_macos_issues.md`.
- Parent plan: `aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md`
  (deviation 2 — permission touchpoints belong to the first skill consumer).

## Owned files / provides / consumes

- **Owns:** `.aitask-scripts/aitask_testmap.sh`; `.aitask-scripts/lib/platform_detect.sh`;
  the `testmap)` arm and usage line in `ait`; `tests/test_testmap_shim.sh`;
  `tests/test_platform_detect.sh`.
- **Provides:** `ait testmap <verb>` for every later bash caller;
  `platform_detect.sh` (the `<os>_<arch>` asset suffix) for M1.5.
- **Consumes:** M1.1 (`AITASKS_HOME`, `aitasks_engine_dir`); M1.2 (the
  binary's `version --json` output and exit contract).

## Step 0 — Reality check (MANDATORY, before any code; record the outcome here)

1. Re-read the proposal rows above and the parent plan's anchors.
2. Inspect the actual current state on the merge target: the landed
   `lib/aitasks_home.sh` API (name task + commit); the landed binary's
   `version` / `version --json` output shape and how a `-dev+<sha>` build
   reports itself (name task + commit); the dispatcher's arm layout and
   `show_usage`; whether `aitask_path.sh` sourcing order matters for the shim.
3. Tabulate every difference: *proposal says / coarse plan says / repository has*.
4. Decide per difference: adapt; revise this plan; or revise the proposal.
   Record the decision and reason.
5. Send `/aitask-note` to every downstream child a difference breaks
   (t1852_5 consumes the shim path and `platform_detect.sh`; M5.1's child
   consumes the `ENGINE_MISSING:` line and exit 3).
6. Re-confirm every file touched is owned here or is the owner's named
   extension (`test_scaffold.sh` copy list if a startup chain grows).

**Outcome:** _(to be recorded when executed)_

## Implementation steps (coarse)

1. `lib/platform_detect.sh` mapping `uname -s` / `uname -m` to
   `linux|darwin` × `amd64|arm64`, with a test.
2. `aitask_testmap.sh`: strict handshake in order — `AIT_TESTMAP_BIN` (print
   an override notice) > `AIT_ENGINE=dev` slot at `$AITASKS_HOME/engine/dev/`
   requiring a `<V>-dev+<sha>` version > `$AITASKS_HOME/engine/v<V>/`
   requiring `== VERSION` exactly (never newest-wins) > `ENGINE_MISSING:<path>`
   exit 3 with the repair hint. Never downloads. `exec`s the binary with the
   caller's arguments.
3. `ait`: `testmap)` arm + usage line. No permission-touchpoint entries
   (deviation 2).
4. `tests/test_testmap_shim.sh` with an `AITASKS_HOME` host and a fake
   binary: one case per tier, the override notice, the dev-version rule, the
   exact-VERSION rule, `ENGINE_MISSING` exit 3.

## Verification / acceptance

- `bash tests/test_testmap_shim.sh`, `bash tests/test_platform_detect.sh`
  pass; `shellcheck` clean.
- With a real binary at `$AITASKS_HOME/engine/v$(cat .aitask-scripts/VERSION)/ait-testmap`,
  `./ait testmap version` prints the engine's version; with it absent, exit 3
  and `ENGINE_MISSING:<path>`.

## Step 9 reference

Archival and cleanup follow the shared `task-workflow` Step 9. Current-branch
profile: no worktree, no merge.
