---
Task: t1852_4_m1_4_shim_and_handshake.md
Parent Task: aitasks/t1852_testmap_m1_engine_foundation_and_distribution.md
Sibling Tasks: aitasks/t1852/t1852_1_*.md, aitasks/t1852/t1852_2_*.md, aitasks/t1852/t1852_3_*.md, aitasks/t1852/t1852_5_*.md, aitasks/t1852/t1852_6_*.md
Archived Sibling Plans: aiplans/archived/p1852/p1852_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-05 17:10
---

# Plan: t1852_4 — M1.4 Shim and handshake

## Context

This is child M1.4 of t1852 (test map, module M1), wave **B**. It delivers
`ait testmap <verb>`, the single entry that every later bash caller uses to
reach the `ait-testmap` engine (M5.1, M6.5, M7.4, M7.5, M8.2, M8.3, M9.3). It
also delivers `lib/platform_detect.sh`, which M1.5 needs to compose the
release-asset name.

It has two providers:

- **M1.1** (t1852_1) provides `AITASKS_HOME` and `aitasks_engine_dir`.
- **M1.2** (t1852_2) provides the binary whose `version` output the handshake reads.

The authoritative spec is `aidocs/testing_engine/n014_explorer_006_proposal.md`:

- Module Map row M1.4 (line 682);
- *Binary distribution* (1991–2010);
- *Process map* (302);
- *Run Surface → Resolution* step 2 (1584–1590, the `ENGINE_MISSING:<path>|<repair>` form);
- `assumption_release_asset_reachable` (3180, "the shim never downloads, so a gate run never performs a network fetch");
- `tradeoff_strict_version_handshake` and `tradeoff_engine_absent_on_host` (3652–3662).

## Step 0 — Reality check (executed 2026-10-04, main @ 95f0394cb)

Providers, with the task and commit that landed each:

- **`lib/aitasks_home.sh`**, from **t1852_1, commit `9129a27c6`**. Its API is exactly what that task's note describes:
  - it has a `_AITASKS_HOME_LOADED` guard;
  - it exports `AITASKS_HOME` (`${AITASKS_HOME:-$HOME/.aitasks}`) and `AITASKS_HOME_LOCK`;
  - `aitasks_engine_dir dev|<V>` prints `…/engine/dev` or `…/engine/v<V>` with no trailing slash, and returns 2 on an empty argument.
  - It is already copied by `tests/lib/test_scaffold.sh`.
- **Engine skeleton**, from **t1852_2, commit `33012bff7`**, with later changes from t1872 (`2d3376466`) and t1852_3 (`c1095fff6`, `build.sh`).
  - `version` prints four lines: `VERSION:<v>`, `COMMIT:<sha>`, `CONTRACT:<n>`, `ENGINE:<abs>`, then exits 0. `--json` prints one object instead.
  - A build with no version set reports `devel` / `unknown`.
  - Stub verbs write `NOT_IMPLEMENTED:<verb>` to stderr and exit 64.
  - The engine's exit table is 0/1/2/3/64/75, and exit 3 means a framework error.
  - All of these shapes are pinned in `goengines/README.md` under "## Interfaces".
- **`build.sh`**: `build.sh host --version V --out DIR` prints `BUILT:<abs>`. This is usable for a real-engine test.
- **`.aitask-scripts/VERSION`** is `0.36.0`.
- **The dispatcher** has single-line arms of the form `name) shift; exec "$SCRIPTS_DIR/…" "$@" ;;`. `show_usage` is a heredoc.
  - **`check_for_updates` runs for every command not in the skip list.** It does two things:
    1. On a fresh cache it prints `Update available …` to **stdout**.
    2. On a stale cache it starts a **background `curl`** to api.github.com.
- **The grep guard** in `tests/test_aitasks_home.sh` (T9) already lists `aitask_testmap.sh` and `lib/platform_detect.sh` in `FEATURE_FILES`.
- **t1856** (the M5 parent, which holds M5.1) has **no children yet**.

| # | item | proposal says | coarse plan says | repository has | decision |
|---|---|---|---|---|---|
| 1 | handshake reads | "requiring `== VERSION`" (form unspecified) | `version --json` | text `version` gives `^VERSION:<v>$`, a bash-native line protocol. JSON needs jq/python to parse safely | **adapt**: read the text form, and require exactly one `VERSION:` line. A bash JSON scrape would depend on key order and spacing |
| 2 | missing-engine line | `ENGINE_MISSING:<path>\|run 'ait setup' or set AIT_TESTMAP_BIN` (Run Surface) | `ENGINE_MISSING:<path>` + repair hint | — | **adopt the two-field form**. The repair text depends on the tier: release gets the proposal's exact text; dev gets `run 'ait engine build' or unset AIT_ENGINE`; override gets `fix or unset AIT_TESTMAP_BIN`. All of it goes to **stderr**, like every engine diagnostic, so stdout carries only the engine's own output |
| 3 | network | "the shim never downloads, so a gate run never performs a network fetch" | never downloads | `ait`'s `check_for_updates` would curl in the background, and print to stdout, for `ait testmap` | **adapt**: add `testmap` to the dispatcher's update-check skip list. Without it, `ait testmap` breaks the assumption and can corrupt the stdout line protocol. **Note to t1856**: `ait test` (M5.1) needs the same entry |
| 4 | stdin | — | — | `ait testmap test --changes -` reads stdin, and a handshake child process would inherit it | the handshake runs `"$bin" version </dev/null`; a test pins it |
| 5 | exit 3 is ambiguous | M5.1 must tell "engine absent" apart from "engine framework error" (advisory mode prints `VERDICT:skip REASON:testmap_absent` only for the first) | — | the engine itself exits 3 for `CONTRACT_MISMATCH` and similar | **adapt**: `aitask_testmap.sh --source-only` exposes `testmap_resolve_engine`, which sets `TESTMAP_ENGINE_BIN` or `TESTMAP_ENGINE_ERROR` without exec'ing anything. This is the same `--source-only` idiom as `aitask_setup.sh:4656`. M5.1 probes with the function and does not guess from an exit code. **Note to t1856** |
| 6 | failed explicit tier | "strict handshake", "never newest-wins" | silent | — | **no fall-through**. A broken `AIT_TESTMAP_BIN`, or `AIT_ENGINE=dev` without a valid dev slot, produces `ENGINE_MISSING` naming *that* path, even when a valid release slot exists. A silent fallback would run a different engine than the one the user asked for |
| 7 | dev-version rule | `<V>-dev+<sha>` | same | build.sh accepts any `[A-Za-z0-9]+` commit, and M1.5's `ait engine build` will pass the git sha | require the prefix `<V>-dev+` plus a suffix matching `^[0-9a-f]{7,64}$` (short sha through sha256). **Note to t1852_5** |
| 8 | `platform_detect.sh` startup chain | — | "scaffold entry if it joins a startup chain" | the shim does not need it; only M1.5 composes asset names | it is **not** sourced at startup, so no scaffold entry. The shim sources only `aitasks_home.sh`, which is already in the scaffold |
| 9 | Go naming agreement | `<os>_<arch>` | same | `platform.AssetSuffix()` returns `runtime.GOOS_GOARCH` | `test_platform_detect.sh` cross-checks the live mapping against `go env GOHOSTOS`/`GOHOSTARCH` (never the GOOS/GOARCH target overrides) when Go is present |
| 10 | permission touchpoints | — | not this child's (parent Deviation 2) | no skill calls the shim | none added (confirmed) |
| 11 | downstream M5.1 | — | note "M5.1's child" | t1856 has no children | the note goes to the parent **t1856**, the same way t1852_2 routed its notes to t1853 and t1854 |

**Ownership re-confirmed.** This child owns:

- the two new scripts;
- the two new tests;
- in `ait`, the `testmap)` arm, its usage line, and the `testmap` token in the update-check skip list. The skip-list token is part of wiring the arm safely; no other submodule owns that list.

`test_scaffold.sh` is not touched.

**Notes to send after approval, before implementation.** Each is hedged as uncommitted at the time of sending.

- **t1852_5**:
  - the `platform_detect.sh` API;
  - the dev-version rule (row 7);
  - install the binary at `$(aitasks_engine_dir <V>)/ait-testmap` with mode +x;
  - the self-check can reuse `testmap_resolve_engine`.
- **t1856**:
  - the resolver API and the `TESTMAP_ENGINE_ERROR` prefixes (rows 2 and 5);
  - stderr placement;
  - the update-check skip-list entry `ait test` needs (row 3).

## Implementation steps

### 1. `.aitask-scripts/lib/platform_detect.sh` (new, executable, sourced lib)

The header and guard copy `lib/aitask_path.sh` (`_PLATFORM_DETECT_LOADED`). It sets no `set -e`.

```bash
# platform_os [<uname -s>]   → linux | darwin
# platform_arch [<uname -m>] → amd64 | arm64
# platform_asset_suffix [<uname -s> <uname -m>] → <os>_<arch>
#   (the suffix of the release asset ait-testmap_<V>_<os>_<arch>; mirrors
#    goengines/internal/platform.AssetSuffix)
# Unsupported → stderr PLATFORM_UNSUPPORTED:<uname -s>|<uname -m>, return 1.
```

The functions are pure `case` statements:

- `Linux` → `linux`, `Darwin` → `darwin`;
- `x86_64|amd64` → `amd64`, `aarch64|arm64` → `arm64`.

Arguments default to `$(uname -s)` and `$(uname -m)`, so tests can drive the table without faking `uname`.

### 2. `.aitask-scripts/aitask_testmap.sh` (new, executable)

The file is laid out in this order:

1. The `#!/usr/bin/env bash` shebang and `set -euo pipefail`.
2. `SCRIPT_DIR`.
3. A column-0 `source "$SCRIPT_DIR/lib/aitasks_home.sh"`.
4. A header comment documenting the whole interface: the tiers, every output line and the exit codes.
5. The functions.
6. `[[ "${1:-}" == "--source-only" ]] && return 0 2>/dev/null || true`.
7. `main`.

- `_tm_safe <value>`: succeeds when the value contains no `|`, CR or LF. Every field that is printed goes through it.
- `_tm_engine_version <bin>`: runs `"$bin" version </dev/null 2>/dev/null` and captures stdout and the return code.
  - It succeeds when the return code is 0 and exactly one `^VERSION:` line is present; it then prints the value.
  - Otherwise it returns 1.
  - An unsafe value counts as unreadable.
- `_tm_check_slot <bin> <mode> <V>`, where mode is `release` or `dev`. It succeeds when `<bin>` is `-f` and `-x`, and its version satisfies the mode:
  - `release`: the version is exactly `<V>`;
  - `dev`: the version starts with `<V>-dev+` and the rest matches `^[0-9a-f]{7,64}$`.

  On a rejection it prints one of these to stderr:
  - `ENGINE_REJECTED:<bin>|not-executable` (exists but not executable);
  - `ENGINE_REJECTED:<bin>|version-unreadable`;
  - `ENGINE_REJECTED:<bin>|version-mismatch|<found>|<required>`, where required is `<V>` or `<V>-dev+<sha>`.

  A plain absence prints nothing; the caller emits `ENGINE_MISSING`.
- `testmap_resolve_engine`: the public function, safe to call under `set -e` as `testmap_resolve_engine || rc=$?`. It clears `TESTMAP_ENGINE_BIN` and `TESTMAP_ENGINE_ERROR`, then:
  1. Reads `$SCRIPT_DIR/VERSION` with `$(<file)`, stripping one trailing CR. If the result is empty or falls outside `[A-Za-z0-9._+-]`, it sets `ERROR=VERSION_INVALID:<file>` and returns 3.
  2. **Override tier.** If `AIT_TESTMAP_BIN` is non-empty, it writes `ENGINE_OVERRIDE:<path>` to stderr. It then requires an absolute path that is `-f` and `-x`, and runs **no version check** (this is the escape hatch for fake engines). If those hold, it sets `BIN` and returns 0. Otherwise it writes `ENGINE_REJECTED:<path>|not-absolute` (or `|not-executable` for a missing or non-`-x` file) and sets `ERROR=ENGINE_MISSING:<path>|fix or unset AIT_TESTMAP_BIN`, then returns 3.
  3. **Dev tier.** If `AIT_ENGINE` is `dev`, the slot is `$(aitasks_engine_dir dev)/ait-testmap`. It runs `_tm_check_slot … dev`; success sets `BIN` and returns 0, and failure sets `ERROR=ENGINE_MISSING:<slot>|run 'ait engine build' or unset AIT_ENGINE` and returns 3. If `AIT_ENGINE` is set to anything other than empty or `dev`, it sets `ERROR=USAGE:AIT_ENGINE must be 'dev' or unset` and returns 64.
  4. **Release tier.** The slot is `$(aitasks_engine_dir "$V")/ait-testmap`, checked with `_tm_check_slot … release`. Success sets `BIN`; failure sets `ERROR=ENGINE_MISSING:<slot>|run 'ait setup' or set AIT_TESTMAP_BIN` and returns 3. No other `v*` slot is ever consulted.

  An unsafe `AITASKS_HOME` or override path sets `ERROR=ENGINE_PATH_UNSAFE:<varname>` (naming the variable, not its value) and returns 3.
- **main:** `rc=0; testmap_resolve_engine || rc=$?`. If `rc != 0`, it prints `$TESTMAP_ENGINE_ERROR` to stderr and exits with `$rc`. Otherwise it runs `exec "$TESTMAP_ENGINE_BIN" "$@"`.

The shim never touches the network, PATH or any file.

### 3. `ait`

- Arm, placed after `codeagent)`:

  ```bash
  testmap)      shift; exec "$SCRIPTS_DIR/aitask_testmap.sh" "$@" ;;
  ```

- Usage, under **Tools**:

  ```
  testmap        Run the test map engine (ait-testmap) after its version handshake
  ```

- Add `testmap` to the update-check skip `case` (`ait:190`), with a short comment saying why: line-protocol stdout, and no network on gate paths.

### 4. `tests/test_platform_detect.sh` (new)

The skeleton follows `tests/test_aitasks_home.sh`: `scratch_cwd`, `asserts.sh`, top-level asserts, and the footer. Each case runs in a subprocess.

- The full mapping table, including both `amd64` aliases and both `arm64` aliases.
- Unsupported inputs (`FreeBSD`, `armv7l`) return 1 with `PLATFORM_UNSUPPORTED:` on stderr and nothing on stdout.
- The default no-argument call equals the explicit `$(uname -s) $(uname -m)` call.
- **Go agreement:** if `go` is present, `platform_asset_suffix` equals `$(env -u GOOS -u GOARCH go env GOHOSTOS)_$(… GOHOSTARCH)`. It compares against the **host** values, never `GOOS`/`GOARCH`, which are cross-compile target overrides. Otherwise the case prints `SKIP`.
- **Override isolation control:** re-run the same comparison with the env var `GOOS=darwin GOARCH=arm64` set (on this linux/amd64 host `go env GOOS` would then say darwin/arm64) and assert it still passes. This proves the check reads the host and not the target.
- The lib is idempotent when double-sourced.

### 5. `tests/test_testmap_shim.sh` (new)

The test stages a fake tree at `$S/fw/.aitask-scripts/{aitask_testmap.sh,lib/aitasks_home.sh,VERSION=1.2.3}` and uses `AITASKS_HOME=$S/h`, `HOME=$S/home`. It uses fake engines from `mkfake <path> <version-line-or-'-'> [version-rc]`, written as bash scripts:

- `version` prints the configured line, and records under `$S/ate` if it managed to read stdin.
- Any other verb writes a marker `$S/ran`, prints `ARG:<a>` for each argument, prints `STDIN:<cat>` when the argument is `--stdin`, and exits with `$FAKE_EXIT`.

Assertions run in the main shell.

| case | setup | expect |
|---|---|---|
| R1 release match | `v1.2.3/ait-testmap` reports `1.2.3` | verb runs; args verbatim (`"a b"`, `""`); `FAKE_EXIT=5` → exit 5; stdout only the engine's |
| R2 stdin | same, `printf 'l1\nl2\n' \| shim x --stdin` | `STDIN:l1 l2` intact; `$S/ate` absent (handshake did not eat stdin) |
| R3 absent | no slot | exit 3; stderr `ENGINE_MISSING:$S/h/engine/v1.2.3/ait-testmap\|run 'ait setup' or set AIT_TESTMAP_BIN`; stdout empty |
| R4 mismatch | slot reports `1.2.2` | `ENGINE_REJECTED:…\|version-mismatch\|1.2.2\|1.2.3` + `ENGINE_MISSING`, exit 3, `$S/ran` absent |
| R5 never newest-wins | valid `v1.2.2`, `v9.9.9` slots, none for `1.2.3` | exit 3 `ENGINE_MISSING` naming `v1.2.3` |
| R6 bare build / dev build in release slot | `devel`; `1.2.3-dev+abc1234` | both rejected (exact match only) |
| R7 unreadable / not executable | version exits 1; no `VERSION:` line; slot `chmod -x` | `version-unreadable` ×2, `not-executable` |
| D1 dev match | `AIT_ENGINE=dev`, dev slot `1.2.3-dev+abc1234` | runs |
| D2 dev rejects | `1.2.3`; `1.2.2-dev+abc1234`; `1.2.3-dev+XYZ`; `1.2.3-dev+abc` (too short) | each rejected; with a **valid release slot present**, still exit 3 naming the dev slot and `ait engine build` (no fall-through) |
| D3 dev absent | — | `ENGINE_MISSING:$S/h/engine/dev/ait-testmap\|…` |
| D4 bad AIT_ENGINE | `AIT_ENGINE=release` | exit 64, `USAGE:` |
| O1 override | `AIT_TESTMAP_BIN=<fake answering no version>`, plus `AIT_ENGINE=dev` and a valid release slot | stderr `ENGINE_OVERRIDE:<path>`; the override runs; stdout clean |
| O2 override broken | nonexistent; non-executable; relative path | `ENGINE_MISSING:<that path>\|fix or unset AIT_TESTMAP_BIN`, exit 3, valid release slot NOT used |
| V1 VERSION invalid | VERSION empty; `1 2` | exit 3 `VERSION_INVALID:` |
| U1 unsafe | `AITASKS_HOME=$S/a\|b` | exit 3 `ENGINE_PATH_UNSAFE:AITASKS_HOME` |
| A1 resolver API | `bash -c 'source "$1" --source-only; rc=0; testmap_resolve_engine \|\| rc=$?; echo "$rc\|$TESTMAP_ENGINE_BIN\|$TESTMAP_ENGINE_ERROR"' _ <shim>` for the match and absent cases. The guarded call is required: sourcing enables `set -e`, so an unguarded `return 3` would kill the shell before the echo | `0\|<slot>\|` and `3\|\|ENGINE_MISSING:…` (status and both variables asserted); `$S/ran` absent (nothing exec'd) |
| W1 dispatcher | real repo `./ait testmap version` with `HOME=$S/home2`, `AIT_TESTMAP_BIN=<fake>`, and `$S/home2/.aitask/update_check` pre-seeded `"<now> 99.0.0"` | stdout is exactly the fake's version line; no `Update available` |
| W2 control | same seeded cache, `./ait no-such-cmd` | stdout contains `Update available` (proves the seed works, so W1's absence means the skip-list entry) |
| W3 usage | `./ait help` | contains `testmap` |
| W4 no network (missing cache) | `PATH=$S/fakebin:$PATH`, where `fakebin/curl` appends its args to `$CURL_REC` and exits 0. **Completion is tied to each invocation's own pipe.** Each run is captured as `out=$(… 2>&1)`. `check_for_updates`' background `( … ) &` subshell inherits the dispatcher's stdout, so the substitution returns only after **every** writer of that pipe has closed it, including any update subshell the invocation spawned. No cross-invocation timing is assumed and nothing is polled. **W4b control**: `out=$(HOME=$S/home4 CURL_REC=$S/curl_ctl ./ait no-such-cmd 2>&1)`. **W4a**: `out=$(HOME=$S/home3 CURL_REC=$S/curl_tm AIT_TESTMAP_BIN=<fake> ./ait testmap version 2>&1)` (no update cache) | W4b: `$S/curl_ctl` exists **immediately** after its own substitution returns. This proves both that the fake intercepts the real fetch path and that draining the pipe waits for the background work. W4a: after its own substitution returns, `$S/curl_tm` is absent **and** `$S/home3/.aitask/update_check` is absent (the background subshell writes it whatever curl returns) |
| E1 real engine | if `go` present: compute the **runnable host** target as `$(env -u GOOS -u GOARCH go env GOHOSTOS)_$(env -u GOOS -u GOARCH go env GOHOSTARCH)` and pass it to `env -u GOOS -u GOARCH goengines/build.sh <that target> --version "$(cat .aitask-scripts/VERSION)" --out $S/b`. This uses the explicit `<os>_<arch>` target and never `host`, which reads `go env GOOS/GOARCH` and would follow a caller's cross-compile override; build.sh's interface is unchanged. Copy to `$S/h2/engine/v<V>/ait-testmap`, then `AITASKS_HOME=$S/h2 ./ait testmap version` | first line `VERSION:<V>`; `./ait testmap select` → exit 64, stderr `NOT_IMPLEMENTED:select`; with the slot removed → exit 3 `ENGINE_MISSING`. Else `SKIP` |

### 6. Static checks

- `shellcheck` on the new script, the new lib, both tests and `ait`.
- `bash -n` on each.

### Post-phase (risk mitigations)

1. [shim_interface_table] Add an `# Interfaces` table to the header comment of `aitask_testmap.sh`, one row per consumed shape:
   - the tier order;
   - each stderr line (`ENGINE_OVERRIDE:`, `ENGINE_REJECTED:` and its three reasons, `ENGINE_MISSING:<path>|<repair>` with the three repair texts, `ENGINE_PATH_UNSAFE:`, `VERSION_INVALID:`, `USAGE:`);
   - the exit codes (3 resolution, 64 usage, otherwise the engine's own);
   - the `--source-only` / `testmap_resolve_engine` API, with its return codes and the `TESTMAP_ENGINE_BIN` / `TESTMAP_ENGINE_ERROR` variables;
   - the dev-version rule;
   - "never downloads; skip-listed from `ait`'s update check".

   Each row names the test case ID that pins it (R1…E1).

   Verify: every case ID named in the table is printed by `tests/test_testmap_shim.sh` (grep each `<ID> ` label at least once in the test file).

## Verification

- `bash tests/test_testmap_shim.sh` and `bash tests/test_platform_detect.sh` → `ALL TESTS PASSED`.
- `bash tests/test_aitasks_home.sh` stays green. The T9 guard now scans the two new files instead of reporting them as not landed.
- `shellcheck` is clean.
- Manual: `./ait testmap version` with no engine installed exits 3 with `ENGINE_MISSING:$HOME/.aitasks/engine/v0.36.0/ait-testmap|run 'ait setup' or set AIT_TESTMAP_BIN`. With a real binary built at that path, it prints `VERSION:0.36.0`. Case E1 covers both.

## Step 9 reference

Archival and cleanup follow the shared task-workflow Step 9. Current-branch profile: no worktree, no merge.

Commit: `feature: Add the ait testmap shim with its strict engine handshake (t1852_4)`.

## Risk

### Code-health risk: low
- The `ait` edit (arm + update-check skip token) sits on every dispatcher invocation; a malformed `case` breaks all commands · severity: low · → mitigation: none (W1–W3 drive the real `./ait`; `bash -n` + shellcheck)

### Goal-achievement risk: low
- The shapes chosen here (stderr lines, repair texts, resolver API and variables, dev-version rule) are consumed by M1.5 (t1852_5) and M5.1 (t1856, unplanned); a shape they cannot use forces rework across tasks · severity: low (residual — addressed by inline post-phase shim_interface_table and the notes to t1852_5 / t1856) · → mitigation: inline post-phase shim_interface_table
- E1 (the only check against the real engine binary) SKIPs on a host without Go, so it can silently not run · severity: low · → mitigation: none (Go is present on this host; implementation confirms E1 printed PASS, not SKIP)

### Planned mitigations
- timing: post-phase | name: shim_interface_table | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — downstream consumers of the shim's lines and resolver API | desc: header-comment Interfaces table in aitask_testmap.sh, each row naming the test case that pins it

## Post-Review Changes

### Change Request 1 (2026-10-05 17:30)
- **Requested by user:** `VERSION_INVALID:$version_file` printed an unchecked framework path. A framework directory containing LF split the diagnostic across two lines, and a pipe added a protocol field. This broke the "every printed field passes `_tm_safe`" and "one diagnostic line" promises (CONFIRMED, blocking).
- **Changes made:**
  - When `VERSION` is invalid and its path is unsafe, the error is now `ENGINE_PATH_UNSAFE:SCRIPT_DIR`. This follows the established convention: name the variable and withhold the value.
  - A valid `VERSION` in such a directory still works, because no other line carries `SCRIPT_DIR`.
  - New case U2 covers LF and pipe directories through both the CLI and the resolver, plus the valid-VERSION case.
  - U1 also covers an unsafe `AIT_TESTMAP_BIN`, which was previously untested.
  - The Interfaces row was updated.
  - The pre-fix code fails exactly the four "one line" U2 checks (scratch mutant).
- **Files affected:** `.aitask-scripts/aitask_testmap.sh`, `tests/test_testmap_shim.sh`

### Change Request 2 (2026-10-05 17:45)
- **Requested by user:** an unreadable `VERSION` made `$(<file)` emit Bash's raw permission error before the structured handling ran. With `chmod 000` the CLI printed two stderr lines in a safe directory and four in a directory containing LF, and the resolver also leaked raw stderr (CONFIRMED, blocking).
- **Changes made:**
  - The read is now `{ v="$(<file)"; } 2>/dev/null || v=""`, so a missing or unreadable file reads as empty and produces only the structured line.
  - New case V2 covers a missing `VERSION`, and an unreadable one through the CLI and through the resolver (resolver stderr must be empty).
  - U2 gained the same unreadable checks for LF and pipe directories.
  - Both cases `SKIP` when file modes are not enforced (root).
  - The pre-fix read fails exactly the six new checks (scratch mutant).
  - Also probed: a corrupt ELF and a bad-interpreter engine yield only `ENGINE_REJECTED …|version-unreadable` + `ENGINE_MISSING`, with no raw shell error.
- **Files affected:** `.aitask-scripts/aitask_testmap.sh`, `tests/test_testmap_shim.sh`

## Final Implementation Notes
- **Actual work done:** Steps 1–6 and the `shim_interface_table` post-phase, as planned:
  - `lib/platform_detect.sh`: 60 lines, `platform_os` / `platform_arch` / `platform_asset_suffix`, with `PLATFORM_UNSUPPORTED:<s>|<m>` naming the pair actually examined;
  - `aitask_testmap.sh`: the strict three-tier handshake, the `--source-only` resolver API, and the header Interfaces table with every row naming its pinning case;
  - `ait`: the `testmap)` arm, the usage line, and the `testmap` token in the update-check skip list;
  - `tests/test_platform_detect.sh`: 29 checks;
  - `tests/test_testmap_shim.sh`: 92 checks — R1–R7, D1–D4, O1–O2, V1–V2, U1–U2, A1, W1–W4 and E1 against the real `build.sh`-built engine.
- **Notes sent:** after approval, to t1852_5 (`…8b5ce5e42187c7856b48f7aa`) and t1856 (`…128efd2074b7997a565f900e`). Both returned `LIVE_NONE:unlocked`.
- **Plan-review revisions (before approval):**
  - A1 guards the resolver call, because sourcing enables `set -e`.
  - The Go cross-check and the E1 build use `GOHOSTOS` / `GOHOSTARCH` with `GOOS` / `GOARCH` unset, and a control proves the override would otherwise have moved `go env GOOS`.
  - W4 covers the missing-cache network branch with a fake `curl`. Completion is bound to each invocation's own `$( )` pipe; the control proves the drain waits for the background fetch.
- **Mutation evidence (scratch copies only):** each of these is caught by its targeted cases:
  - the handshake keeping stdin (R2);
  - `testmap` not skip-listed (W1, W4);
  - dev falling through to release (D2);
  - an unchecked dev suffix (D2);
  - a newest-wins glob (R4, R5).
- **Deviations from plan:**
  - `ENGINE_PATH_UNSAFE` gained the `SCRIPT_DIR` variable name (Change Request 1).
  - The `VERSION` read tolerates unreadable files (Change Request 2).
  - In `platform_detect.sh`, `platform_os` / `platform_arch` alone report the live other field in `PLATFORM_UNSUPPORTED:`, while `platform_asset_suffix` reports the examined pair exactly once.
- **Issues encountered:**
  - `.aitask-scripts/VERSION` moved from 0.36.0 to 0.36.1 on main mid-task. The shim reads it at run time, so nothing changed.
  - shellcheck reports only SC1091 (info: source not followed), the same as every sibling script.
- **Key decisions:**
  - The handshake reads the TEXT `version` line protocol, not `--json`.
  - All shim diagnostics go to stderr, and stdout is exclusively the engine's.
  - A set tier that fails is final (no fall-through).
  - The override has no version check, but must be an absolute path to an executable file.
  - The dev suffix must match `^[0-9a-f]{7,64}$`.
  - `platform_detect.sh` is on no startup chain, so there is no scaffold entry.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - M1.5: install at `"$(aitasks_engine_dir <V>)/ait-testmap"` with mode +x. Name dev builds `<V>-dev+<hex 7..64>`. Self-check with `source aitask_testmap.sh --source-only; rc=0; testmap_resolve_engine || rc=$?`, unsetting `AIT_TESTMAP_BIN` / `AIT_ENGINE` to probe only the release slot. `platform_detect.sh` must be sourced explicitly.
  - Any later `ait` arm whose stdout is line protocol (M5.1 `test)`) must join the update-check skip list. W1, W2 and W4 in `tests/test_testmap_shim.sh` are the reusable test pattern: a seeded fresh cache for the notice, and a fake `curl` on PATH captured by `$( )` for the network branch.
  - The fake-engine helper `mkfake` in `tests/test_testmap_shim.sh` (four-line text `version`, ARG/STDIN echo, `$FAKE_EXIT`) is a reusable model for M5.1's fake engine.
