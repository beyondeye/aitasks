---
Task: t1852_5_m1_5_install_upgrade_dev_verbs.md
Parent Task: aitasks/t1852_testmap_m1_engine_foundation_and_distribution.md
Sibling Tasks: aitasks/t1852/t1852_1_*.md, aitasks/t1852/t1852_2_*.md, aitasks/t1852/t1852_3_*.md, aitasks/t1852/t1852_4_*.md, aitasks/t1852/t1852_6_*.md
Archived Sibling Plans: aiplans/archived/p1852/p1852_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-05 23:43
---

# Plan: t1852_5 — M1.5 Install, upgrade and developer verbs

## Context

Parent goal: M1, the engine foundation and distribution. This child is **M1.5**,
wave **C**. M1.1–M1.4 landed the pieces it needs: the `AITASKS_HOME` resolver,
the Go engine, the release assets and the `ait testmap` shim. **No host gets an
engine yet.** `ait setup` / `ait upgrade` never download the binary, so
`ait testmap` always answers `ENGINE_MISSING`. After this task:

- every `ait setup` and `ait upgrade` installs the exact-version engine into
  `$AITASKS_HOME/engine/v<V>/`;
- setup prints `TESTMAP:<state>`;
- developers get `ait engine build|test|cross|prune`.

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`.
The relevant parts are the Module Map row M1.5 and the component *Engine install,
upgrade and state report*. Also relevant: Assumptions `assumption_release_asset(s)_reachable` and
`assumption_one_engine_per_framework_version`, and Tradeoffs
`tradeoff_setup_network_fetch`, `tradeoff_engine_version_skew` and
`tradeoff_engine_absent_on_host`. The parent plan's Deviations are 1, 2, 4 and 8.

## Step 0 — Reality check (executed 2026-10-05, main @ d0e102a1c)

Providers verified on main: M1.1 `9129a27c6` (`lib/aitasks_home.sh`,
`setup_aitasks_home()`), M1.2 `33012bff7`, M1.3 `c1095fff6` (`goengines/build.sh`,
release wiring), M1.4 `d0e102a1c` (`aitask_testmap.sh`, `lib/platform_detect.sh`).
The **v0.36.1 GitHub release already carries** `ait-testmap_0.36.1_{linux,darwin}_{amd64,arm64}`
+ `ait-testmap_0.36.1_SHA256SUMS.txt` (checked with `gh release view`), so the
release tier can be exercised live. All four inbox notes (t1852_1..4) match the
landed files.

| # | proposal / coarse plan says | repository has | decision |
|---|---|---|---|
| 1 | `.sha256` sidecar short-circuit | M1.3 publishes no sidecar asset | **adapt**: the sidecar is installer-side, `<slot>/ait-testmap.sha256` in `sha256sum` format (`<hex>  ait-testmap`), written after a verified release install. On re-run, `sha256sum -c` of it plus a passing self-check means skip the fetch (no network). |
| 2 | "`.dev`-marked binaries never overwritten" | marker undefined | **adapt**: `<slot>/.dev` marker file, written whenever a release slot is filled from a non-release source (`--local-engine`, `--engine-from-source`). It is written **before** the binary rename, so it fails safe. Any later install into that slot is refused (`kept-dev`) unless `--force-engine`. The dev slot `engine/dev/` is separate and has no marker. |
| 3 | `install.sh` reaches it after `install_global_shim` | true (line 1518); the parser dies on unknown options; `setup_aitasks_home` is not called on this path | **adapt**: the installer creates `$AITASKS_HOME/engine` itself. |
| 4 | `--local-engine <path>` | `ait` `cd`s to the repo root and exports `AIT_INVOCATION_PWD` | **adapt**: setup resolves a relative path against `AIT_INVOCATION_PWD` (fallback `$PWD`), and install.sh against its own cwd. A missing file is a usage error before anything runs. |
| 5 | every install fetches the release asset | 8 existing tests run the real `install.sh --local-tarball` promising "zero network" (e.g. `test_install_changelog_preservation.sh`, `test_frozen_agents_acceptance.sh` timed run) | **revise plan**: `--local-tarball` means an offline install, so install.sh calls the installer with `AIT_TESTMAP_FETCH=0` and only the network tier is skipped. An explicit `--local-engine` / `--engine-from-source` is still honoured. `ait upgrade` never passes `--local-tarball`, so upgrades fetch. |
| 6 | `--engine-from-source` builds with `goengines/build.sh` | `goengines/` is excluded from the release tarball | **adapt**: works only in a framework checkout. Elsewhere it prints `TESTMAP_BINARY:no-source` and a hint (build in an aitasks clone, then `--local-engine`). The proposal's "off-matrix hosts build from source" is true only via that route; the hint documents it. |
| 7 | `TESTMAP:absent` when "no `aitestmap/`" | the proposal's own `ait test` rule: registry present ⇔ `aitestmap/config.yaml` | **adapt**: use `aitestmap/config.yaml`, so setup and `ait test` share one definition. |
| 8 | self-check `version --json` echoes `<V>` | shim reads text `VERSION:` | **both**: the installer self-checks the staged binary with `version --json` (`"version":"<V>"`). The state report runs the shim's own `testmap_resolve_engine` (text handshake). |
| 9 | `HOME_LEGACY:` hint in the M1.5 component text | the Module Map gives it to M1.6 | **M1.6's** (Module Map wins, parent Deviation 1). |
| 10 | prune "against the project registry" | `~/.config/aitasks/projects.yaml` (`AITASKS_PROJECTS_INDEX`); machine output `aitask_project_resolve.sh list` → `PROJECT:<name>:<path>:<RESOLVED\|STALE>` | **adapt**: fail closed. A missing or unparseable registry, or a RESOLVED project with an unreadable VERSION, means `PRUNE_REFUSED:` and nothing is removed. The current project's version is always kept. |
| 11 | owned files: the two setup functions | setup and `aitask_engine.sh` both need fetch / verify / atomic-install / self-check | **revise plan**: a new M1.5-owned lib `lib/engine_install.sh`, sourced lazily inside the setup functions (not on any startup chain, so no scaffold entry) and at column 0 by `aitask_engine.sh`. It is registered in the grep guard. |
| 12 | `.aitask-testmap/` gitignored by setup | the gate-logs helper pattern runs `git commit -m` with no pathspec (it commits the whole index) | **adapt**: new `setup_testmap_gitignore()` with the same shape, but committing `-- .gitignore` only. This repo's own `.gitignore` gains the line in the code commit. |
| 13 | `AITASKS_HOME_LOCK` "refused-against by any `ait`" | nobody takes the lock yet (M1.6 introduces the flock) | **adapt**: leave it to M1.6 and note it to t1852_6. |
| 14 | `ait` arm | `testmap` is in the update-check skip list (line-protocol stdout) | `engine` joins the skip list. Its stdout is also line protocol. |
| 15 | `install.sh` may run under macOS `/bin/bash` 3.2 | `"${arr[@]}"` on an empty array under `set -u` dies in 3.2 | use `${arr[@]+"${arr[@]}"}` for the engine-arg pass-through. |
| 16 | (plan review, concern 1) self-check of the staged download | curl/wget create downloads 0644 (non-executable) | `engine_stage_exec` (checked `chmod 0755`) on every staged binary **before** its self-check; R0/R1 pin it through the real fetch helper. |
| 17 | (plan review, concern 2) `.dev` protection | an early check plus an unserialised publish lets a concurrent setup (another project, same `AITASKS_HOME`) overwrite a custom engine and clear its marker | per-slot `stale_lock` (`$AITASKS_HOME/engine/.locks/<slot>`) held by every slot writer (three install tiers, `engine build`, `engine prune`), with the authoritative `.dev` re-check inside it. This is distinct from M1.6's home-migration lock. `registry_lock` is rejected because its `EXIT` trap would replace install.sh's cleanup trap. |
| 19 | (plan review r2) lock parent | `stale_lock`'s guard and lock are plain `mkdir`s, so a missing `.locks/` reads as permanently busy | checked `mkdir -p` of `engine/.locks` before every acquire; preparation failure (`lock-unavailable`) is reported separately from contention (`slot-busy`); D6 runs on a fresh root. |
| 20 | (plan review r2) prune keep set | "each project's VERSION" did not say which file and did not validate contents | `.aitask-scripts/VERSION` only (a root `VERSION` is the consuming project's), read through the shared validator `engine_read_framework_version`; empty or malformed content gives `version-invalid`; the whole keep set is validated before any deletion (E2, E2b). |
| 18 | (plan review, concern 3) failure handling | `… \|\| true` disables errexit across the whole called function tree | every failable step is explicitly checked; publish rolls back marker and sidecar on a failed replacement; `installed` is printed only after a successful rename; F1–F4 run under both call shapes. |

Downstream notes to send after approval (`/aitask-note`):
- **t1852_6**: the `aitask_engine.sh` dispatch shape and where the `home` arm goes;
  `lib/engine_install.sh`; nobody honours `AITASKS_HOME_LOCK` yet (M1.6 adds the
  refusal to `install_engine_binary` / `prune`); the `.dev` marker and sidecar files inside the slots;
  the per-slot publication locks under `$AITASKS_HOME/engine/.locks/` (moving
  `engine/` while one is held must be refused — the migration preflight should
  treat a live slot lock as busy).
- **t1857 (M6.1)**: the `report_testmap_state()` switch shape, the
  `aitestmap/config.yaml` presence rule, and the comment marking where
  `bootstrapping|<next>` goes.

Every file touched is M1.5-owned or a named extension. One exception is the
FEATURE lists in M1.1's `tests/test_aitasks_home.sh`, which are M1.5's named
extension of that guard; the t1852_1 note invites it.

## Implementation steps

### 1. New lib `.aitask-scripts/lib/engine_install.sh` (sourced, idempotent guard `_ENGINE_INSTALL_LOADED`)

Bash, no `set -e` of its own. It sources `lib/stale_lock.sh` at column 0 (requires the caller's
`warn()`; setup, install.sh and `aitask_engine.sh` all have it). Functions return status codes and
never call `die`.

**Errexit-independence rule (review concern 3).** These functions run under
`install.sh`'s `install_engine_binary … || true`, where bash disables errexit for
the whole call tree. They also run under setup's plain call, where errexit is on.
So every command that can fail carries its own explicit check: `mktemp`, `cp`,
`chmod`, `mkdir`, every `mv`, every marker and sidecar write, every `rm` of
metadata, the lock acquire, and the fetch. Behaviour is then identical in both
contexts. Nothing after a failed step runs. A success token is printed only
after the binary rename has returned 0.

- `engine_read_framework_version <file>`: prints the version, or returns 1 if the file is missing or unreadable, 2 if it is empty or malformed. One CR is stripped, then the content must match `^[A-Za-z0-9._+-]+$`. It is the single reader for install_engine_binary, `engine build` and prune, and it is only ever given an `.aitask-scripts/VERSION` path.
- `engine_sha256 <file>`: prints the hex digest (`sha256sum`, else `shasum -a 256`); returns 1 when neither tool exists.
- `engine_sha256_check <dir> <sumsfile>`: `(cd dir && sha256sum -c --status f)`, else `shasum -a 256 -c -s`.
- `engine_fetch <url> <dest>`: `curl -fsSL --max-time 120`, else `wget -q --timeout=120`; returns 1 when neither exists. Same flags as install.sh's `download_url()`. **The result is NOT executable** (curl/wget create 0644).
- `engine_stage_exec <file>`: `chmod 0755` with an explicit check. **Called on every staged binary before its self-check** (review concern 1): after checksum verification on the release tier, after `cp` on the local tier, and on the `BUILT:` output on the source tier.
- `engine_self_check <bin> <expected_version>`: `"$bin" version --json </dev/null 2>/dev/null` is grepped `-F` for `"version":"<V>"`. On a mismatch it prints the found version (or `?`) and returns 1.
- `engine_staging_dir`: `mkdir -p "$AITASKS_HOME/engine"`, then `mktemp -d "$AITASKS_HOME/engine/.staging.XXXXXX"`. The staging dir is on the same filesystem as the slot, so the final `mv` is an atomic rename.
- **Per-slot publication lock** (review concern 2):
  - **API.** `engine_slot_lock <slot_name>` runs in two phases with distinct return codes:
    - **Preparation.** A checked `mkdir -p "$AITASKS_HOME/engine/.locks"`. stale_lock's guard and lock are plain `mkdir`s and never create their parent, so on a fresh root an acquire would otherwise just exhaust its retries and look busy. If preparation fails (the parent is missing or not a directory), return **3**. The caller prints `TESTMAP_BINARY:lock-unavailable|<locks dir>`, never `slot-busy`.
    - **Acquire.** `stale_lock_acquire "$AITASKS_HOME/engine/.locks/<slot_name>" "${ENGINE_SLOT_LOCK_RETRIES:-600}" 0.1 "engine slot <slot_name>"` (about 60 s). If it fails while the lock dir exists (there is a holder), return **1**, reported as `slot-busy`. If it fails with no lock dir present, return **3**, reported as `lock-unavailable`. On success return 0 and keep `STALE_LOCK_TOKEN`.
    - `engine_slot_unlock` calls `stale_lock_release` with that token.
    - `prune` and `engine build` use the same codes (`PRUNE_KEPT:<dir>|busy` vs `PRUNE_FAILED:<dir>|lock-unavailable`; `ENGINE_LOCK_UNAVAILABLE:` / `ENGINE_SLOT_BUSY:` for build).
  - **Why not `registry_lock`.** `stale_lock` is used directly because `registry_lock_acquire` installs an `EXIT` trap that would replace install.sh's tmpdir-cleanup trap.
  - **Stale and live holders.** A dead holder pid is reclaimed by the stale_lock protocol. A live holder past the deadline gives `TESTMAP_BINARY:slot-busy|<bin>`, and nothing is written.
  - **Location.** The lock lives outside every `v*/` slot, so prune's `v*` walk never sees it.
  - **Who takes it.** Every slot writer: the three install tiers, `ait engine build` (slot `dev`) and `ait engine prune` (per slot).
  - **What runs inside.** Only the protection re-check and the publish run inside the lock. Downloads, builds and self-checks happen beforehand, in staging.
- `engine_publish <staged_bin> <slot_dir> <mode> [<force>]`, where mode is `release|marked|devslot`. It must be called with the slot lock held, and returns 0 published / 1 nothing changed / 2 rollback failed.
  1. **Authoritative protection re-check.** For `release|marked` without force, a `.dev` present now gives `kept-dev` and return 1. The check is under the lock, so a writer that marked the slot after our early check is never overwritten.
  2. `mkdir -p "$slot_dir"` (checked).
  3. `release`. The sidecar `<hex>  ait-testmap` is prepared in staging beforehand and verified by `engine_sha256_check`. Then:
     - `mv -f` the binary. On failure return 1: the rename is atomic, so the old binary is intact.
     - `mv -f` the sidecar. On failure: warn `sidecar-not-written`, still published (a missing or stale sidecar only costs a re-fetch).
     - `rm -f .dev` under `--force`. On failure: warn and keep the marker, which is conservative.
  4. `marked`. Remember `had_dev`, then:
     - write `.dev` if absent (on failure return 1);
     - move any sidecar aside into staging (on failure, roll back the marker and return 1);
     - `mv -f` the binary. On failure, roll back: restore the sidecar and remove a marker that we created. Return 1, or 2 if a rollback step itself failed.
  5. `devslot`: `mv -f` only (checked).
- Header comment with an Interfaces table (each output token and the test case that pins it), matching the shim's style.

### 2. `install_engine_binary [--local-engine P] [--engine-from-source] [--no-testmap] [--force-engine]` in `aitask_setup.sh`

Placed after `setup_aitasks_home()`. It sources `$SETUP_LIB_DIR/engine_install.sh` and
`platform_detect.sh` inside the function. **It always returns 0 (non-fatal)**: bad
args print `TESTMAP_BINARY:usage|…` and return 0. Protocol lines go bare on stdout,
and hints use `info`/`warn`.

1. **Skip.** `--no-testmap` prints `TESTMAP_BINARY:skipped` and returns.
   `AIT_TESTMAP_FETCH=0` disables the release tier. If neither `--local-engine`
   nor `--engine-from-source` was given, it prints `TESTMAP_BINARY:skipped` and returns.
2. **Version.** V is read from `$VERSION_FILE` (`.aitask-scripts/VERSION`) by `engine_read_framework_version`: strip CR, non-empty, `^[A-Za-z0-9._+-]+$`.
   Otherwise it prints `TESTMAP_BINARY:version-invalid|<file>` and returns.
   `slot=$(aitasks_engine_dir "$V")` and `bin=$slot/ait-testmap`.
3. **`.dev` protection, early fast path.** If `$slot/.dev` exists and `--force-engine` is not set, print
   `TESTMAP_BINARY:kept-dev|<bin>`, warn "pass --force-engine to replace", and return.
   This avoids a pointless download. **It is not the guard**: the authoritative re-check is
   step 1 of `engine_publish`, under the slot lock.
4. **Local tier (final if given).** `--local-engine P`: `cp` P into staging (checked), then
   `engine_stage_exec`, then self-check against V.
   - Fail: `TESTMAP_BINARY:self-check-failed|local|<found>`; nothing is installed and no later tier runs.
   - Pass: `engine_slot_lock`, then `engine_publish … marked`, then `engine_slot_unlock`. Print
     `TESTMAP_BINARY:installed|<bin>|local` only when the publish returns 0.
5. **Short-circuit.** This applies when there is no `--force-engine`, `bin` exists, the sidecar
   exists, `engine_sha256_check` passes, and the self-check passes. Then print
   `TESTMAP_BINARY:present|<bin>` and return (no network).
6. **Release tier** (unless fetch is disabled):
   - Platform: `suffix=$(platform_asset_suffix)`. On failure, print `TESTMAP_BINARY:platform-unsupported|<uname -s>|<uname -m>` and go to step 7.
   - Base URL: `${AIT_ENGINE_RELEASE_URL:-https://github.com/$REPO/releases/download/v$V}`. The override is for mirrors and file:// tests, and is documented.
   - Fetch `ait-testmap_<V>_SHA256SUMS.txt` and `ait-testmap_<V>_<suffix>` into staging.
     A failure prints `TESTMAP_BINARY:fetch-failed|<url>` and goes to step 7.
   - Checksum: extract exactly one line matching `^[0-9a-f]{64}  ait-testmap_<V>_<suffix>$` into `asset.sum`, then run `engine_sha256_check`.
     A missing line or a failed check prints `TESTMAP_BINARY:checksum-mismatch|<asset>`, removes staging, and goes to step 7. The slot is untouched.
   - Then `engine_stage_exec` on the verified asset (it arrives 0644), then the self-check.
     A failure gives `self-check-failed|release|<found>` and step 7.
   - Then lock, then `engine_publish … release [force]`, then unlock. Print `TESTMAP_BINARY:installed|<bin>|release` only when the publish returns 0.
7. **Source tier** (only with `--engine-from-source`):
   - `build=$SETUP_LIB_DIR/../../goengines/build.sh`. If it is absent, print `TESTMAP_BINARY:no-source|<path>` with the hint.
   - Otherwise run `"$build" --version "$V" --out "$staging" host` (rc checked) and take exactly one `BUILT:` line.
     Then `engine_stage_exec`, the self-check, and lock → publish `marked` → unlock.
     Print `TESTMAP_BINARY:installed|<bin>|source` only on a publish returning 0.
8. **Publish failures.**
   - Return 1 (not `kept-dev`): `TESTMAP_BINARY:install-failed|<bin>`, warn "previous binary and protection unchanged".
   - Return 2: `TESTMAP_BINARY:install-failed|rollback|<bin>` and a loud warn naming the slot for manual inspection.
   - Neither falls through to a later tier.
9. **Nothing installed**, and `bin` absent or failing the self-check: print
   `ENGINE_MISSING:<bin>|run 'ait setup --local-engine <path>' or '--engine-from-source'` and warn.
   An existing valid binary is left as-is, and the message says so.
   Staging is always removed by an explicit `rm -rf` on every return path (no trap). The slot lock is always released before return.

### 3. `report_testmap_state` in `aitask_setup.sh`

```bash
# M6.1 (t1857) named extension: an unfinished aitestmap/onboard.yaml ledger
# reports TESTMAP:bootstrapping|<next phase> — insert its branch between the
# absent and onboarded arms below. Setup reports; it never onboards.
```
- **Engine probe.** In a subshell: `source "$SETUP_LIB_DIR/../aitask_testmap.sh" --source-only`,
  then `rc=0; testmap_resolve_engine 2>/dev/null || rc=$?`, and echo the error.
  It honours `AIT_TESTMAP_BIN` / `AIT_ENGINE`, so it reports what `ait testmap` would do. VERSION is the framework's own.
- **States:**
  - rc ≠ 0 → `TESTMAP:engine-missing`, plus `info` with the resolver's diagnostic line;
  - no `$SCRIPT_DIR/../aitestmap/config.yaml` → `TESTMAP:absent|run /aitask-testmap-onboard`;
  - else → `TESTMAP:onboarded`.
- Returns 0 always.

### 4. `setup_testmap_gitignore` + `main()` / `usage()` in `aitask_setup.sh`

- The gitignore helper is a clone of `setup_gate_logs_gitignore`. It writes `.aitask-testmap/`
  with the comment `# Test map runs, ledger and onboarding scratch (per-checkout)`, and commits with `git commit -m … -- .gitignore`.
  It is called right after `setup_gate_logs_gitignore`.
- **`main()` parser** gains:
  - `--local-engine <path>`, resolved against `${AIT_INVOCATION_PWD:-$PWD}`. A missing arg or file is a `die`.
  - `--engine-from-source`, `--no-testmap` and `--force-engine`, collected into `engine_args=()`.
  - `--no-testmap` combined with any other engine flag is a `die`.
  - `--hooks-only` combined with an engine flag is a `die`.
- **Calls in `main()`:** `install_global_shim` is followed by
  `install_engine_binary ${engine_args[@]+"${engine_args[@]}"}` and then `report_testmap_state`.
- `usage()` gains the four flags, `AIT_TESTMAP_FETCH=0` and an example.

### 5. `install.sh`

- Parser: `--local-engine` requires an arg, and the path is made absolute (the file must exist,
  else `die` before extraction). `--engine-from-source`, `--no-testmap` and `--force-engine`
  go into `ENGINE_ARGS=()`, with the same conflict rule as setup.
- `usage()`: the four flags.
- In `main()`, right after `install_global_shim`:
  ```bash
  info "Installing test map engine..."
  if [[ -n "$LOCAL_TARBALL" ]]; then   # offline install: no network fetch
      AIT_TESTMAP_FETCH=0 install_engine_binary ${ENGINE_ARGS[@]+"${ENGINE_ARGS[@]}"} || true
  else
      install_engine_binary ${ENGINE_ARGS[@]+"${ENGINE_ARGS[@]}"} || true
  fi
  ```
  (A function-call prefix assignment is temporary in bash, so it does not leak.)

### 6. `.aitask-scripts/aitask_engine.sh` (new) + `ait`

- Header: `set -euo pipefail`. It sources `lib/aitasks_home.sh` and `lib/engine_install.sh` at column 0.
  `GOENGINES="$SCRIPT_DIR/../goengines"`. Usage errors print `USAGE:<msg>` on stderr and exit 64.
  An unknown verb prints `UNKNOWN_VERB:<v>`, then usage, and exits 64.
  A comment marks where M1.6's `home [--migrate]` arm goes. Until then `home` is an unknown verb (exit 64).
- **`build`:** requires `$GOENGINES/build.sh` (else `ENGINE_SOURCE_MISSING:<dir>`, exit 3).
  It reads V from VERSION and `sha=$(git -C "$SCRIPT_DIR/.." rev-parse HEAD)`, then runs
  `build.sh --version "$V-dev+$sha" --commit "$sha" --out <staging> host`.
  It runs `engine_stage_exec` and self-checks against `$V-dev+$sha`. Under the slot lock `dev`, it publishes as `devslot` into `aitasks_engine_dir dev`,
  prints `ENGINE_BUILT:<bin>|<version>`, and gives the hint `AIT_ENGINE=dev ait testmap …`.
- **`test [go test args]`:** `cd "$GOENGINES" && go vet ./... && go test ./... "$@"`.
- **`cross [build.sh options]`:** `exec "$GOENGINES/build.sh" all "$@"`.
- **`prune [--dry-run] [--force]`:**
  - **Keep set.** It starts as the current project's **framework** version, read from
    `$SCRIPT_DIR/VERSION`, which is `.aitask-scripts/VERSION`. To that it adds
    `<path>/.aitask-scripts/VERSION` of every `RESOLVED` row from
    `"$SCRIPT_DIR/aitask_project_resolve.sh" list`. A root `<path>/VERSION`
    belongs to the consuming project (t1772) and is **never** read.
    The parse splits the name off at the first `:` and the status at the last `:`; the path is the middle.
  - **Version reading.** Every version goes through one reader, `engine_read_framework_version <file>`
    in the lib, which install_engine_binary shares. It strips one trailing CR and requires
    non-empty content matching `^[A-Za-z0-9._+-]+$`. Those are the engine version rules
    the shim and `build.sh` already apply. The whole keep set is read and validated
    **before any deletion**.
  - **Refusals** (exit 1, nothing removed):
    - `PRUNE_REFUSED:no-registry|<file>`: the registry file is missing;
    - `PRUNE_REFUSED:registry-unreadable|<file>`: the file exists but no row parsed;
    - `PRUNE_REFUSED:version-unreadable|<file>`: the current project's or a RESOLVED project's framework VERSION file is missing or unreadable;
    - `PRUNE_REFUSED:version-invalid|<file>`: the file exists but is empty or malformed.
  - **Walk.** Only real directories `$AITASKS_HOME/engine/v*/` are walked; symlinks are skipped.
    `dev/` and `.staging.*` are never touched.
  - **Per slot:**
    - in the keep set → `PRUNE_KEPT:<dir>|<names csv>`;
    - `.dev` without `--force` → `PRUNE_KEPT:<dir>|dev-marked`;
    - otherwise take the slot lock `v<ver>` and **re-check `.dev`** under it (busy → `PRUNE_KEPT:<dir>|busy`). Then `rm -rf -- "$dir"`, verify that it is gone, and release the lock. The result is `PRUNED:<dir>`, or `PRUNE_FAILED:<dir>` with exit 1 at the end. With `--dry-run` it prints `PRUNE_WOULD:<dir>` and nothing is removed or locked.
- **`ait`:** the `engine)` arm, a usage line under Tools
  (`engine  Build, test, cross-build and prune the test map engine binaries`), and `engine` added to the update-check skip list.

### 7. Grep guard extension (`tests/test_aitasks_home.sh`)

- `FEATURE_FUNCTIONS` += `aitask_setup.sh:install_engine_binary` and `aitask_setup.sh:report_testmap_state`.
- `FEATURE_FILES` += `.aitask-scripts/lib/engine_install.sh`.

### 8. Docs

- `aidocs/packaging/packaging_strategy.md`: a new `## Per-user engine binary (~/.aitasks/engine/)` section, covering:
  - PM packages and nfpm (`arch: all`) do not ship the engine;
  - `ait setup` and `ait upgrade` (through `install.sh`) fetch the exact-version asset into `~/.aitasks/engine/v<V>/` and verify it against `ait-testmap_<V>_SHA256SUMS.txt`;
  - offline / off-matrix hosts use `--local-engine` or `--engine-from-source`;
  - `--no-testmap` / `AIT_TESTMAP_FETCH=0` skip it;
  - pointer to `aidocs/framework/go_engine.md`.
- `CLAUDE.md`: a short `### Engine (ait-testmap)` block after Linting, covering:
  - the install location;
  - the four setup flags and `AIT_TESTMAP_FETCH=0`;
  - `ait engine build|test|cross|prune`;
  - `AIT_ENGINE=dev`;
  - the pointer to `go_engine.md` / `goengines/README.md`.

### 9. `tests/test_install_engine_binary.sh` (new)

The model is `test_install_changelog_preservation.sh`: `enter_scratch_cwd`, asserts helpers,
**file-backed counters** (bodies run in subshells), and a release-layout tarball of this tree.
HOME, SHIM_DIR and `AITASKS_HOME` are redirected into scratch.
- **Engine fixtures.** `mkengine <path> <version>` writes a bash fake answering
  `version` (text) and `version --json` (`{"version":"<v>",…}`).
- **Mirror.** `mkmirror <dir> <V>` writes `ait-testmap_<V>_<host suffix>` (a fake engine) plus a correct
  sums file. The release tier is served by `AIT_ENGINE_RELEASE_URL=file://<dir>`.
- **Install flow:** each case runs the real `install.sh --dir T --local-tarball TB`.
  - I1 `--local-engine FAKE`: exit 0; the binary lands at `$AITASKS_HOME/engine/v$V/ait-testmap` with +x; `.dev` is present; `TESTMAP_BINARY:installed|…|local`; T's shim resolver returns rc 0 with that path.
  - I2 `--no-testmap`: `TESTMAP_BINARY:skipped` and no slot.
  - I3 `AIT_TESTMAP_FETCH=0`: skipped.
  - I4 `--local-tarball` alone: skipped, and a logging fake `curl` on PATH was never called with the engine URL.
  - I5 refusals before extraction (target untouched, non-zero exit): `--local-engine` with no arg; a nonexistent path; `--no-testmap --local-engine X`.
  - I6 a wrong-version fake: `self-check-failed`, slot empty, `ENGINE_MISSING:`, exit 0.
- **Release tier:** run via `source T/.aitask-scripts/aitask_setup.sh --source-only` with the mirror.
  It always goes through the real `engine_fetch` (curl over `file://`), never a pre-staged fixture.
  - R0: pins the fact behind review concern 1. `engine_fetch file://<mirror asset> <dest>`, where the mirror file is +x, yields a non-executable `<dest>`.
  - R1: `installed|…|release`, sidecar present and `sha256sum -c` clean, no `.dev`. This passes only if the staged asset was made executable before the self-check, so it fails if the ordering regresses.
  - R2: mirror removed, re-run gives `present` (no fetch).
  - R3: wrong hex in sums gives `checksum-mismatch`; the slot is absent before and after, and a pre-existing binary is byte-identical.
  - R4: asset missing from sums gives a refusal.
  - R5: an empty mirror gives `fetch-failed` + `ENGINE_MISSING:` and rc 0.
  - R6: a PATH-stub `uname` (`Plan9`) gives `platform-unsupported`.
- **`.dev` protection:**
  - D1: a local install (`.dev`) followed by a release run gives `kept-dev`, bytes unchanged.
  - D2: the same with `--force-engine` replaces from the release; `.dev` is gone and the sidecar written.
  - D3: `--local-engine` over a `.dev` slot gives `kept-dev`; with `--force-engine` it is replaced.
  - D4, the race (review concern 2), made deterministic with a test seam. `AIT_ENGINE_TEST_PRE_PUBLISH_HOOK=<script>` is run, if set, after staging and before `engine_slot_lock`. Its only use is this test, and it is documented as such in the lib header. The case:
    - A release install starts on an unmarked slot and passes the early check.
    - The hook performs a complete `--local-engine` install (`.dev` + a custom binary) in a separate process.
    - Then the release install takes the lock. Expected: `kept-dev`, custom bytes unchanged, `.dev` still present, no `installed` line.
    - Negative control: the same run with the under-lock re-check disabled (a scratch copy of the lib with that line removed) overwrites the custom binary. This proves the case detects the race.
  - D5, lock contention: a live holder of `.locks/v<V>` (a `sleep` process holding it via `stale_lock_acquire` in a background shell), with `ENGINE_SLOT_LOCK_RETRIES=5` (a test knob) → `slot-busy` and the slot untouched. A dead-pid holder is reclaimed and the install proceeds.
  - D6, fresh root (review round 2): every install case (I1, R1, D1) starts from an `AITASKS_HOME` with **no** `engine/` and **no** `engine/.locks/`. The fixtures never precreate them. I1 and R1 assert `.locks/` is absent before the run and that the install succeeds. Lock-preparation failure: `engine/.locks` pre-created as a **regular file** gives `lock-unavailable` (not `slot-busy`), nothing published, and rc 0.
- **Failure handling** (review concern 3). Each case runs under both call shapes: `install_engine_binary … || true` (errexit off, like install.sh) and plain under `set -e` (like setup).
  - F1: the binary rename fails. Injected via a sourced `mv` function wrapper that fails only for `*/ait-testmap` targets. A release install over an existing verified release binary gives `install-failed`, no `installed` line, old binary and old sidecar byte-identical, `.dev` state unchanged, and setup continues (rc 0, the next statement runs).
  - F2: the same failure on a `marked` (local) install over a release slot. The created `.dev` is rolled back, the sidecar is restored, and the old binary is intact.
  - F3: the slot dir is read-only (`chmod 0555`). The marker write fails, giving `install-failed` with nothing changed. Skipped when running as root, where the chmod has no effect.
  - F4: the sidecar move fails (a wrapper fails for `*.sha256`). The result is `installed` plus the `sidecar-not-written` warning; the binary is the new one and the next run re-fetches rather than reporting `present`.
- **Source tier:**
  - S1: in T (no `goengines/`), `--engine-from-source` gives `no-source`.
  - S2 (only when `go` is installed; otherwise a `SKIP:` line, as in shim E1): this repo's setup in a scratch `AITASKS_HOME` gives `installed|…|source`, a real `version` of `VERSION:$V`, and `.dev`.
- **States** (`report_testmap_state`):
  - T1: an empty `AITASKS_HOME` gives `TESTMAP:engine-missing`.
  - T2: an installed engine and no `aitestmap/config.yaml` give `TESTMAP:absent|run /aitask-testmap-onboard`.
  - T3: `aitestmap/config.yaml` present gives `TESTMAP:onboarded`.
- **Wiring:** bounded `main()`, using the T8 pattern from `test_aitasks_home.sh` with the two functions replaced by argument-logging stubs.
  - W1: `--local-engine rel --force-engine` passes the absolute path (resolved against `AIT_INVOCATION_PWD`) and `--force-engine` to `install_engine_binary`. The call order is `install_global_shim` < `install_engine_binary` < `report_testmap_state`.
  - W2: `--no-testmap --local-engine x` dies.
  - W3: no flags gives a call with no args.
- **Gitignore:**
  - G1: `setup_testmap_gitignore` in a scratch git repo adds the line once (idempotent). Its commit touches only `.gitignore`, and a pre-staged unrelated file stays staged and uncommitted.
- **`aitask_engine.sh`:**
  - E1 prune with an `AITASKS_PROJECTS_INDEX` fixture: a RESOLVED project at 1.0.0 and a STALE one; slots v1.0.0, v2.0.0, v3.0.0 (`.dev`), v<current V>, dev/. `--dry-run` removes nothing and prints `PRUNE_WOULD:` for v2 only. A real run removes only v2.0.0. `--force` also removes v3.0.0. `dev/` and v<V> are always kept.
  - E2 refusals, each asserting every slot byte-identical afterwards (nothing removed):
    - no registry → `PRUNE_REFUSED:no-registry`;
    - a RESOLVED project with no `.aitask-scripts/VERSION` → `PRUNE_REFUSED:version-unreadable`;
    - an **empty** one → `PRUNE_REFUSED:version-invalid`;
    - a **malformed** one (`1 2`, or a CR-only body) → `PRUNE_REFUSED:version-invalid`.
  - E2b, root and framework versions differ: project A has root `VERSION` `9.9.9` and `.aitask-scripts/VERSION` `1.0.0`. Expected: slot v1.0.0 is kept and v9.9.9 is pruned.
  - E5 lock: the first prune on a fresh `AITASKS_HOME`, which has no `.locks/`, succeeds; that proves preparation. A live holder of `.locks/v2.0.0` gives `PRUNE_KEPT:…|busy`, and that slot survives.
  - E3: an unknown verb and `home` both exit 64.
  - E4 (go only): `build` gives `ENGINE_BUILT:` with `<V>-dev+<40hex>`, and the shim resolver passes with `AIT_ENGINE=dev` against that `AITASKS_HOME`.

### Post-phase (risk mitigations)

1. [install_regression_sweep] Run each existing install/setup test and require PASS. A failure is fixed in this task, or reported if it is pre-existing on main. The tests:
   - `tests/test_install_changelog_preservation.sh`, `test_install_upgrade_changelog.sh`, `test_install_create_data_dirs.sh`, `test_install_tarball_download.sh`
   - `test_crew_runner_config_delivery.sh`, `test_t167_integration.sh`, `test_frozen_agents_acceptance.sh`, `test_t644_branch_mode_upgrade.sh`
   - `test_seed_manifest_drift.sh`, `test_packaging_cleanup.sh`, `test_install_merge.sh`, `test_aitasks_home.sh`
   - `pytest tests/test_shell_startup_closure.py`

   Then grep the diff of `install.sh` for array expansions and confirm each uses the `${a[@]+"${a[@]}"}` form. Also run `bash -n install.sh`.
2. [live_release_fetch_check] With a scratch `AITASKS_HOME` and HOME, and no `AIT_ENGINE_RELEASE_URL`, source this repo's `aitask_setup.sh --source-only` and call `install_engine_binary`. Expected results:
   - `TESTMAP_BINARY:installed|<scratch>/engine/v0.36.1/ait-testmap|release`;
   - `(cd slot && sha256sum -c ait-testmap.sha256)` passes;
   - the shim's `testmap_resolve_engine` returns rc 0;
   - the real binary's `version` prints `VERSION:0.36.1`;
   - a second call prints `present` with no network, which is proven by a run with `AIT_ENGINE_RELEASE_URL=file:///nonexistent` still reporting `present`.

   Record the outputs in the Final Implementation Notes.

## Verification

- `bash tests/test_install_engine_binary.sh`, `bash tests/test_aitasks_home.sh` and
  `bash tests/test_testmap_shim.sh` all pass.
- `shellcheck -x` passes on `aitask_setup.sh`, `aitask_engine.sh`, `lib/engine_install.sh` and `install.sh`.
- `./ait setup --local-engine <real build>` path: covered by W1 and the scratch install.
- On this repository, `report_testmap_state` prints `TESTMAP:absent|…` once an engine is installed.
- Smoke runs of `ait engine test`, `ait engine cross --out <scratch>` and `ait engine build`,
  plus `ait engine prune --dry-run` against the real registry. The last is read-only.
- Step 9 (Post-Implementation): archival and cleanup follow the shared `task-workflow` Step 9.
  Current-branch profile: no worktree and no merge.

## Risk

### Code-health risk: medium
- `install.sh` is the entry point for both `curl | bash` and `ait upgrade`. A new fatal path there would break every install and every upgrade: the parser, the sourced call, or bash 3.2's empty-array expansion under `set -u` · severity: medium (residual: low, addressed by inline post-phase install_regression_sweep) · → mitigation: inline post-phase install_regression_sweep
- Real `ait setup` runs gain a ~10 MB network fetch. Tests that run a full setup (`test_setup_python_install.sh`, frozen-agents level 3) now download, and existing install tests could pick up new output or a fetch · severity: low (residual, addressed by inline post-phase install_regression_sweep) · → mitigation: inline post-phase install_regression_sweep

- The per-slot lock and the rollback paths add concurrency and failure-handling code. A defect there could wedge a slot (busy forever) or leave mixed metadata · severity: low (live holders time out to `slot-busy`; dead pids are reclaimed by stale_lock; F1–F4, D4 and D5 pin the paths) · → mitigation: none

### Goal-achievement risk: medium
- Four interpretive decisions (Step 0 rows 1, 2, 5, 7) may not match what downstream consumers (M1.6, M6.1) expect: the `.dev` marker meaning, the installer-side sidecar, `--local-tarball` meaning no fetch, and the `aitestmap/config.yaml` presence rule · severity: medium · → mitigation: none (recorded in the Step 0 table; notes to t1852_6 / t1857)
- The release tier is tested only against `file://` fakes. Real GitHub redirects, real asset names and a real sums file stay unproven until a live run · severity: low (residual, addressed by inline post-phase live_release_fetch_check) · → mitigation: inline post-phase live_release_fetch_check

### Planned mitigations
- timing: post-phase | name: install_regression_sweep | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health: install.sh fatal path / existing install tests gaining fetch or output | desc: re-run every existing install/setup test file plus a bash-3.2 array-expansion review of install.sh
- timing: post-phase | name: live_release_fetch_check | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal: release tier proven only against file:// fakes | desc: install from the real v0.36.1 GitHub release into a scratch AITASKS_HOME and verify sidecar, resolver, and the no-network short-circuit
