---
priority: low
effort: low
depends: []
issue_type: chore
status: Ready
labels: [ci, packaging, workflows]
created_at: 2026-05-10 10:29
updated_at: 2026-05-10 10:29
---

The `Release Packaging` workflow surfaces Node 20 deprecation warnings for two GitHub Actions referenced in `.github/workflows/release-packaging.yml`:

- `actions/checkout@v4`
- `softprops/action-gh-release@v2`

These are informational/non-blocking warnings emitted by the GitHub-hosted runner because the underlying Node 20 runtime is being phased out. The actions still execute successfully today, but will stop running once GitHub retires Node 20 support on the runners.

## Source run

https://github.com/beyondeye/aitasks/actions/runs/25457909709 (the same v0.20.0 release run that surfaced the now-fixed `goreleaser/nfpm-action` issue tracked as t757).

## Suggested fix

Bump each action to the latest major (or whichever major moves to Node 24 once available):

- `actions/checkout@v4` → upgrade to the next major when published with Node 24 support (currently `v4` is the latest stable; recheck before fixing).
- `softprops/action-gh-release@v2` → recheck for a newer major before fixing.

Touchpoints to audit (not just `release-packaging.yml`):

```bash
grep -rn 'actions/checkout@\|softprops/action-gh-release@' .github/
```

Bump every reference together to keep versions consistent across workflows.

## Verification

1. After bump: re-run a release (or trigger via a throwaway pre-release tag) and confirm no `Node 20` deprecation warnings in the run summary.
2. Confirm `build-deb`, `build-rpm`, `test-deb`, `test-rpm` and the upload steps still pass — i.e. the bump is behavior-preserving for the release pipeline.

## Out of scope

- Changes to nfpm packaging (handled in t757).
- Maintainer-secret gating (`HOMEBREW_TAP_TOKEN`, `AUR_SSH_PRIVATE_KEY`) — already correct.

## Related

- t757 (Fix nfpm-action in release packaging workflow) flagged these deprecations as out-of-scope.
