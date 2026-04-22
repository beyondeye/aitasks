---
Task: t623_2_homebrew_tap_with_ci_auto_bump.md
Parent Task: aitasks/t623_more_installation_methods.md
Sibling Tasks: aitasks/t623/t623_1_*.md, t623_3_*.md, t623_4_*.md, t623_5_*.md, t623_6_*.md
Archived Sibling Plans: aiplans/archived/p623/p623_1_*.md (once t623_1 archives — primary reference)
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Implementation Plan: t623_2 — Homebrew tap with CI auto-bump

## Prerequisites

1. t623_1 merged (provides `packaging/shim/ait` and `aidocs/packaging_strategy.md`).
2. Maintainer has created the `beyondeye/homebrew-aitasks` repo on GitHub (one-time, per the runbook in `aidocs/packaging_strategy.md`).
3. `HOMEBREW_TAP_TOKEN` secret set on `beyondeye/aitasks` (PAT with `repo` scope on the tap repo).

## Steps

### 1. Create the formula template

`packaging/homebrew/aitasks.rb.template`:

```ruby
class Aitasks < Formula
  desc "File-based task management framework for AI coding agents"
  homepage "https://aitasks.io/"
  url "https://github.com/beyondeye/aitasks/releases/download/vVERSION_PLACEHOLDER/ait"
  sha256 "SHA256_PLACEHOLDER"
  license "Apache-2.0"

  depends_on "bash"
  depends_on "python@3.12"
  depends_on "fzf"
  depends_on "jq"
  depends_on "git"
  depends_on "zstd"
  depends_on "curl"

  def install
    bin.install "ait"
  end

  test do
    output = shell_output("#{bin}/ait some-bogus-command 2>&1", 1)
    assert_match(/No ait project found/, output)
  end
end
```

### 2. Create the maintainer runbook

`packaging/homebrew/README.md`:

- One-time tap-repo creation (clone, add `Formula/` subdir, push initial commit with a placeholder Formula/aitasks.rb that has valid Ruby so `brew tap` doesn't error).
- `gh secret set HOMEBREW_TAP_TOKEN` command with a PAT that has `repo` scope on `beyondeye/homebrew-aitasks`.
- Local test instructions:
  ```bash
  sed -e 's/VERSION_PLACEHOLDER/0.17.0/g' \
      -e "s/SHA256_PLACEHOLDER/$(curl -fsSL https://.../v0.17.0/ait | sha256sum | cut -d' ' -f1)/g" \
      packaging/homebrew/aitasks.rb.template > /tmp/aitasks.rb
  brew install --build-from-source /tmp/aitasks.rb
  brew test aitasks
  ```

### 3. Create the reusable packaging workflow

`.github/workflows/release-packaging.yml`:

```yaml
name: Release Packaging

on:
  workflow_call:
    inputs:
      version:
        required: true
        type: string

jobs:
  publish-homebrew:
    runs-on: ubuntu-latest
    env:
      VERSION: ${{ inputs.version }}
    steps:
      - uses: actions/checkout@v4

      - name: Download shim from release
        id: checksum
        run: |
          curl -fsSL "https://github.com/beyondeye/aitasks/releases/download/v${VERSION}/ait" -o ait
          SHA256=$(sha256sum ait | cut -d' ' -f1)
          echo "sha256=$SHA256" >> "$GITHUB_OUTPUT"
          echo "Shim SHA256: $SHA256"

      - name: Render formula
        run: |
          mkdir -p tap-out
          sed -e "s/VERSION_PLACEHOLDER/${VERSION}/g" \
              -e "s/SHA256_PLACEHOLDER/${{ steps.checksum.outputs.sha256 }}/g" \
              packaging/homebrew/aitasks.rb.template > tap-out/aitasks.rb
          echo "--- Rendered formula ---"
          cat tap-out/aitasks.rb

      - name: Push to tap repo
        env:
          TAP_TOKEN: ${{ secrets.HOMEBREW_TAP_TOKEN }}
        run: |
          git clone "https://x-access-token:${TAP_TOKEN}@github.com/beyondeye/homebrew-aitasks.git" tap-repo
          mkdir -p tap-repo/Formula
          cp tap-out/aitasks.rb tap-repo/Formula/aitasks.rb
          cd tap-repo
          git config user.email "actions@github.com"
          git config user.name "aitasks release bot"
          git add Formula/aitasks.rb
          if git diff --cached --quiet; then
            echo "No formula changes, skipping commit"
          else
            git commit -m "Update aitasks to v${VERSION}"
            git push origin main
          fi
```

### 4. Wire the packaging workflow into the release workflow

Modify `.github/workflows/release.yml`:

1. Add a `plan` job at the top that extracts the version once and exposes it as an output (copy the pattern from `sinelaw/fresh/.github/workflows/release.yml`):
   ```yaml
   plan:
     runs-on: ubuntu-latest
     outputs:
       version: ${{ steps.version.outputs.version }}
     steps:
       - name: Extract version
         id: version
         run: |
           TAG="${GITHUB_REF_NAME}"
           VERSION="${TAG#v}"
           echo "version=$VERSION" >> "$GITHUB_OUTPUT"
   ```
2. Make the existing `release` job `needs: plan` and consume `${{ needs.plan.outputs.version }}` where appropriate.
3. Add a `packaging` job at the end:
   ```yaml
   packaging:
     needs: release
     uses: ./.github/workflows/release-packaging.yml
     secrets: inherit
     with:
       version: ${{ needs.plan.outputs.version }}
   ```

### 5. Validate workflow YAML

Run `actionlint .github/workflows/*.yml` (install via `brew install actionlint` or docker image). Fix any warnings.

## Verification Checklist

- [ ] `packaging/homebrew/aitasks.rb.template` exists and passes Ruby syntax check (`ruby -c packaging/homebrew/aitasks.rb.template` — may need a dummy substitution first).
- [ ] Local formula install on macOS: `brew install --build-from-source /tmp/aitasks.rb` succeeds; `brew test aitasks` passes.
- [ ] `which ait` after brew install points at `$(brew --prefix)/bin/ait`; running `ait setup` in a fresh empty git repo begins the bootstrap.
- [ ] `actionlint .github/workflows/release-packaging.yml .github/workflows/release.yml` clean.
- [ ] After tagging a prerelease (`v0.17.1-rc.1`), the tap repo at `beyondeye/homebrew-aitasks` receives a commit within 2 min.
- [ ] Subsequent tag re-runs update the formula idempotently (no duplicate empty commits).

## Final Implementation Notes (to be filled in post-implementation)

- **Actual work done:**
- **Deviations from plan:**
- **Issues encountered:**
- **Key decisions:**
- **Notes for sibling tasks:** — especially if the `plan` job output name changes (t623_3/4/5 all consume `needs.plan.outputs.version`).
