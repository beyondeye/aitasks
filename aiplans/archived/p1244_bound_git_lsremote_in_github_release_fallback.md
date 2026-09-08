---
Task: t1244_bound_git_lsremote_in_github_release_fallback.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1244 — Bound `git ls-remote` in the GitHub release fallback

## Context

`github_latest_tag_version()` (`.aitask-scripts/lib/github_release.sh:92`) is the
rate-limit-free fallback used when the GitHub REST API is unavailable. Both curl
paths in the same file carry an explicit time bound (`--max-time 10` for the
release lookup, `--max-time 5` for the rate-limit probe), but the `git ls-remote`
fallback has none. On a wedged network — a connection that blackholes instead of
refusing — the call can hang indefinitely, freezing whatever attended command
reached it.

This was found during the t1223_2 plan review: the Python wrapper
`framework_version.resolve_latest_version` had to add `start_new_session=True`
plus a process-group `SIGKILL` precisely because a timed-out helper could leave a
live `git ls-remote` **grandchild** behind. The bash-side callers have no
equivalent bound at all.

**Correction to the task body** (verified while planning): `ait`'s
`check_for_updates` (`ait:124-186`) does *not* reach this helper — it runs its own
inline `curl -sS --max-time 5` in a disowned background subshell and never sources
`lib/github_release.sh`. The genuinely exposed attended callers are:

| caller | path |
|---|---|
| `ait upgrade` | `aitask_upgrade.sh:67` → `github_latest_tag_version` (rate-limit branch) |
| `ait setup` | `aitask_setup.sh:2466` → `github_resolve_latest_version` → `github_latest_tag_version` |
| `install.sh` (`curl \| bash`) | `resolve_latest_version_gittags()` at `install.sh:214` — a deliberate copy of the same helper, with a "keep the two in sync" comment |
| `lib/framework_version.py` | already bounded on its own side (10s + process-group kill); the fix is belt-and-braces there |

A second, related defect surfaced while prototyping: under `set -o pipefail` the
helper's pipeline returns **1** whenever `grep` matches nothing (measured). Today
that only bites on the no-tags path; adding a timeout makes empty output routine,
so `aitask_upgrade.sh:67` and `github_release.sh:114` — both unguarded command
substitutions under `set -euo pipefail` — would start dying silently instead of
reaching their own error messages. Fixing the return status is therefore part of
this change, not a separate cleanup.

## Approach

Add a private, self-contained bounded runner inside `lib/github_release.sh` and
route the fallback through it, so every caller inherits the bound.

**Three constraints shape the implementation:**

1. **No `timeout(1)`.** Both test suites stub `git` as a *shell function*
   (`tests/test_github_release.sh:37`, `tests/test_install_tarball_download.sh:84`),
   and an exec'd `timeout` would bypass the stub and turn those tests into live
   network calls. macOS also ships no `timeout` by default. So the bound is a
   background job plus a polling watchdog — the same shape as
   `aitask_sync.sh:_git_with_timeout` and
   `aitask_remote_drift_check.sh:_git_fetch_with_timeout`.
2. **Output to a temp file, not a pipe.** Killing the direct child leaves a
   `git-remote-https` grandchild holding the write end of a pipe, which keeps the
   reader blocked for the full hang — exactly what t1223_2 measured. A file has no
   such reader.
3. **Kill the whole process tree.** A recursive `pgrep -P` walk reaps the
   transport helper too. Prototyped and confirmed: a stubbed 30-second
   `git ls-remote` returned empty at the 2s bound with **zero** leftover
   descendants.

`lib/github_release.sh` must stay dependency-free — `tests/test_setup_help_flag.sh:43`
and `tests/test_init_data.sh:94` copy it into fixtures standalone — so the runner
is local to the file rather than extracted into a new shared lib.

### 1. `.aitask-scripts/lib/github_release.sh`

- Document the new knob in the file header and add a default near the top:
  `AIT_GIT_LSREMOTE_TIMEOUT` (default `10`, matching the file's `--max-time 10`
  and the framework-wide `NETWORK_TIMEOUT=10`).
- **Normalize the knob before it is used anywhere.** It is externally set, and
  every malformed shape fails badly (all measured during planning):

  | value | unguarded behavior |
  |---|---|
  | `abc` | `$(( SECONDS + t ))` under `set -u` → `abc: unbound variable`, aborting the function *and* the caller's command substitution |
  | `""` | `deadline=0` → instant "timeout": the fallback silently returns empty **forever** |
  | `0`, `-5` | same silent disable |
  | `a[0$(id)]` | arithmetic array-subscript evaluation — command substitution inside `$(( … ))` |

  Guard once, at the top of the runner, and normalize anything unsupported back
  to the documented default rather than failing:

  ```bash
  local timeout_s="${AIT_GIT_LSREMOTE_TIMEOUT:-10}"
  if [[ "$timeout_s" =~ ^[0-9]+$ ]] && (( 10#$timeout_s > 0 )); then
      timeout_s=$(( 10#$timeout_s ))
  else
      timeout_s=10
  fi
  ```

  `10#` is required — `(( 08 > 0 ))` is an "invalid octal" error. The `if`/`else`
  form (not `[[ … ]] && (( … ))`) is required too: a false `&&` list is a
  non-zero statement and trips `set -e`. After this the value is a plain positive
  integer, safe for both the arithmetic and `GIT_HTTP_LOW_SPEED_TIME`.
- Add `_ait_ls_remote_kill_tree()` — recursive `pgrep -P` walk, `kill` each pid,
  all best-effort (`|| true`).
- Add `_github_ls_remote_tags <url>` — the bounded runner. **`$AIT_GIT_LSREMOTE_TIMEOUT`
  is never referenced again after the normalization above; every use below is the
  normalized `timeout_s`** — otherwise the raw malformed value stays on the
  execution path and the validation guarantees nothing:
  - `mktemp "${TMPDIR:-/tmp}/ait_lsremote.XXXXXX"` (portable form; no
    `mktemp --suffix`, per `aidocs/framework/sed_macos_issues.md`);
  - run `git ls-remote --tags --refs "$url" 'v*' >"$tmp" 2>/dev/null &` with
    `GIT_TERMINAL_PROMPT=0`, `GIT_HTTP_LOW_SPEED_LIMIT=1`,
    `GIT_HTTP_LOW_SPEED_TIME="$timeout_s"` so git aborts a stalled transfer
    itself and tears its helper down cleanly, with the watchdog as the hard
    backstop for the phases the low-speed timer does not cover (DNS / TCP
    connect);
  - poll with `sleep 0.2 2>/dev/null || sleep 1` against
    `deadline=$(( SECONDS + timeout_s ))` — using bash's `SECONDS` keeps the
    bound correct whichever sleep granularity the platform accepts;
  - on timeout: tree-kill, `wait`, print nothing; otherwise `cat "$tmp"`;
  - always `rm -f "$tmp"` and `return 0`.
  - Every fallible step guarded (`if`/`then`, `|| true`) so the function is
    `set -euo pipefail`-safe when sourced.
- Rewrite `github_latest_tag_version()` to pipe `_github_ls_remote_tags` through
  the unchanged `sed`/`grep`/`sort -t. -k…n`/`tail -1` filter chain, appending
  `|| true` to the pipeline so an empty result is exit **0**, not a `pipefail` 1.

### 2. `install.sh` — keep the documented mirror honest

`resolve_latest_version_gittags()` carries an explicit "This mirrors
`github_latest_tag_version()` … keep the two in sync" comment and has the identical
unbounded hang on the highest-blast-radius path (`curl | bash`). Port the same
bounded runner, knob normalization and tree-kill helper into install.sh (it cannot
source the lib — the lib is not on disk until the tarball is extracted) and update
the sync comment to say the bound is part of what is mirrored. Its call site
already has `|| true` (`install.sh:280`), so no status change is needed there.

**The install.sh helpers MUST carry distinct names** — `_install_ls_remote_tags`
and `_install_kill_process_tree`, not the library's `_github_*` names.
`tests/test_install_tarball_download.sh` sources install.sh (line 26) and *then*
`lib/github_release.sh` (line 28); bash resolves function calls dynamically and a
later definition wins (verified). With shared names the library's copy would
silently replace install.sh's, so `resolve_latest_version_gittags()` would exercise
the *library* runner and the new installer test below would pass on a broken
installer. Distinct names make that impossible regardless of source order.

### 3. `tests/test_github_release.sh` — new coverage

Add tests alongside the existing ones (same in-file `git()` stub pattern, `PASS`/
`FAIL` counters — no subshell bodies, so no `assert_counters_init` needed).

**The hanging stub must reproduce the real process shape**, because the defect
being fixed is a surviving *descendant*, not a surviving direct child. A stub
that merely calls `sleep 30` inline only proves the direct child was killed. So
the stub spawns a nested shell that has its own child, records **both** PIDs to a
file, and the test asserts each exact PID is gone afterwards:

**`bash -c 'sleep 30'` will not work as the fixture** — bash exec-optimizes a sole
simple command, so the process *becomes* `sleep` with no children (verified:
`comm=sleep`, `pgrep -P` empty). The fixture must force a real shell parent, e.g.
`bash -c 'sleep 30 & wait'` (verified: `comm=bash` with one child):

```bash
git() {
    if [[ "${1:-}" == "ls-remote" ]]; then
        bash -c 'sleep 30 & wait' &     # nested shell (depth 2 from the watchdog)
        local nested=$! gc="" i=0       # its own `sleep` is depth 3
        while [[ -z "$gc" && $i -lt 25 ]]; do
            gc="$(pgrep -P "$nested" 2>/dev/null | head -1)"
            [[ -z "$gc" ]] && sleep 0.1
            i=$(( i + 1 ))
        done
        printf '%s\n%s\n' "$nested" "$gc" > "$STUB_PIDS"
        wait
        return 0
    fi
    command git "$@"
}
```

The test asserts a non-empty `<grandchild>` was actually recorded before checking
cleanup — an empty one means the fixture stopped producing the nested shape and
the cleanup assertion has become vacuous.

Tests to add:

- **timeout**: hanging stub, `AIT_GIT_LSREMOTE_TIMEOUT=1` → empty output, exit 0,
  elapsed wall time `<= 5s`.
- **recursive descendant cleanup**: after that call, assert `kill -0 <nested>`
  **and** `kill -0 <grandchild>` both fail — exact PIDs, not a `pgrep -f` name
  match. This is the assertion that actually pins `pgrep -P` recursion; a
  depth-1-only kill leaves the grandchild orphaned and alive.
- **malformed knob**: `AIT_GIT_LSREMOTE_TIMEOUT=abc` (and one of `""` / `0`) with
  the *instant* stub → still returns `0.10.0`, exit 0. Without the normalization
  the first aborts on `unbound variable` and the others return empty.
- **empty result is exit 0**: `git` stub returns nothing → `rc` is 0 (the
  `pipefail` regression guard).
- Existing Test 5 / Test 6 (numeric sort, resolver fallback) must still pass
  unchanged — they are the proof the happy path is untouched.

### 4. `tests/test_install_tarball_download.sh` — test install.sh's copy directly

`assert_gittag_resolver_parity` compares only *parsed output* from an instant
stub, so any divergence in install.sh's copied process-management code leaves the
`curl | bash` installer hanging while every test above still passes. The copy
therefore needs its own behavioral test, not parity alone.

Add a test that drives `resolve_latest_version_gittags()` **directly** with the
same hanging/nested stub shape and `AIT_GIT_LSREMOTE_TIMEOUT=1`, asserting:
bounded elapsed time (`<= 5s`), empty output, exit status **0** (captured at the
function call — install.sh's own call site masks it with `|| true` at
`install.sh:280`), and both recorded descendant PIDs gone.

Also assert `declare -F _install_ls_remote_tags` succeeds, pinning the distinct-name
isolation above: if the installer's runner is ever renamed back to a library name,
this test fails loudly instead of silently exercising the library's copy.

The existing parity assertions stay and must remain green.

## Files

- `.aitask-scripts/lib/github_release.sh` — knob normalization + bounded runner + rewritten fallback (primary)
- `install.sh` — mirrored bound in `resolve_latest_version_gittags()`
- `tests/test_github_release.sh` — timeout / descendant-cleanup / malformed-knob / exit-status tests
- `tests/test_install_tarball_download.sh` — direct bounded-hang test for install.sh's copy

## Verification

```bash
shellcheck .aitask-scripts/lib/github_release.sh install.sh
bash tests/test_github_release.sh
bash tests/test_install_tarball_download.sh
bash tests/test_setup_help_flag.sh     # copies the lib into a fixture standalone
bash tests/test_init_data.sh           # same
```

End-to-end, against the real network:

```bash
# happy path unchanged — prints the current release version
bash -c 'source .aitask-scripts/lib/github_release.sh && github_latest_tag_version beyondeye/aitasks'

# hard bound observed against a REAL hang. Note the internal helper is called
# directly with a full URL: github_latest_tag_version prefixes
# `https://github.com/`, so passing a blackhole address as the *repo* argument
# only produces a fast github.com 404 and proves nothing.
time bash -c 'set -euo pipefail; source .aitask-scripts/lib/github_release.sh
  out="$(AIT_GIT_LSREMOTE_TIMEOUT=3 _github_ls_remote_tags https://10.255.255.1/x.git)"
  echo "out=[$out] rc=$?"'
```

## Implementation notes (as landed)

Implemented as planned; no deviations from the approved approach.

Measured results:

- **Real-hang bound.** `git ls-remote https://10.255.255.1/x.git` alone runs past
  12s (verified with an external watchdog). Through the new runner at
  `AIT_GIT_LSREMOTE_TIMEOUT=3` it returns empty, exit 0, in ~3s, with **zero**
  leftover processes for that host.
- **Falsifiability controls.** Both new assertions were checked against pre-fix
  copies of the code:
  - replacing `_github_kill_process_tree "$pid"` with a plain `kill "$pid"`
    leaves **both** the nested shell and its grandchild `alive` — the recursive
    walk is what the test pins;
  - removing the knob normalization makes `AIT_GIT_LSREMOTE_TIMEOUT=abc` and
    `=0` return empty instead of the version;
  - the pre-t1244 installer resolver takes the full 8s against a hanging stub
    (fails the `<= 5s` bound) and has no `_install_ls_remote_tags`.
  Note `AIT_GIT_LSREMOTE_TIMEOUT=""` is *not* discriminating on its own — the
  `${…:-default}` expansion already covers empty. It stays as a regression guard
  in case that expansion is ever changed to `${…-default}`.
- **Tests 10 and 11 run under the caller's shell, not the test file's** (review
  round 2). `tests/test_github_release.sh` executes `set +euo pipefail` near its
  top, which silently defeated both assertions: without `pipefail` the pipeline's
  status is `tail`'s 0, so the trailing `|| true` was never exercised and Test 11
  passed with *or* without the fix; without `set -u` the malformed-knob abort
  cannot happen either. Both now wrap the call in a `set -euo pipefail` subshell —
  the real callers (`aitask_upgrade.sh`, `aitask_setup.sh`) all run with those
  settings — and the file's own settings are left untouched. Re-verified against
  pre-fix copies: dropping `|| true` makes Test 11 return `rc=1` (FAILS), and
  dropping the normalization makes Test 10's `abc` case return empty (FAILS).
- **The descendant fixture is deterministic, not a race** (review round 3). The
  first version had the *parent* poll `pgrep -P` for the grandchild, which made
  the fixture a race it had to win against the watchdog — reported failing as
  "fixture actually produced a grandchild = no" (not reproducible here: 6 clean
  runs, plus 3 more at load average 9.2 — but a test that must win a race is
  wrong whether or not this machine loses it). The nested shell now records its
  own pid (`$$`) and its child's (`$!`) itself, in one `printf` microseconds
  after the fork; nothing polls or searches, and the stub timeout moved 1s → 3s
  for headroom (the elapsed assertion only has to separate "bounded" from the
  30s stub hang, so its bound moved 5s → 8s). Re-verified: 12/12 clean runs
  (8 unloaded, 4 at load average ~9.5) plus the installer test under load, and
  the depth-1-only control still leaves **both** processes `alive` → Test 9
  FAILS, so the assertion still pins the recursive walk.
- **Cleanup no longer depends on `pgrep`** (review round 4, and the real
  defect). A reviewer's run reported both descendants still alive after the
  cleanup. Root cause, reproduced by removing `pgrep` from `PATH`: the walk was
  built on `pgrep -P` alone, and on a system without procps (minimal containers
  ship none) that degrades silently to a depth-1 kill — leaving exactly the
  descendants this task exists to reap. **The process group is now the primary
  mechanism**, and it needs no external binary: the runner enables job control
  for the launch only (`set -m`, restored immediately, and only when the shell
  did not already have it), which makes the background job its own group leader,
  and cleanup signals the group with `kill -- "-$pid"`. The `pgrep` walk stays as
  a secondary fallback for a shell that could not give the job its own group.
  This is safe by construction: if the job never became a group leader, no group
  carries that id and the signal is refused with ESRCH — it can never reach the
  calling shell's own group, whose id is that shell's pid.
  Mirrored in `install.sh`. New **Test 9b** in both suites shadows `pgrep` with a
  failing shell function and asserts both recorded PIDs are gone; the pgrep-only
  control leaves both `alive` → Test 9b FAILS, so it pins the repair rather than
  the environment. Verified with `pgrep` both present and absent from `PATH`.
  `set -m` leaks no job-control notices to stderr (checked: empty).
- **Strict-mode knob sweep.** Under `set -euo pipefail`, `abc`, `""`, `0`, `-5`,
  `a[0$(id)]` and `08` all normalize to the 10s default and still resolve the
  live version — no abort, no arithmetic evaluation of the value, no octal error.
- **Suites green.** `test_github_release.sh` 30/30, `test_install_tarball_download.sh`
  35/35, `test_setup_help_flag.sh` 23/23, `test_init_data.sh` 140/140.
  `shellcheck` clean on `lib/github_release.sh`; the three findings it reports on
  `install.sh` (lines 678, 828, 1434) are pre-existing and untouched by this
  change.

## Risk

### Code-health risk: medium
- The watchdog + tree-kill is process-management code whose failure mode is
  silent: a bug makes version resolution return empty and both `ait upgrade` and
  `ait setup` degrade quietly rather than erroring. · severity: medium · → mitigation: covered by the timeout / leak / exit-status tests in plan step 3
- `install.sh` is the highest-blast-radius file in the repo, and the change adds
  ~25 lines of process handling to a `curl | bash` path that output-parity tests
  cannot see through. · severity: medium · → mitigation: covered by plan step 4 — a direct bounded-hang test on `resolve_latest_version_gittags()`, not parity alone
- Adds a third near-copy of the portable-timeout pattern (`aitask_sync.sh`,
  `aitask_remote_drift_check.sh`, now here). Extracting a shared helper is
  deliberately **not** done: the lib must stay standalone for the fixture
  copies. · severity: low · → mitigation: none needed — recorded in the file comment

### Goal-achievement risk: low
- None identified. The defect, the callers, the kill semantics and the `pipefail`
  side effect were each verified empirically during planning.

## Final Implementation Notes

- **Actual work done:** `git ls-remote` in the release fallback is now hard-bounded.
  `.aitask-scripts/lib/github_release.sh` gained `_github_ls_remote_tags` (a
  background job + polling watchdog writing to a temp file, launched under job
  control so it owns a process group), `_github_kill_process_tree` /
  `_github_kill_descendants` (process-group kill, with a `pgrep -P` walk as
  fallback), normalization of the new `AIT_GIT_LSREMOTE_TIMEOUT` knob, and a
  `|| true` on the resolver pipeline. `install.sh`'s documented mirror
  `resolve_latest_version_gittags()` got the same treatment under distinct
  helper names. Tests: 5 new cases in `tests/test_github_release.sh` and 1 new
  case (7 assertions) in `tests/test_install_tarball_download.sh`.
- **Deviations from plan:** none in approach. Two things were added during
  review that the approved plan did not anticipate — see "Issues encountered".
- **Issues encountered:**
  - *The cleanup depended on an external binary.* The first implementation walked
    the process tree with `pgrep -P` alone. A reviewer's run reported both
    descendants still alive; reproduced here by removing `pgrep` from `PATH`. On
    a system without procps the walk degrades silently to a depth-1 kill and
    leaks exactly the descendants this task exists to reap. Fixed by making the
    **process group** the primary mechanism (`set -m` for the launch only,
    restored immediately; `kill -- "-$pid"` for cleanup), keeping the `pgrep`
    walk as a secondary fallback. Pinned by Test 9b in both suites, which
    shadows `pgrep` with a failing shell function.
  - *Two tests were vacuous.* `tests/test_github_release.sh` runs
    `set +euo pipefail`, which defeated both the `pipefail` guard (the pipeline's
    status is `tail`'s 0, so the trailing `|| true` was never exercised) and the
    malformed-knob guard (the `set -u` abort cannot happen). Both now run the
    call inside a `set -euo pipefail` subshell, matching the real callers.
  - *The descendant fixture was a race.* Its first version had the parent poll
    `pgrep -P` for a grandchild that had to appear before the watchdog fired.
    The nested shell now records its own pid and its child's itself, in one
    `printf`.
  - *A misleading early measurement.* `github_latest_tag_version 10.255.255.1/x`
    does not test a blackholed host — the helper prefixes `https://github.com/`,
    so it hits a fast 404. The real bound is measured by calling
    `_github_ls_remote_tags` with a full URL; `git` alone runs past 12s there.
- **Key decisions:**
  - **No `timeout(1)`.** Both suites stub `git` as a shell *function*, which an
    exec'd `timeout` would bypass into a live network call; macOS also ships
    none. The watchdog shape matches `aitask_sync.sh:_git_with_timeout`.
  - **Temp file, not a pipe.** A surviving transport grandchild holding a pipe's
    write end blocks the reader for the full hang (t1223_2). A file cannot.
  - **Distinct helper names in `install.sh`.** `tests/test_install_tarball_download.sh`
    sources install.sh and *then* the library; bash resolves calls dynamically
    and a later definition wins, so shared names would make the installer's test
    silently exercise the library's runner.
  - **No shared extraction.** This is a third near-copy of the portable-timeout
    pattern, accepted deliberately: `lib/github_release.sh` must stay
    dependency-free because `test_setup_help_flag.sh` and `test_init_data.sh`
    copy it into fixtures standalone, and `install.sh` cannot source anything.
  - **Group kill is safe unguarded.** If the job never became a group leader, no
    group carries that id and the signal is refused with ESRCH; it can never
    reach the calling shell's group, whose id is that shell's own pid.
- **Upstream defects identified:** None
