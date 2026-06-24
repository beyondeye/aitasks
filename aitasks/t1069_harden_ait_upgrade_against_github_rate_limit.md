---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [framework]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-24 23:35
updated_at: 2026-06-25 00:43
---

## Problem

`ait upgrade` fails with a misleading error when the GitHub API is rate-limited:

```
[ait] Checking latest version...
[ait] Error: Could not determine latest version. No releases found at https://github.com/beyondeye/aitasks/releases
```

This was hit while running `ait upgrade` across the `aitasks_go` and `aitasks_mobile` sibling repos shortly after publishing v0.26.0. The release **exists and is healthy** — published, not draft, not prerelease, with a clean `tag_name` (verified via the API). The error message is wrong: there are releases.

## Root cause

`resolve_version()` in `.aitask-scripts/aitask_upgrade.sh` (lines ~44-60) calls the **unauthenticated** GitHub API:

```
https://api.github.com/repos/beyondeye/aitasks/releases/latest
```

Unauthenticated API access is capped at **60 requests/hour per public IP**. When that quota is exhausted, GitHub responds with **HTTP 403** and a *non-empty* JSON body:

```json
{ "message": "API rate limit exceeded for <ip>", "documentation_url": "..." }
```

The script's only guard is `if [[ -z "$api_response" ]]` (line ~49), which only catches an **empty / network-unreachable** response (→ "Could not reach GitHub API"). A rate-limit body is non-empty but has no `tag_name`, so it slips through: `grep '"tag_name"'` finds nothing, `version` ends up empty, and the script dies with the misleading **"No releases found"** message (line ~58-59).

## Why intermittent / why it "works now"

- Same machine → same public IP → a **single shared 60/hour bucket** across all repos.
- Exhaustion comes mainly from **repeated, *uncached* `ait upgrade` invocations** across sibling repos (each `resolve_version` call is one uncached REST hit), compounded by the lower-frequency callers below.

**Correction (investigation found three callers of `/releases/latest`, not one):**

1. `resolve_version()` in `.aitask-scripts/aitask_upgrade.sh` — the actual bug (uncached, no fallback, misleading message).
2. `check_latest_version()` in `.aitask-scripts/aitask_setup.sh` (~line 1620) — runs **only at the end of `ait setup` / `ait upgrade`** (called once at ~line 3182), and already silently returns on failure. Low-frequency; shares the duplicated parse.
3. `check_for_updates()` in the top-level **`ait` dispatcher** (~lines 116–179) — the real per-command "update available" check. It **already caches with a 24h TTL** (`~/.aitask/update_check`), fetches in a backgrounded subshell, **keeps the timestamp fresh on a parse-miss so it does not retry**, and is **skipped for `upgrade`/`setup`**. It does **not** spam the API. (`aitask_upgrade.sh:130` only *clears* this cache.)

So the original premise that a background check "burns the quota on every `ait` run" was wrong — that path is already capped at once/day and degrades gracefully.

This is **not** a code-divergence bug: the sibling repos run v0.25.0 of `aitask_upgrade.sh`, whose `resolve_version` is byte-identical to current v0.26.0. It is a framework-wide error-handling gap.

## Acceptance criteria

1. **Accurate diagnostics:** `resolve_version()` distinguishes and reports, with distinct messages:
   - rate-limit-exceeded (parse the HTTP status and/or the `message` field; ideally include the reset time from the `X-RateLimit-Reset` header or `rate_limit` endpoint),
   - genuine "no releases" (real 404 / empty release list),
   - network-unreachable.
   Capture the HTTP status code (e.g. `curl -w '%{http_code}'` or check headers) instead of relying solely on body emptiness.
2. **Rate-limit-free fallback:** when the API path fails, fall back to resolving the latest version tag via the **git protocol**, which is *not* subject to the 60/hour API limit, e.g.:
   ```bash
   git ls-remote --tags --refs https://github.com/beyondeye/aitasks 'v*'
   ```
   sort the resulting tags semver-aware and pick the highest. Confirm `ait upgrade` succeeds via this path even when the REST API is rate-limited.
3. **Optional token support:** if `GH_TOKEN` / `GITHUB_TOKEN` is set in the environment, send it as a bearer/`Authorization` header to raise the limit to 5000/hour. Do not require a token.
4. **Route `check_latest_version()`** in `aitask_setup.sh` through the same shared resolver (so it benefits from the accurate classification + git-tag fallback), preserving its existing silent-degrade contract. **No new TTL cache is needed**: the only per-command update check (the `ait` dispatcher's `check_for_updates()`) already caches with a 24h TTL and degrades gracefully — its **sole** defect is a latent macOS bug, a GNU-only `\?` BRE quantifier in its `sed` parse (`ait:167`), which is fixed in place to the portable `sed -E ...v?...` form used elsewhere. (Footgun documented in `aidocs/framework/sed_macos_issues.md`.)
5. **Tests:** add a self-contained bash test under `tests/` exercising the shared resolver against fixtures for a rate-limit 403 body, a valid release body, a 404, and an empty response (asserting the correct classification/exit for each), plus the git-tag fallback and the combined resolver's fallback-on-rate-limit path.

## Affected files

- `.aitask-scripts/lib/github_release.sh` — **new** shared, sourceable resolver (API classification + git-tag fallback + token support).
- `.aitask-scripts/aitask_upgrade.sh` — `resolve_version()` rewrite (primary fix).
- `.aitask-scripts/aitask_setup.sh` — `check_latest_version()` routed through the helper.
- `ait` — one-line `sed -E` portability fix in `check_for_updates()` (~line 167).
- `tests/test_github_release.sh` — new unit test for the shared resolver.

## Notes

- Shell conventions apply (`aidocs/framework/shell_conventions.md`): `set -euo pipefail`, error helpers, macOS sed/grep portability for any parsing.
- Keep the existing `--force --dir` installer flow and the `~/.aitask/update_check` cache-clear behavior intact.
- Sibling repos will pick up the fix on their next `ait upgrade` once it's released; no per-repo change needed.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-24T21:43:19Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-24T21:43:21Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-24T21:54:06Z status=pass attempt=1 type=human
