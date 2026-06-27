---
Task: t1075_install_sh_direct_tarball_download_no_api.md
Worktree: (none — profile 'fast', current branch)
Branch: (current)
Base branch: main
---

# Plan: install.sh direct tarball download (no REST API) — t1075

## Context

`ait upgrade <VERSION>` fails with *"Could not find release tarball"* whenever the
unauthenticated GitHub REST API quota (60 req/hr/IP) is exhausted. The tarball
exists — the API just returned a rate-limit body instead of release JSON, so
`install.sh`'s `download_tarball()` `grep '"browser_download_url"'` found nothing.

This is the **download** half of the failure class that t1069 already fixed for
version **resolution** (it hardened `resolve_version` in `aitask_upgrade.sh` with a
`git ls-remote` fallback + token support via `lib/github_release.sh`). The tarball
download in `install.sh` was never touched. Two concrete defects:

1. **Rate-limit fragile** — `download_tarball()` hits `api.github.com/.../releases/latest`
   purely to discover a URL that is actually deterministic, with no token and no
   fallback. (The reported failure.)
2. **Requested version ignored** — `aitask_upgrade.sh` resolves the target version
   then runs `install.sh --force` *without passing it through*, so `download_tarball`
   always fetches `releases/latest`. `ait upgrade <older>` silently installs *latest*.
   Masked today only because requested usually == latest.

**Key fact (verified in the task + `release.yml:87`):** the release asset is always
`aitasks-v<VERSION>.tar.gz`, downloadable from the rate-limit-free CDN:
`https://github.com/<repo>/releases/download/v<VERSION>/aitasks-v<VERSION>.tar.gz`
(returns 302→200, zero REST calls). `release.yml` uploads it via
`softprops/action-gh-release`, so the URL is guaranteed.

## Approach

Restructure `install.sh`'s `download_tarball()` to a **3-tier strategy** and thread
the resolved version from `aitask_upgrade.sh`:

```
LOCAL_TARBALL set?  → copy it (UNCHANGED)
version known?      → deterministic CDN URL, NO api.github.com  ← happy path
no version?         → resolve latest via `git ls-remote --tags` (rate-limit-free), then CDN URL
CDN download fails? → REST API last resort (honors GH_TOKEN), EXCEPT when an
                      explicit version was requested → die (never silently install latest)
```

### Files to modify

- **`install.sh`** — the fix site (`download_tarball()` ~line 179, arg-parsing, usage).
- **`.aitask-scripts/aitask_upgrade.sh`** — `main()` passes the resolved version (one line).
- **`tests/test_install_tarball_download.sh`** — NEW unit test (sources `install.sh --source-only`).

### Design decisions (with rationale — these are blast-radius-sensitive)

**(a) Version handoff = `AIT_TARGET_VERSION` env var, NOT a `--version` flag, on the
upgrade path.** `aitask_upgrade.sh` downloads the *target* version's `install.sh`
(`raw.githubusercontent.com/$REPO/v<V>/install.sh`) and runs *that*. If we passed a
`--version` flag and the target predates this fix, the old installer dies on an
unknown option — a regression. An unknown **env var** is silently ignored by old
installers (they fall back to their existing behaviour), so the env channel is
strictly never-worse. We ALSO add a `--version <V>` flag to `install.sh` for explicit
standalone use (`bash install.sh --version 0.26.1`); the flag takes precedence over
the env var. So both surfaces exist; `aitask_upgrade.sh` uses the safe one.

**(b) Inlined git-tag resolver (duplicates `github_latest_tag_version`).** `install.sh`
runs standalone via `curl | bash` and **cannot** source `lib/github_release.sh` (the
lib isn't on disk yet — we're installing it). This matches the *established* install.sh
convention: `commit_installed_files()` already duplicates a path list from
`aitask_setup.sh` and `commit_installed_data_files()` inlines `_ait_detect_data_worktree`,
both with "Mirrors X — keep in sync" comments. The new `resolve_latest_version_gittags()`
gets the same explicit sync-guard comment pointing at the canonical lib function.

**(c) Explicit version + CDN failure ⇒ `die`, never fall back to `releases/latest`.**
Falling back to latest when a *specific* version was asked for would re-introduce
defect #2. Only the "resolve latest" path (no explicit version) is allowed to fall
through to the REST API.

**(d) `GH_TOKEN`/`GITHUB_TOKEN` honored on the remaining REST call** (the last-resort
fallback only), mirroring the `Authorization: Bearer` pattern in `github_release.sh`.

### `install.sh` changes (concrete)

1. **New global + arg parse.** Add `TARGET_VERSION=""` near the other globals; add a
   `--version` case to the arg loop:
   ```sh
   --version)
       [[ $# -ge 2 ]] || die "--version requires a version argument"
       TARGET_VERSION="$2"
       shift 2
       ;;
   ```
   Add a line to `usage()` documenting `--version VERSION` and an example.

2. **Three small helpers above `download_tarball()`** (functions, so order is only
   for locality):

   - `download_url <url> <dest>` — factors the curl/wget branch. Uses `curl -fsSL
     --max-time 120` (the **`-f`** is new and load-bearing: without it curl returns 0
     on a 404 and writes the error page to `dest`, defeating the fallback; wget
     already exits nonzero on HTTP errors). `-L` follows the CDN's 302.
   - `resolve_latest_version_gittags` — mirrors `github_latest_tag_version` (sync
     comment); `command -v git || return 0` so a git-less host degrades to the REST
     path. Portable: `sed -E`, `grep -E`, numeric `sort -t. -k1,1n -k2,2n -k3,3n`
     (no GNU-isms — see `aidocs/framework/sed_macos_issues.md`).
   - `github_api_tarball_url` — the OLD REST lookup, extracted, now adding the
     `Authorization: Bearer $tok` header (curl `-H` / wget `--header=`) when a token
     is set. Uses `${auth[@]+"${auth[@]}"}` for `set -u`-safe empty-array expansion.

3. **Rewrite `download_tarball()`** to the 3-tier strategy above. Resolve
   `requested_version="${TARGET_VERSION:-${AIT_TARGET_VERSION:-}}"`, strip a leading
   `v`, validate `^[0-9]+\.[0-9]+(\.[0-9]+)?$` (else `die`). Build
   `https://github.com/$REPO/releases/download/v${version}/aitasks-v${version}.tar.gz`
   and `download_url` it. On success return; on failure either `die` (explicit
   version) or `warn` + fall to `github_api_tarball_url` (resolved-latest path).

### `aitask_upgrade.sh` change (concrete)

In `main()`, the installer invocation (currently line 146) becomes:
```sh
# Pass the resolved version via env (NOT a --version flag): the downloaded
# installer is the *target* version's, and a pre-t1075 installer silently
# ignores an unknown env var but would die on an unknown flag.
AIT_TARGET_VERSION="$target_version" bash "$tmpdir/install.sh" --force --dir "$AIT_DIR"
```

### Out of scope (explicit — AC does not require, all degrade gracefully)

The task's own audit table marks these "fold in only if cheap"; they are NOT the
reported failure and already fail soft. Scoping them OUT (no silent AC deviation —
the AC covers only the upgrade/download path):
- `ait:164` `check_for_updates` — daily-cached background notice, fails silently.
- `aitask_setup.sh:226/290/324` (`bkt`) and `:2779` (`lazygit`) — 3rd-party, warn+skip.

I'll offer these as an optional standalone follow-up task at the end (Step 8c), not
implement them here.

## Testing / Verification

**New unit test `tests/test_install_tarball_download.sh`** (pattern: `test_github_release.sh`
stubs + `test_install_merge.sh`'s `source install.sh --source-only`). Sources the
installer, then defines `curl`/`wget`/`git` stubs that log invocations and return
canned data. Cases (mapped to ACs):
1. **Explicit version (`AIT_TARGET_VERSION`/`TARGET_VERSION`)** → asserts the dest URL
   is `.../releases/download/v0.26.1/aitasks-v0.26.1.tar.gz` and **no** `api.github.com`
   call was logged. (AC1, AC2)
2. **No version** → git stub returns tags `v0.9.0/v0.10.0/v0.2.1`; asserts CDN URL for
   `v0.10.0` (numeric-sorted) and **no** `api.github.com` call. (AC3)
3. **Explicit version + CDN download fails** (curl stub returns nonzero) → asserts
   `download_tarball` exits nonzero (`die`) and **never** queries `releases/latest`. (AC2 hardening)
4. **REST fallback honors token** → no version + git stub empty + `GH_TOKEN` set →
   asserts the logged API call carries `Authorization: Bearer`. (AC5)
5. **`--local-tarball`** → `LOCAL_TARBALL` set to a temp file → asserts it's copied to
   dest with zero network calls. (AC4)

**Regression:** `bash tests/test_t167_integration.sh`, `bash tests/test_t644_branch_mode_upgrade.sh`
(both use `--local-tarball`, the unchanged early-return), `bash tests/test_github_release.sh`,
`bash tests/test_install_merge.sh`.

**Lint:** `shellcheck install.sh .aitask-scripts/aitask_upgrade.sh tests/test_install_tarball_download.sh`.

**Live e2e (AC1's "verifiable by" clause — manual, needs network/release):** block
`api.github.com` (e.g. `/etc/hosts` → `127.0.0.1 api.github.com`) and run
`ait upgrade <VERSION>`; confirm it still succeeds. This is a good candidate for a
standalone manual-verification follow-up (offered at Step 8c) since it can't run in CI.

Per `task-workflow` Step 9, post-implementation runs `./ait gates run 1075` (no gates
declared → legacy `verify_build` from `project_config.yaml`), then archival.

## Risk

### Code-health risk: low
- Inlined duplication of `github_latest_tag_version` in `install.sh` (cannot source the
  lib on the curl|bash path). · severity: low · → mitigation: drift_guard_gittag_resolver
  (also mitigated in-design by a "Mirrors … keep in sync" comment, matching the existing
  install.sh duplication convention)
- Adding `-f` to the curl download changes 404 handling (now fails instead of writing the
  error page) — intended, but a behaviour change on the REST-fallback download too. · severity: low · → mitigation: none (intended behaviour, covered by test case 3)

### Goal-achievement risk: low
- The deterministic-CDN happy path and token-aware REST fallback are unit-tested, but the
  full live `ait upgrade` e2e (block api.github.com → success) can't run in CI. · severity: medium · → mitigation: manual_verify_upgrade_no_api

### Planned mitigations
- timing: after | name: drift_guard_gittag_resolver | type: test | priority: low | effort: low | addresses: code-health sync-drift (inlined resolver vs lib) | desc: add a test that feeds the same stubbed git output to install.sh's resolve_latest_version_gittags and lib/github_release.sh's github_latest_tag_version and asserts identical output, guarding against drift between the two
- timing: after | name: manual_verify_upgrade_no_api | type: manual_verification | priority: medium | effort: low | addresses: goal-achievement e2e-gap (no live upgrade test in CI) | desc: block api.github.com (e.g. /etc/hosts) and confirm ait upgrade <VERSION> still downloads and installs from the CDN with zero REST calls
