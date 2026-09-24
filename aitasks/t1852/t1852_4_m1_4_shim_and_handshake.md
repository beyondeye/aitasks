---
priority: medium
effort: medium
depends: [t1852_1, t1852_2]
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1852_1** id=2026-09-23T13:21:10Z.e3adb1202e1da3bb3a5b4516 from=t1852_1 from_verified=yes at=2026-09-23T13:21:10Z base=5e378b436a5237d795aff5d9abc498e6632a4880 base_branch=main dirty=yes host=omg16
>
> | From the t1852_1 (M1.1) reality check — the resolver API shape you consume. Claim, not instruction; the lib is designed and approved but UNCOMMITTED as of this moment (main @ 63012375f + working tree), so verify against the landed file when you pick.
> | 
> | - `.aitask-scripts/lib/aitasks_home.sh` (double-source guard `_AITASKS_HOME_LOADED`) exports `AITASKS_HOME` (default `$HOME/.aitasks`) and `AITASKS_HOME_LOCK` (`$AITASKS_HOME/.home.lock`).
> | - `aitasks_engine_dir <version|dev>` prints the slot WITHOUT a trailing slash: `dev` -> `$AITASKS_HOME/engine/dev`; any other arg -> `$AITASKS_HOME/engine/v<arg>` (pass the bare VERSION, no `v` prefix). Empty arg -> usage on stderr, return 2. Compose the binary path as `"$(aitasks_engine_dir "$V")/ait-testmap"`.
> | - Source it from the shim exactly like setup does: unconditional, column 0, `source "$SCRIPT_DIR/lib/aitasks_home.sh"` (the startup-closure contract test derives fixture copy lists from that shape). It is being added to `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` by t1852_1, so `test_testmap_shim.sh` can rely on the scaffold providing it.
> | - The grep guard in `tests/test_aitasks_home.sh` pre-registers `.aitask-scripts/aitask_testmap.sh` and `lib/platform_detect.sh` as feature files: an unmarked `$HOME/.aitask` / `~/.aitask` line in either will fail it once the file exists. Exemption is per line only, via a trailing `# legacy-root-ok: <reason>` comment.

> **✉ note:t1852_2** id=2026-09-24T06:18:17Z.c291190810d07fcc122bd2da from=t1852_2 from_verified=yes at=2026-09-24T06:18:17Z base=33012bff731972003d827cd6b152419d11ab9353 base_branch=main dirty=yes host=omg16
>
> | M1.2 landed in commit 33012bff7. The binary your shim handshakes with (full shapes in goengines/README.md "## Interfaces"):
> | - `ait-testmap version` prints four lines: `VERSION:<v>`, `COMMIT:<sha>`, `CONTRACT:<n>`, `ENGINE:<abs path, symlinks resolved>`; exit 0.
> | - `version --json` prints one object: {"version":…,"commit":…,"contract":<int>,"engine":…}. The proposal's "version --json prints ENGINE:<path>" is realised as the `engine` key in JSON and the `ENGINE:` line in text.
> | - An unset build reports version `devel` / commit `unknown`, which matches neither `== VERSION` nor `<V>-dev+<sha>`, so a bare `go build` binary fails your handshake closed.
> | - Stub verbs: stderr `NOT_IMPLEMENTED:<verb>`, exit 64, no stdout. Unknown verb: stderr `UNKNOWN_VERB:<verb>` + `USAGE:…`, exit 64. Exit table 0/1/2/3/64/75; a verb returning a code outside its contract becomes 3 with `EXIT_CONTRACT_VIOLATION:`.
