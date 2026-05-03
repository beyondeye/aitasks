# Homebrew packaging

Templates and reference for the aitasks Homebrew tap.

## What's here

- `aitasks.rb.template` — Ruby formula template with `VERSION_PLACEHOLDER`
  and `SHA256_PLACEHOLDER` markers. Rendered by the `publish-homebrew` job
  in `.github/workflows/release-packaging.yml` on every `v*` release tag,
  then pushed to the `beyondeye/homebrew-aitasks` tap repo.
- This README.

## First-time setup

If you are setting up Homebrew distribution for aitasks for the first time
— creating the `beyondeye/homebrew-aitasks` tap repo, generating the
`HOMEBREW_TAP_TOKEN` PAT, validating the formula on a macOS workstation,
cutting the first release — see
[`aidocs/homebrew_maintainer_setup.md`](../../aidocs/homebrew_maintainer_setup.md)
for the comprehensive walkthrough.

## Local-test snippet (macOS)

To verify the template renders cleanly and the resulting formula installs
locally, without needing an existing GitHub release:

```bash
VERSION=$(cat .aitask-scripts/VERSION)
SHA256=$(shasum -a 256 packaging/shim/ait | cut -d' ' -f1)
sed -e "s/VERSION_PLACEHOLDER/${VERSION}/g" \
    -e "s/SHA256_PLACEHOLDER/${SHA256}/g" \
    packaging/homebrew/aitasks.rb.template > /tmp/aitasks.rb
brew install --build-from-source /tmp/aitasks.rb
brew test aitasks
```

This snippet uses the **local** shim file at `packaging/shim/ait` and the
**local** `.aitask-scripts/VERSION`, so it tests the upcoming-release shape
without needing the release asset to exist on GitHub yet. The `url` in the
rendered formula will point at a `vVERSION/ait` release asset that may not
exist — `brew install --build-from-source` against a local file path
bypasses the URL fetch, so the test still works.

For the end-user install path (`brew tap … && brew install aitasks`), see
section 5 of `aidocs/homebrew_maintainer_setup.md`.

## Why shim-only

The Homebrew formula bundles only the global `ait` shim — not the framework
itself. Each PM ships the same 87-line shim; the framework is downloaded
on first `ait setup` from `github.com/beyondeye/aitasks`. This decouples
PM release cycles from framework changes — see
[`aidocs/packaging_strategy.md`](../../aidocs/packaging_strategy.md) for
the full rationale, dependency-name mapping, and release-cadence policy.
