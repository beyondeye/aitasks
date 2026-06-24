---
Task: t1069_harden_ait_upgrade_against_github_rate_limit.md
Worktree: (none — profile 'fast', current branch)
Branch: (current)
Base branch: main
---

# Harden `ait upgrade` version resolution against GitHub API rate limiting

## Context

`ait upgrade` fails with a misleading error when the GitHub API is rate-limited:

```
[ait] Error: Could not determine latest version. No releases found at https://github.com/beyondeye/aitasks/releases
```

The release exists and is healthy — the message is wrong. Root cause: `resolve_version()`
in `.aitask-scripts/aitask_upgrade.sh` queries the **unauthenticated** GitHub API
(`/releases/latest`, capped at **60 req/hour/IP**). When that quota is exhausted, GitHub
returns **HTTP 403** with a *non-empty* body `{"message":"API rate limit exceeded ..."}`.
The script's only guard is `[[ -z "$api_response" ]]` (catches empty/unreachable only), so
the rate-limit body slips through → `tag_name` not found → empty version → the misleading
"No releases found" die. Symptom is intermittent because the quota resets hourly and is
shared across all sibling repos on one public IP.

### Findings that corrected the task's assumptions (scope-honesty)

Investigation found **three** callers of `/releases/latest`, not one:

1. **`.aitask-scripts/aitask_upgrade.sh:46` `resolve_version()`** — the actual bug. No
   error classification, no fallback, misleading message.
2. **`.aitask-scripts/aitask_setup.sh:1620` `check_latest_version()`** — runs only at the
   *end of `ait setup`/`ait upgrade`* (called once at `:3182`), silently returns on failure.
   Low-frequency, but shares the duplicated parse.
3. **`ait:116-179` `check_for_updates()`** (top-level dispatcher) — the real per-command
   "update available" check. It **already** caches with a 24h TTL (`~/.aitask/update_check`),
   fetches in a backgrounded subshell, **keeps the timestamp fresh on a parse-miss so it
   does not retry**, and is **skipped for `upgrade`/`setup`**. It does *not* spam the API.

**Therefore AC4's premise is wrong** and will be corrected in the task file (see "AC update"
below): the background check does **not** "burn the quota on every ait run", and the cache
is owned by the dispatcher — `aitask_upgrade.sh:130` only *clears* it. The dispatcher is
already well-behaved; the one real defect it carries is a latent macOS bug: its parse at
`ait:167` uses `sed 's/...v\?.../'` — the `\?` BRE quantifier is **GNU-only** (documented
BSD/macOS footgun in `aidocs/framework/sed_macos_issues.md`), while the other two callers
correctly use portable `sed -E ...v?...`.

**Scope decision (user-approved): Focused.** New sourceable helper used by callers #1 and
#2; caller #3 (`ait`) gets only the one-line portability sed fix in place — its cache /
background logic is left untouched to avoid coupling `./ait` startup to a new lib (which
would force a `tests/lib/test_scaffold.sh` source-on-startup baseline change). Residual,
deliberate: the dispatcher keeps its own inline parse (standalone by design).

## Approach

Extract the API call + classification + fallback into one small **sourceable, testable**
library (`testability-first decomposition`), wire the two `.aitask-scripts` callers to it,
fix the dispatcher's sed in place, and add a unit test for the pure helper.

### 1. New helper: `.aitask-scripts/lib/github_release.sh`

A pure library (no `main`, sourced like the other `lib/*.sh`). Two public functions + one
combined resolver returning **rich, scope-honest** results:

- `github_latest_release_version <repo>` — the API path.
  - Build the request honoring auth: if `GH_TOKEN` or `GITHUB_TOKEN` is set, add
    `-H "Authorization: Bearer $tok"` (raises the limit to 5000/hr). Never *require* a token.
  - Capture body **and** status in one call:
    ```bash
    resp="$(curl -sS --max-time 10 $auth -w '\n%{http_code}' "https://api.github.com/repos/$repo/releases/latest" 2>/dev/null)" || true
    http="${resp##*$'\n'}"; body="${resp%$'\n'*}"
    ```
  - Parse `tag_name` with **portable** `sed -E 's/.*"tag_name": *"v?([^"]*)".*/\1/'`.
  - Classify (print token to stderr, version to stdout):
    - non-empty version parsed → stdout=version, return 0.
    - `http == 403` and body matches `rate limit` (or `X-RateLimit-Remaining: 0`) →
      return 2 (`RATELIMIT`). Best-effort reset time: query the **exempt**
      `https://api.github.com/rate_limit` endpoint (does not count against core limit),
      parse `.resources.core.reset`, and surface "try again in ~N min" computed as
      `(reset - now + 59)/60` (avoids `date` format portability).
    - `http == 404` or empty release object → return 3 (`NOTFOUND`).
    - empty `resp` / `http == 000` → return 4 (`NETWORK`).
- `github_latest_tag_version <repo>` — **rate-limit-free** git fallback (git protocol is not
  subject to the 60/hr API cap):
  ```bash
  git ls-remote --tags --refs "https://github.com/$repo" 'v*' 2>/dev/null \
    | sed -E 's#.*refs/tags/v?##' \
    | sort -t. -k1,1n -k2,2n -k3,3n | tail -1
  ```
  (semver-aware numeric sort — avoids GNU-only `sort -V`.)
- `github_resolve_latest_version <repo>` — combined: try the API; on `RATELIMIT`/`NETWORK`
  fall back to `github_latest_tag_version`. Returns the version and, on stderr, which path
  was used + the reason (so consumers can print an accurate, specific message).

Portability: ERE sed only, numeric `sort` (no `-V`), `(reset-now)/60` instead of `date`
formatting. Sweep done per the "footguns travel in families" rule.

### 2. `.aitask-scripts/aitask_upgrade.sh` — rewrite `resolve_version()` "latest" branch

- Add near the top (after `SCRIPT_DIR`): `source "$SCRIPT_DIR/lib/github_release.sh"`.
- Replace the inline curl/grep/sed + the `[[ -z ]]` guard with a call to
  `github_latest_release_version "$REPO"`, capturing stdout + exit code, and branch:
  - success → `echo "$version"`.
  - `RATELIMIT` → `warn` with an **accurate** message ("GitHub API rate limit exceeded
    (60/hr unauthenticated)[; try again in ~N min]; set GH_TOKEN to raise the limit"),
    then attempt `github_latest_tag_version "$REPO"`. If it yields a version →
    `info "Resolved latest version via git tags (REST API was rate-limited): v$version"`
    and `echo` it. Else `die` with the rate-limit message.
  - `NOTFOUND` → `die "No published releases found at https://github.com/$REPO/releases"`
    (now genuinely accurate).
  - `NETWORK` → `die "Could not reach GitHub API. Check your network connection."`
- The explicit-version branch (semver validation) is unchanged.

### 3. `.aitask-scripts/aitask_setup.sh` — route `check_latest_version()` through the helper

- Source the helper alongside the existing lib sources.
- Replace the inline parse (`:1620-1621`) with `github_resolve_latest_version "$REPO"`
  (or the release-only variant), preserving the existing silent-degrade contract (return
  with no message on any non-success). No behavior change on success.
- Leave the unrelated `bkt`/`glab`/`lazygit` third-party `jq` parses untouched.

### 4. `ait` (dispatcher) — one-line portability fix only

- At `ait:167`, change the GNU-only BRE parse to the portable ERE form used elsewhere:
  ```bash
  | sed -E 's/.*"tag_name": *"v?([^"]*)".*/\1/')" || true
  ```
- **Do not** touch the cache/background/skip logic (already correct). Do **not** source the
  new helper here (Focused scope; avoids source-on-startup coupling).

### 5. AC update to the task file (no silent AC deviation)

Update `aitasks/t1069_harden_ait_upgrade_against_github_rate_limit.md` (commit via
`./ait git`): rewrite **AC4** to reflect that the dispatcher already caches (24h TTL) and
degrades gracefully — the only dispatcher change is the portability sed fix; and soften the
root-cause narrative (quota exhaustion comes from repeated *uncached* `ait upgrade`
invocations across repos, not a per-command spam). Add the macOS `\?` sed defect note.

### 6. Test: `tests/test_github_release.sh`

Self-contained (mirrors `tests/test_version_checks.sh`): source the helper, override `curl`
and `git` as shell functions returning fixtures, source `tests/lib/asserts.sh`, and assert:
- valid release JSON → returns parsed version (no leading `v`), exit 0.
- 403 + `{"message":"API rate limit exceeded ..."}` → exit 2 / `RATELIMIT`.
- empty response → exit 4 / `NETWORK`.
- 404 → exit 3 / `NOTFOUND`.
- `github_latest_tag_version` over a fake `git ls-remote` listing → highest version by
  numeric sort (e.g. `v0.9.0` and `v0.10.0` → `0.10.0`, guarding lexical-sort regressions).
- `github_resolve_latest_version` falls back to tags when the API stub returns 403.

### Install / seed

No seed duplication: there is **no** `seed/` copy of `aitask_upgrade.sh`, `aitask_setup.sh`,
or `ait`. `install.sh` copies `.aitask-scripts/` wholesale and `ait` from the repo root, so
the new `lib/github_release.sh` ships through the normal copy. (Verify during impl that the
install copy includes `.aitask-scripts/lib/`.)

## Files

- `.aitask-scripts/lib/github_release.sh` — **new** sourceable helper.
- `.aitask-scripts/aitask_upgrade.sh` — `resolve_version()` rewrite + source line.
- `.aitask-scripts/aitask_setup.sh` — `check_latest_version()` rewrite + source line.
- `ait` — one-line ERE sed portability fix at `:167`.
- `aitasks/t1069_*.md` — AC4 correction (via `./ait git`).
- `tests/test_github_release.sh` — **new** unit test.

## Verification

- `bash tests/test_github_release.sh` → ALL TESTS PASSED.
- `shellcheck .aitask-scripts/lib/github_release.sh .aitask-scripts/aitask_upgrade.sh` → clean.
- Live happy path: `ait upgrade` (or `ait upgrade latest`) from this repo resolves
  `0.26.0`/"already up to date" with no error.
- Simulated rate-limit: temporarily force the API path to 403 (env stub / unset network)
  and confirm `ait upgrade` prints the accurate rate-limit message **and** still resolves
  the version via the git-tag fallback.
- `GH_TOKEN=<token> ait upgrade` exercises the authenticated path without error.
- `bash tests/test_version_checks.sh` still passes (setup.sh sourced clean).

## Risk

### Code-health risk: medium
- Touches two load-bearing paths — the `ait upgrade` resolution path and the per-command
  `ait` dispatcher (runs on every invocation). A defect in `resolve_version` could break
  upgrades for all users. · severity: medium · → mitigation: unit test for the pure helper +
  manual happy-path + simulated-rate-limit verification before merge.
- New shared lib adds one more `lib/*.sh`, but only sourced by two scripts (not `./ait`
  startup), so no test-scaffold baseline coupling. · severity: low · → mitigation: TBD.

### Goal-achievement risk: low
- Approach directly delivers the goal; the git-tag fallback is a proven, rate-limit-free
  path and only *adds* a recovery route. Main assumption — curl `-w '%{http_code}'` status
  capture — holds across supported curl versions. · severity: low · → mitigation: None identified.

No before/after risk-mitigation follow-up tasks proposed (risks are bounded and covered by
the in-task test + verification).
