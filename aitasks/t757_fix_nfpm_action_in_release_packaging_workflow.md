---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [ci, packaging]
assigned_to: dario-e@beyond-eye.com
issue: https://github.com/beyondeye/aitasks/actions/runs/25457909709
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-08 10:49
updated_at: 2026-05-10 10:35
---

The v0.20.0 release workflow has two failing jobs (`packaging / build-deb` and `packaging / build-rpm`) because both reference a GitHub Action that no longer exists.

## Failing run
https://github.com/beyondeye/aitasks/actions/runs/25457909709

## Root cause
Both jobs fail at "Set up job" with:
```
##[error]Unable to resolve action goreleaser/nfpm-action, repository not found
```

The `goreleaser/nfpm-action` repository on GitHub returns 404 — the action has been removed/deleted upstream since t623_4 / t623_5 originally wired it in. As a result:
- No `.deb` is built or uploaded for the release
- No `.rpm` is built or uploaded for the release
- `test-deb` and `test-rpm` jobs are skipped (they depend on the build jobs)

## Locations to fix
`.github/workflows/release-packaging.yml`:
- Line 126 — `build-deb` step "Install nfpm"
- Line 189 — `build-rpm` step "Install nfpm"

## Suggested fix
Replace `uses: goreleaser/nfpm-action@v1` with a direct nfpm install. Two options (the archived plan p623_4 already documents that local testing during t623_4 was performed via the `goreleaser/nfpm:latest` Docker image — so either path is consistent with the existing approach):

**Option A — Docker (matches local test path used in p623_4):**
```yaml
- name: Build .deb
  run: |
    docker run --rm -v "$PWD:/tmp/src" -w /tmp/src goreleaser/nfpm:latest \
      package --packager deb \
      --config packaging/nfpm/nfpm.yaml \
      --target "aitasks_${VERSION}_all.deb"
```
(Drops the separate "Install nfpm" step entirely.)

**Option B — Direct binary install:**
```yaml
- name: Install nfpm
  run: |
    NFPM_VERSION=2.46.3
    curl -sSL "https://github.com/goreleaser/nfpm/releases/download/v${NFPM_VERSION}/nfpm_${NFPM_VERSION}_Linux_x86_64.tar.gz" \
      | sudo tar -xz -C /usr/local/bin nfpm
```

Recommend Option A: fewer moving parts, matches the local-verification path already documented in the archived t623_4 plan, and avoids hard-coding an nfpm version that needs to be bumped.

## Verification after fix
1. Trigger the release workflow on a test tag (or rerun against v0.20.0)
2. Confirm `build-deb`, `build-rpm`, `test-deb`, `test-rpm` jobs pass
3. Confirm `.deb` and `.rpm` artifacts are uploaded to the release page

## Out of scope (separate concerns flagged by the same run)
- Node 20 deprecation warnings for `actions/checkout@v4` and `softprops/action-gh-release@v2` — informational, not blocking. Track as a separate task if desired.
- Maintainer-secret gating (`HOMEBREW_TAP_TOKEN`, `AUR_SSH_PRIVATE_KEY`) is working as designed (soft-skip with warnings).

## Related history
- t623_4 (archived) — added the deb packaging workflow
- t623_5 (archived) — added the rpm packaging workflow
- p623_4 / p623_5 (archived plans) — note that the action was pinned at `@v1` and that local testing used the Docker image
