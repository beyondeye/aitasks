---
Task: t757_fix_nfpm_action_in_release_packaging_workflow.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan — t757: Fix nfpm-action in release packaging workflow

## Context

The `Release Packaging` workflow attached to v0.20.0 (run [25457909709](https://github.com/beyondeye/aitasks/actions/runs/25457909709)) failed in two jobs:

```
##[error]Unable to resolve action goreleaser/nfpm-action, repository not found
```

`goreleaser/nfpm-action` was referenced when the deb/rpm packaging was first wired up (archived tasks t623_4 / t623_5). The upstream repo has since been removed (returns 404), so any release that triggers the packaging workflow will fail at "Set up job" before running any steps. As a result `.deb` and `.rpm` artifacts are not produced or uploaded for releases, and the dependent `test-deb` / `test-rpm` jobs are skipped.

The fix replaces the broken `uses:` step with a direct invocation of the official `goreleaser/nfpm` Docker image — the same image that the archived plan `aiplans/archived/p623/p623_4_debian_ubuntu_deb_package_with_ci.md` documents was used for local verification of the packaging at t623_4 implementation time. The Docker route eliminates a moving part (no separate "Install nfpm" step, no version-pin to maintain) and keeps the workflow consistent with the documented local-test path.

## Files Modified

- `.github/workflows/release-packaging.yml` — only file changed. Two jobs (`build-deb` and `build-rpm`).

## Implementation

### Change 1 — `build-deb` job (lines ~125–134)

Replace this block:

```yaml
      - name: Install nfpm
        uses: goreleaser/nfpm-action@v1

      - name: Build .deb
        run: |
          nfpm package \
            --packager deb \
            --config packaging/nfpm/nfpm.yaml \
            --target "aitasks_${VERSION}_all.deb"
```

with:

```yaml
      - name: Build .deb (via nfpm Docker image)
        run: |
          docker run --rm \
            -v "$PWD:/tmp/src" -w /tmp/src \
            -e VERSION \
            goreleaser/nfpm:latest \
            package \
              --packager deb \
              --config packaging/nfpm/nfpm.yaml \
              --target "aitasks_${VERSION}_all.deb"
```

Notes:
- `-v "$PWD:/tmp/src" -w /tmp/src` mirrors the invocation recorded in the archived p623_4 plan.
- `-e VERSION` forwards the job-level `VERSION` env so nfpm.yaml's `version: ${VERSION}` interpolation works inside the container.
- The `--target` path is relative to the working directory, so the artifact lands in `$PWD/aitasks_${VERSION}_all.deb` on the runner — exactly where the existing `Upload to release` step picks it up. No change to the upload step.

### Change 2 — `build-rpm` job (lines ~188–197)

Same edit, mirrored for rpm. Replace:

```yaml
      - name: Install nfpm
        uses: goreleaser/nfpm-action@v1

      - name: Build .rpm
        run: |
          nfpm package \
            --packager rpm \
            --config packaging/nfpm/nfpm.yaml \
            --target "aitasks-${VERSION}-1.noarch.rpm"
```

with:

```yaml
      - name: Build .rpm (via nfpm Docker image)
        run: |
          docker run --rm \
            -v "$PWD:/tmp/src" -w /tmp/src \
            -e VERSION \
            goreleaser/nfpm:latest \
            package \
              --packager rpm \
              --config packaging/nfpm/nfpm.yaml \
              --target "aitasks-${VERSION}-1.noarch.rpm"
```

Same rationale as Change 1.

### Why Docker over a direct binary install

| Option | Pros | Cons |
|---|---|---|
| Docker image `goreleaser/nfpm:latest` (chosen) | No version pin to maintain; `docker` is preinstalled on `ubuntu-latest`; matches the archived t623_4 local-test invocation. | Tagged at `:latest` — pulls newest at run time. Acceptable for a release-packaging job; the alternative is to pin a specific `:v2.46.3` tag if reproducibility is desired. |
| Direct binary install via `curl ... | tar` | Pinned version → reproducible. | Adds a separate step; requires bumping the pin manually whenever nfpm releases. |

If the user prefers reproducibility, pin to `goreleaser/nfpm:v2.46.3` (current latest) instead of `:latest`. Recommend `:latest` for now to match the original `@v1` major-pin spirit (allow non-breaking updates).

### Out of scope (flagged but NOT changed in this task)

- **Node 20 deprecation warnings** for `actions/checkout@v4` and `softprops/action-gh-release@v2` — informational only, surfaced by the same run. Should be tracked as a separate task if/when an upgrade is desired.
- **Maintainer-secret gating** (`HOMEBREW_TAP_TOKEN`, `AUR_SSH_PRIVATE_KEY`) — already working as designed (soft-skip with warnings). No change.
- **Other workflow files** — `grep -rn nfpm-action .github/` confirms the only two references in active code are at lines 126 and 189 of `release-packaging.yml`. No other touchpoints.

## Verification

1. **Static check** — `grep -n 'nfpm-action\|nfpm:latest' .github/workflows/release-packaging.yml` should show two `nfpm:latest` lines and zero `nfpm-action` lines after the edit.

2. **Local dry-run of the Docker invocation** (replicates what the runner will do):
   ```bash
   VERSION=0.20.0-test docker run --rm \
     -v "$PWD:/tmp/src" -w /tmp/src \
     -e VERSION \
     goreleaser/nfpm:latest \
     package --packager deb \
     --config packaging/nfpm/nfpm.yaml \
     --target "/tmp/aitasks_${VERSION}_all.deb"
   ls -la /tmp/aitasks_*.deb
   ```
   Same for `--packager rpm`. Confirms nfpm.yaml resolves the relative `./packaging/shim/ait` and `./packaging/nfpm/postinstall.sh` paths correctly inside the container.

3. **CI verification** — the actual workflow only runs on a real release tag. Two options to verify before the next real release:
   - Open a PR with the fix; the workflow file is `workflow_call`-only so it won't trigger automatically — leave the next real release tag as the verification trigger.
   - (Optional, more aggressive) Push a throwaway pre-release tag (e.g. `v0.20.1-test`) to exercise the full release pipeline once.

4. **Post-merge expected outcome** — on the next release: `build-deb` and `build-rpm` complete green; `aitasks_<v>_all.deb` and `aitasks-<v>-1.noarch.rpm` are uploaded to the release; `test-deb` and `test-rpm` matrix runs against ubuntu/debian and fedora/rocky distros pass.

## Step 9 (Post-Implementation)

This task is implemented on the current branch (no worktree, per fast profile `create_worktree: false`). Step 9 will:
- Skip worktree cleanup.
- Skip `verify_build` if not configured (it isn't for this repo).
- Run `aitask_archive.sh 757` to move task/plan to archived/, set status Done, release lock, and commit.
- `./ait git push`.
