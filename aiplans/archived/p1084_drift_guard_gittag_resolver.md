---
Task: t1084_drift_guard_gittag_resolver.md
Worktree: (none - profile 'fast', current branch)
Branch: (current)
Base branch: main
---

# Plan: Drift guard for git tag resolvers (t1084)

## Context

t1075 added `resolve_latest_version_gittags()` to `install.sh` as an inlined
copy of `.aitask-scripts/lib/github_release.sh`'s `github_latest_tag_version()`.
The duplication is intentional because `install.sh` must work on the
`curl | bash` path before `.aitask-scripts/lib/github_release.sh` exists on
disk, but it means future edits can make the standalone installer resolve a
different latest tag than the framework library.

## Implementation Plan

- Extend `tests/test_install_tarball_download.sh`, which already sources
  `install.sh --source-only` and stubs `git ls-remote`.
- Source `.aitask-scripts/lib/github_release.sh` in the same test file.
- Add a helper that feeds one shared `GIT_TAGS_OUTPUT` fixture through both
  `resolve_latest_version_gittags()` and `github_latest_tag_version "$REPO"`,
  asserting the expected output and parity between the two functions.
- Add two drift fixtures:
  - numeric ordering: `v0.9.0`, `v0.10.0`, `v0.2.1` resolves to `0.10.0`;
  - edge filtering/sort parity: include `v1.2.3-alpha`, `v1.2.3`,
    `v1.2.10`, and `v1.2.3.4`, asserting the current shared result `1.2.10`.
- Do not change production resolver logic.

## Verification

- `bash tests/test_install_tarball_download.sh`
- `bash tests/test_github_release.sh`

## Final Implementation Notes

- **Actual work done:** Added the shared-library source to
  `tests/test_install_tarball_download.sh`, introduced
  `assert_gittag_resolver_parity`, and added numeric-sort plus edge-filtering
  parity fixtures for the installer and library git-tag resolvers.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Kept the guard in the existing installer tarball test so it
  reuses the established `install.sh --source-only` load path and `git`
  fixture, avoiding a separate shell harness for the same behavior.
- **Upstream defects identified:** None
