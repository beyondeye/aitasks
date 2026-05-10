---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [ci, packaging, workflows]
created_at: 2026-05-10 12:47
updated_at: 2026-05-10 12:47
---

The `test-rpm (rockylinux:9)` job in the Release Packaging workflow fails at the
`Install curl` step because `dnf install -y curl ca-certificates` conflicts with
the `curl-minimal` package preinstalled in the current `rockylinux:9` base image.

Fedora 41 / 42 are unaffected (their base images do not ship `curl-minimal`),
and the actual release artifacts (build-rpm, build-deb, publish-aur,
publish-homebrew) all succeeded — only the post-release smoke test failed.

## Source run

https://github.com/beyondeye/aitasks/actions/runs/25625180130 (v0.20.1)

Failure log excerpt (test-rpm rockylinux:9):

```
Package ca-certificates-2023.2.60_v7.0.306-90.1.el9_2.noarch is already installed.
Error:
 Problem: problem with installed package curl-minimal-7.76.1-26.el9_3.2.0.1.x86_64
  - package curl-minimal-7.76.1-26.el9_3.2.0.1.x86_64 from @System conflicts with curl provided by curl-7.76.1-35.el9_7.3.x86_64 from baseos
  - cannot install the best candidate for the job
(try to add '--allowerasing' to command line to replace conflicting packages ...)
##[error]Process completed with exit code 1.
```

## Location

`.github/workflows/release-packaging.yml:218`:

```yaml
      - name: Install curl
        run: dnf install -y curl ca-certificates
```

## Suggested fix

Add `--allowerasing` so dnf is permitted to replace `curl-minimal` with the
full `curl` package (this is the workaround dnf itself recommends in the
error message and is safe on Fedora 41/42 where there is nothing to erase):

```yaml
      - name: Install curl
        run: dnf install -y --allowerasing curl ca-certificates
```

Alternatives considered:

- **Drop `curl` and only install `ca-certificates`** — `curl-minimal` already
  provides `/usr/bin/curl` and the only subsequent use is a plain
  `curl -fsSL ... -o /tmp/ait.rpm`, which works under curl-minimal. Smaller
  diff but couples the workflow to whatever curl variant the base image ships.
- **Pin to a known-good `rockylinux:9.x` digest** — fragile; a future image
  refresh re-introduces the same bug.

`--allowerasing` is preferred because it preserves intent (full curl in the
test container) and is a one-token change.

## Verification

1. Re-run the workflow against the v0.20.1 tag (or trigger via a throwaway
   pre-release tag) and confirm the `test-rpm (rockylinux:9)` job's
   `Install curl` step succeeds and the rest of the matrix continues to pass.
2. Confirm fedora:41 / fedora:42 still succeed (no regression from the new
   flag).

## Out of scope

- Node 20 deprecation warnings on `actions/checkout@v4` and
  `softprops/action-gh-release@v2` are tracked separately by **t758**.
