---
Task: t759_fix_test_rpm_rockylinux_curl_minimal_conflict.md
Base branch: main
plan_verified: []
---

# Plan — Fix test-rpm rockylinux curl-minimal conflict

## Context

The v0.20.1 release run (https://github.com/beyondeye/aitasks/actions/runs/25625180130) shipped all artifacts (build-rpm, build-deb, publish-aur, publish-homebrew) successfully, but the `packaging / test-rpm (rockylinux:9)` smoke job failed at the very first `Install curl` step:

```
package curl-minimal-7.76.1-26.el9_3.2.0.1.x86_64 from @System
  conflicts with curl provided by curl-7.76.1-35.el9_7.3.x86_64 from baseos
(try to add '--allowerasing' to command line ...)
##[error]Process completed with exit code 1.
```

The current `rockylinux:9` Docker image preinstalls `curl-minimal`, which dnf refuses to silently replace with the full `curl` package. Fedora 41 / 42 are unaffected (their base images don't ship `curl-minimal`), so the failure is rocky-only.

This is a CI smoke-test bug, not a release defect — the published RPM/DEB/AUR/Homebrew artifacts for v0.20.1 are fine. The fix is a single flag change so future releases don't get a red ❌ on the workflow summary.

## Approach

Add `--allowerasing` to the `dnf install` line so dnf is permitted to swap `curl-minimal` for `curl`. This is the workaround dnf itself recommends in the error message and is a no-op on Fedora 41/42 where there is nothing to erase.

Considered and rejected:
- **Drop `curl` entirely, keep only `ca-certificates`** — works (curl-minimal already provides `/usr/bin/curl` and the only call site is `curl -fsSL ... -o /tmp/ait.rpm`), but couples the workflow to whatever curl variant the base image ships.
- **Pin to a specific `rockylinux:9.x` digest** — fragile; defers the problem.

## Files to modify

- `.github/workflows/release-packaging.yml:218` — single-line edit.

## Implementation

In `.github/workflows/release-packaging.yml`, in the `test-rpm` job, change:

```yaml
      - name: Install curl
        run: dnf install -y curl ca-certificates
```

to:

```yaml
      - name: Install curl
        run: dnf install -y --allowerasing curl ca-certificates
```

Nothing else in the workflow changes. The `test-deb` `apt-get install` line at `.github/workflows/release-packaging.yml:157` is unaffected (apt has no equivalent conflict).

## Verification

The workflow has only `on: workflow_call` (no `workflow_dispatch`), so it can only run as part of a tag push from `release.yml`. Verifying without bumping a release means reproducing locally with Docker, which is faster and authoritative for this specific failure:

```bash
# Reproduce the original failure (expect non-zero exit + curl-minimal conflict message)
docker run --rm rockylinux:9 dnf install -y curl ca-certificates

# Confirm the fix on rocky 9 (expect: curl-minimal replaced, exit 0)
docker run --rm rockylinux:9 dnf install -y --allowerasing curl ca-certificates

# Confirm no regression on the unaffected matrix entries (expect: exit 0)
docker run --rm fedora:41 dnf install -y --allowerasing curl ca-certificates
docker run --rm fedora:42 dnf install -y --allowerasing curl ca-certificates
```

End-to-end CI verification will land naturally on the next release tag (v0.20.2 or later) — confirm the `test-rpm (rockylinux:9)` job is green in that run.

## Out of scope

- The `Node 20 deprecation` warnings on `actions/checkout@v4` and `softprops/action-gh-release@v2` are tracked separately by `t758_upgrade_node20_deprecated_actions_in_release_workflow.md`. Different concern, different files-touched footprint, do not bundle here.
- The 7-second `publish-homebrew` runtime in the same v0.20.1 run (suggesting it may have been soft-skipped pending the in-progress homebrew tap setup tracked outside this task) is unrelated.

## Step 9 notes

Standard Step 9 (Post-Implementation) applies. No worktree was created (fast profile), so the branch/worktree cleanup steps are skipped — only the archive script and push run.
