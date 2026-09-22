---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [testmap, ait_dispatcher, bash_scripts]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-09-22 17:27
updated_at: 2026-09-22 17:27
---

## Context

Child **M1.4 — Shim and handshake** of t1852 (test map feature, module M1).
Wave **B**. Delivers `ait testmap <verb>` — the entry every later bash caller
uses (M5.1 `aitask_test.sh`, M6.5, M7.4, M7.5, M8.2, M8.3, M9.3). **Providers:**
M1.1 (`t1852_1`, the `AITASKS_HOME` resolver) and M1.2 (`t1852_2`, the binary
whose `version --json` the handshake reads).

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
— Module Map `#### M1` row M1.4, component *Binary distribution (M1.3, M1.4)*
(the handshake paragraph), *Architecture → Process map* (the shim line),
*Tradeoffs → Engine and distribution (M1)* (`tradeoff_strict_version_handshake`,
`tradeoff_engine_absent_on_host`). Parent plan:
`aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md`.

**Coarse plan only.** The child plan `aiplans/p1852/p1852_4_m1_4_shim_and_handshake.md`
records what the proposal fixes for M1.4 and does not design internals; its
**Step 0 — Reality check** (mandatory, before any code, recorded in the plan)
inspects the landed `lib/aitasks_home.sh` API and the landed binary's
`version --json` output shape (name the tasks and commits).

## Scope (from the proposal)

- `.aitask-scripts/aitask_testmap.sh` resolves the binary through a **strict
  handshake**, in order: `AIT_TESTMAP_BIN` (with an override notice) >
  `AIT_ENGINE=dev` slot at `$AITASKS_HOME/engine/dev/` requiring a version of
  the form `<V>-dev+<sha>` > `$AITASKS_HOME/engine/v<V>/` requiring `== VERSION`
  exactly (never newest-wins) > `ENGINE_MISSING:<path>` exit 3 with the repair
  hint (`ait setup` / `ait engine build`). The shim **never downloads**, so a
  gate run never performs a network fetch. Then it execs the binary with the
  caller's arguments.
- `.aitask-scripts/lib/platform_detect.sh` maps `uname` to the
  `<os>_<arch>` asset suffix (`linux`/`darwin` × `amd64`/`arm64`).
- The `ait testmap` dispatcher arm in `ait` (`testmap)  shift; exec
  "$SCRIPTS_DIR/aitask_testmap.sh" "$@" ;;`), listed in `show_usage`.
- Tests: `tests/test_testmap_shim.sh` with an `AITASKS_HOME` host directory
  and a fake binary answering `version --json`; `tests/test_platform_detect.sh`.
- **Permission touchpoints are not this child's** (parent-plan Deviation 2):
  no skill invokes the shim in M1; the first skill consumer (M6.5 / M8.3 /
  M9.3) adds the five-touchpoint allowlist entries.

## Key files to modify

- `.aitask-scripts/aitask_testmap.sh` — new (owned).
- `.aitask-scripts/lib/platform_detect.sh` — new (owned).
- `ait` — the `testmap)` arm and its usage line (owned arm).
- `tests/test_testmap_shim.sh`, `tests/test_platform_detect.sh` — new (owned).
- `tests/lib/test_scaffold.sh` — copy-list entries for `aitasks_home.sh` /
  `platform_detect.sh` if they join a startup `source` chain (rule in
  `aidocs/framework/shell_conventions.md`).

## Reference files for patterns

- `ait` dispatcher arms (`create)`, `board)` …) and `show_usage`.
- `.aitask-scripts/lib/python_resolve.sh` — a resolver with an ordered
  candidate list; `.aitask-scripts/lib/aitask_path.sh` — sourced-lib guard.
- `tests/test_global_shim.sh` for a shim test that stages a fake tree.
- `aidocs/framework/aitasks_extension_points.md` "No global PATH override for
  framework-internal binaries" and "Adding a new helper script";
  `aidocs/framework/shell_conventions.md`; `sed_macos_issues.md`.

## Provides / consumes

- **Provides:** `ait testmap <verb>` and the shim path for every later bash
  caller; `platform_detect.sh` for M1.5's asset name.
- **Consumes:** M1.1 (`t1852_1`), M1.2 (`t1852_2`).

## Implementation plan (coarse)

1. Step 0 — Reality check.
2. `platform_detect.sh` + its test.
3. `aitask_testmap.sh` handshake + dispatcher arm + usage line.
4. `tests/test_testmap_shim.sh`: one case per tier, the override notice, the
   `<V>-dev+<sha>` rule, the exact-VERSION rule, `ENGINE_MISSING` exit 3.

## Verification

- `bash tests/test_testmap_shim.sh` and `bash tests/test_platform_detect.sh`
  pass; `shellcheck` clean.
- With a real M1.2 binary placed at `$AITASKS_HOME/engine/v$(cat
  .aitask-scripts/VERSION)/ait-testmap`, `./ait testmap version` prints the
  engine's version line; with it absent, exit 3 and `ENGINE_MISSING:<path>`.
