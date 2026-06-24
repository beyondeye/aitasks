---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [framework]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-24 23:35
updated_at: 2026-06-24 23:40
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
- Running `ait` in multiple sibling repos compounds the calls. Additionally, `check_latest_version()` in `.aitask-scripts/aitask_setup.sh` (line ~1620) hits the **same** `/releases/latest` endpoint as the background "update available" check on `ait` invocations, silently consuming the same quota.
- The quota resets hourly, so a later retry succeeds — making the failure look random.

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
4. **Apply the same hardening to `check_latest_version()`** in `aitask_setup.sh` so the background update check doesn't burn the shared quota on every `ait` run — at minimum cache its result with a TTL (there is already a `~/.aitask/update_check` cache file referenced in `aitask_upgrade.sh:130`); reuse/extend that cache so the network call is skipped within the TTL.
5. **Tests:** add a bash test under `tests/` that exercises `resolve_version` against fixtures for (a) a rate-limit 403 body, (b) a valid release body, (c) an empty response — asserting the correct message/exit for each. Keep it self-contained per the repo's test conventions.

## Affected files

- `.aitask-scripts/aitask_upgrade.sh` — `resolve_version()` (primary fix)
- `.aitask-scripts/aitask_setup.sh` — `check_latest_version()` (~line 1620; shared-quota hardening + cache)
- `tests/` — new test for version resolution

## Notes

- Shell conventions apply (`aidocs/framework/shell_conventions.md`): `set -euo pipefail`, error helpers, macOS sed/grep portability for any parsing.
- Keep the existing `--force --dir` installer flow and the `~/.aitask/update_check` cache-clear behavior intact.
- Sibling repos will pick up the fix on their next `ait upgrade` once it's released; no per-repo change needed.
