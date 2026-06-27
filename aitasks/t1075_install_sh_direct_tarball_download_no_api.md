---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [installer, upgrade, github-api, reliability]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-25 11:30
updated_at: 2026-06-27 22:35
---

## Problem

`ait upgrade <VERSION>` fails with

```
[ait] Error: Could not find release tarball. Download manually from:
            https://github.com/beyondeye/aitasks/releases
```

whenever the unauthenticated GitHub REST API quota (60 requests/hour per IP) is
exhausted. The error is misleading — the release tarball exists; the API simply
returned a rate-limit JSON body instead of release data, and the installer's
`grep '"browser_download_url"'` found nothing.

This is the **download** half of the same class of failure that t1069 fixed for
version **resolution**. t1069 hardened `resolve_version` in
`.aitask-scripts/aitask_upgrade.sh` (REST API → `git ls-remote` fallback + token
support, via `lib/github_release.sh`). But the tarball download in `install.sh`
was never touched and still hits the rate-limited REST API with no token and no
fallback.

## Root cause

`download_tarball()` in `install.sh` (around line 188) does:

```sh
api_response="$(curl -sS ... "https://api.github.com/repos/$REPO/releases/latest")"
tarball_url="$(echo "$api_response" | grep '"browser_download_url".*\.tar\.gz"' ...)"
```

Two defects:

1. **Rate-limit fragile.** It depends on the REST API (`releases/latest`) purely
   to discover a download URL that is, in fact, deterministic. No `GH_TOKEN`
   support, no fallback. This is the failure the reporter hit.
2. **Requested version is ignored.** `aitask_upgrade.sh` resolves the target
   version, then runs `bash install.sh --force --dir "$AIT_DIR"` **without
   passing the version through**. `download_tarball` always fetches
   `releases/latest`. So `ait upgrade <older-version>` silently installs the
   *latest* tarball instead of the requested one. This is currently masked only
   because the requested version usually equals latest.

## The release asset URL is deterministic (no API needed)

`.github/workflows/release.yml:87` builds the asset as:

```sh
tar -czf aitasks-${{ github.ref_name }}.tar.gz ...   # ref_name == tag, e.g. v0.26.1
```

So for any tag the asset is always `aitasks-v<VERSION>.tar.gz`, downloadable from
the release-assets CDN (NOT the REST API, NOT rate-limited):

```
https://github.com/<repo>/releases/download/v<VERSION>/aitasks-v<VERSION>.tar.gz
```

Verified: this returns `302 → 200` (~1.5 MB) with zero REST API calls. For the
bare `curl | bash` path where no version is supplied, the latest version can be
resolved API-free via `git ls-remote --tags` (the git protocol is exempt from
the REST quota — already implemented as `github_latest_tag_version` /
`github_resolve_latest_version` in `lib/github_release.sh`).

## Suggested fix

1. **Pass the resolved version into `install.sh`.** From `aitask_upgrade.sh`,
   export `AIT_TARGET_VERSION` (or add a `--version` flag) before invoking the
   installer. This fixes defect #2.
2. **Build the deterministic CDN URL in `download_tarball`** from the version and
   download it directly — no REST API call on the upgrade path.
3. **Resolve `latest` API-free for the standalone `curl | bash` path.** When no
   version is provided (installer run directly, lib not guaranteed present),
   resolve via `git ls-remote --tags`; keep the REST API only as a last-resort
   fallback, and have *that* honor `GH_TOKEN` / `GITHUB_TOKEN`.
4. Keep `--local-tarball` behavior unchanged.

## Audit of remaining GitHub-API touchpoints (lower priority, same class)

| Location | Purpose | Risk | Note |
|----------|---------|------|------|
| `ait:164` `check_for_updates` | daily background update notice | Low — cached 24h, runs in background subshell, fails silently | Could reuse `github_resolve_latest_version` for token + git fallback; not user-blocking |
| `aitask_setup.sh:226/290/324` | `bkt` (bitbucket-cli) latest version | Medium — only during `ait setup`, 3rd-party repo | Already fails soft (warn + manual-install hint); add token / pin? |
| `aitask_setup.sh:2779` | `lazygit` latest version | Medium — only during `ait setup`, 3rd-party repo | Already fails soft (warn + skip) |

These are not the reported failure and degrade gracefully; fold in only if cheap.

## Acceptance criteria

- `ait upgrade <VERSION>` downloads `aitasks-v<VERSION>.tar.gz` from the CDN with
  **no** call to `api.github.com` on the happy path (verifiable by blocking
  `api.github.com` and confirming the upgrade still succeeds).
- `ait upgrade <older-version>` installs **that** version's tarball, not latest.
- Standalone `curl | bash install.sh` (no version) still resolves and installs
  the latest release when the REST API is rate-limited (git-tag fallback).
- `--local-tarball` path still works.
- `GH_TOKEN` / `GITHUB_TOKEN`, when set, is honored on any remaining REST call.

## Key files

- `install.sh` — `download_tarball()` (the rate-limited REST lookup; the fix site)
- `.aitask-scripts/aitask_upgrade.sh` — `main()` invokes `install.sh` without
  passing the resolved version; `resolve_version` already hardened (t1069)
- `.aitask-scripts/lib/github_release.sh` — reusable API-free resolvers
  (`github_latest_tag_version`, `github_resolve_latest_version`) + token support
- `.github/workflows/release.yml:87` — proves the deterministic asset name
- `ait:164`, `.aitask-scripts/aitask_setup.sh:226/290/324/2779` — secondary
  API touchpoints noted in the audit above
- Note macOS/sed portability conventions — see `aidocs/framework/sed_macos_issues.md`
