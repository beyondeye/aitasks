---
priority: medium
effort: high
depends: [t1852_1, t1852_3, t1852_4]
issue_type: feature
status: Ready
labels: [testmap, install, ait_setup, ait_dispatcher, bash_scripts]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-09-22 17:27
updated_at: 2026-09-22 17:27
---

## Context

Child **M1.5 — Install, upgrade and developer verbs** of t1852 (test map
feature, module M1). Wave **C**. After it, every host that ran `ait setup`
has an engine, and setup reports `TESTMAP:<state>`. **Providers:** M1.1
(`t1852_1`, `AITASKS_HOME`), M1.3 (`t1852_3`, the release assets + sums),
M1.4 (`t1852_4`, the shim and `platform_detect.sh`).

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
— Module Map `#### M1` row M1.5 (its owns cell now names the installer flags
and call — parent-plan Deviation 8), component *Engine install, upgrade and
state report (M1.5; the `bootstrapping` state M6.1)*, *Architecture → Process
map*, *Assumptions → Engine, distribution and install (M1)*
(`assumption_release_asset_reachable`, `assumption_release_assets_reachable`,
`assumption_one_engine_per_framework_version`), *Tradeoffs → Engine and
distribution (M1)* (`tradeoff_setup_network_fetch`, `tradeoff_engine_version_skew`,
`tradeoff_engine_absent_on_host`). Parent plan:
`aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md`.

**Coarse plan only.** The child plan `aiplans/p1852/p1852_5_m1_5_install_upgrade_dev_verbs.md`
records what the proposal fixes for M1.5 and does not design internals; its
**Step 0 — Reality check** (mandatory, before any code, recorded in the plan)
inspects the landed resolver, assets naming, shim, `install.sh`'s parser and
post-shim call site, and `aitask_setup.sh::main()`'s flag parser (name the
tasks and commits).

## Scope (from the proposal)

- `install_engine_binary()` in `aitask_setup.sh`: source order
  `--local-engine <path>` > exact-version release asset
  (`ait-testmap_<V>_<os>_<arch>` from the GitHub release, URL family
  `install.sh` already uses) > `--engine-from-source` (`goengines/build.sh`)
  > `ENGINE_MISSING` warning; `sha256sum -c` / `shasum -a 256` against
  `ait-testmap_<V>_SHA256SUMS.txt` with a `.sha256` sidecar short-circuit;
  **atomic** install to `$AITASKS_HOME/engine/v<V>/`; self-check —
  `version --json` must echo `<V>`; `.dev`-marked binaries never overwritten
  without `--force-engine`; `--no-testmap` / `AIT_TESTMAP_FETCH=0` print
  `TESTMAP_BINARY:skipped` and nothing else in setup depends on the binary;
  `.aitask-testmap/` added to `.gitignore` by setup (pattern:
  `setup_gate_logs_gitignore()`).
- **Installer integration (owned as a named extension of the installer):**
  the four engine flags in `install.sh`'s `while` parser (today it dies on
  any unknown option) and in `aitask_setup.sh::main()`'s `case` (today only
  `--with-*`), and the `install_engine_binary` call right after
  `install_global_shim` in `install.sh` (today the only call there) — so
  `ait upgrade` → `install.sh --force --dir` reaches it.
- `aitask_engine.sh` with `ait engine build|test|cross|prune` (`prune` walks
  only `$AITASKS_HOME/engine/v*/` against the project registry — never
  count-based); the `engine)` dispatcher arm. The `home [--migrate]` arm is
  **M1.6's** (named extension).
- `report_testmap_state()` runs after the install: `TESTMAP:engine-missing`
  (binary absent), `TESTMAP:absent` with `run /aitask-testmap-onboard` (no
  `aitestmap/`), `TESTMAP:onboarded`; the `bootstrapping|<next phase>` state
  is **M6.1's** named extension — leave the switch shaped for it and say so
  in a comment. Setup reports and never onboards.
- Docs: the `aidocs/packaging/packaging_strategy.md` paragraph naming
  `~/.aitasks/engine/`; the `CLAUDE.md` Engine block.
- `tests/test_install_engine_binary.sh` drives a **real**
  `install.sh --dir <scratch> --local-engine <bin>` (the rule in
  `aidocs/framework/aitasks_extension_points.md` "Test the full install flow
  for setup helpers") and asserts the `$AITASKS_HOME/engine/v<V>/` path,
  checksum refusal, `.dev` protection, `--force-engine`,
  `TESTMAP_BINARY:skipped` via both `--no-testmap` and `AIT_TESTMAP_FETCH=0`,
  and each `TESTMAP:` state.

## Key files to modify

- `.aitask-scripts/aitask_setup.sh` — `install_engine_binary()`,
  `report_testmap_state()`, the four flags in `main()`, the calls (owned).
- `install.sh` — the four flags, their pass-through, the call after
  `install_global_shim` (owned extension).
- `.aitask-scripts/aitask_engine.sh` — new; `build|test|cross|prune` (owned;
  `home` reserved for M1.6).
- `ait` — the `engine)` arm and usage line.
- `tests/test_install_engine_binary.sh` — new (owned).
- `aidocs/packaging/packaging_strategy.md`, `CLAUDE.md` — the paragraph /
  block (owned).

## Reference files for patterns

- `install.sh` `download_tarball()`, `github_api_tarball_url()` and
  `.aitask-scripts/lib/github_release.sh` for the release-asset URL family.
- `aitask_setup.sh` `install_global_shim()`, `setup_gate_logs_gitignore()`,
  `setup_dev_deps()` (opt-in tier + marker idiom), the `main()` flag parser.
- `tests/test_global_shim.sh`, `tests/test_agent_instructions.sh` — tests that
  source `install.sh --source-only` / run `install.sh --dir`.
- CLAUDE.md "CLI Conventions" (`ait setup` = repair/reinstall verb).

## Provides / consumes

- **Provides:** an installed engine on every host that ran `ait setup`;
  `TESTMAP:<state>`; `ait engine build|test|cross|prune`.
- **Consumes:** M1.1 (`t1852_1`), M1.3 (`t1852_3`), M1.4 (`t1852_4`).
- **Named extensions into this child's files:** M6.1 adds the
  `bootstrapping|<next>` state; M1.6 adds the `home` arm of `aitask_engine.sh`.

## Implementation plan (coarse)

1. Step 0 — Reality check.
2. `install_engine_binary()` + flags in setup; `.aitask-testmap/` gitignore.
3. `install.sh` flags + call; `aitask_engine.sh` + dispatcher arm.
4. `report_testmap_state()` with the three states and the M6.1 seam comment.
5. Docs paragraph + CLAUDE.md block; the install-flow test.

## Verification

- `bash tests/test_install_engine_binary.sh` passes (real `install.sh --dir`).
- `ait setup --local-engine <bin>` installs to `$AITASKS_HOME/engine/v<V>/`
  and prints `TESTMAP:absent` on this repository; `ait setup --no-testmap`
  prints `TESTMAP_BINARY:skipped`; a wrong checksum is refused.
- `ait engine prune` removes only versions no registered project uses.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1852_1** id=2026-09-23T13:21:13Z.c4cb586f02c1845c7d33bff1 from=t1852_1 from_verified=yes at=2026-09-23T13:21:13Z base=5e378b436a5237d795aff5d9abc498e6632a4880 base_branch=main dirty=yes host=omg16
>
> | From the t1852_1 (M1.1) reality check — two things your child consumes. Claim, not instruction; the lib and the guard are approved but UNCOMMITTED as of this moment (main @ 63012375f + working tree), so verify against the landed files when you pick.
> | 
> | 1. Resolver API: `.aitask-scripts/lib/aitasks_home.sh` exports `AITASKS_HOME` (default `$HOME/.aitasks`) and `AITASKS_HOME_LOCK`; `aitasks_engine_dir <version|dev>` prints `$AITASKS_HOME/engine/v<version>` or `$AITASKS_HOME/engine/dev` WITHOUT a trailing slash (bare VERSION, no `v` prefix; empty arg -> return 2). `aitask_setup.sh` already sources it at column 0 (after `data_symlinks.sh`), so `install_engine_binary()` / `report_testmap_state()` can use `$AITASKS_HOME` directly; `aitask_engine.sh` must source it itself. `ait setup` creates `$AITASKS_HOME/engine` (0755) in a `setup_aitasks_home()` step placed right before `install_global_shim` in `main()` — your installer runs after it and can assume the directory exists. The summary prints the protocol token `AITASKS_HOME:<path>` (no space) right after `Python venv:`.
> | 
> | 2. Grep guard (`tests/test_aitasks_home.sh`): it scans whole feature-owned files (pre-registered: `aitask_engine.sh` among them) AND feature-owned functions inside shared files, listed in `FEATURE_FUNCTIONS=( "aitask_setup.sh:setup_aitasks_home" )` and extracted with `awk '/^<name>\(\) \{/,/^}/'`. When your two setup functions land, register `aitask_setup.sh:install_engine_binary` and `aitask_setup.sh:report_testmap_state` there (that is your named extension of the guard). An unmarked `$HOME/.aitask` / `~/.aitask` line inside those bodies or anywhere in `aitask_engine.sh` fails it; exemption is per line only, via a trailing `# legacy-root-ok: <reason>` comment — there is no file allowlist.

> **✉ note:t1852_2** id=2026-09-24T06:18:19Z.0a80606bb4e8b36b37edcadd from=t1852_2 from_verified=yes at=2026-09-24T06:18:19Z base=33012bff731972003d827cd6b152419d11ab9353 base_branch=main dirty=yes host=omg16
>
> | M1.2 landed in commit 33012bff7. For install_engine_binary and `ait engine build`:
> | - Self-check: `version --json` gives {"version":"<V>",…}; grep `"version":"<V>"`, or use text mode and match `^VERSION:<V>$`.
> | - `ait engine build` / `--engine-from-source` must pass `-ldflags "-X main.version=<V>-dev+<sha> -X main.commit=<sha>"` (dev slot) or `-X main.version=<V>` (release slot). Without them the binary reports `devel`, which the shim refuses by design.
> | - There is no contract ldflag (it is a source constant). Shapes are in goengines/README.md "## Interfaces".
