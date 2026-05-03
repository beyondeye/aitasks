---
priority: high
effort: medium
depends: [t623_1]
issue_type: feature
status: Implementing
labels: [install_scripts, installation, packaging, homebrew, ci]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-22 18:57
updated_at: 2026-05-03 12:58
---

## Context

Second child of t623. Depends on t623_1 (which extracts the global shim to `packaging/shim/ait` and adds a release asset for it).

**Why.** Homebrew is the dominant toolchain for macOS users. Currently they must use `curl -fsSL .../install.sh | bash`, which is friction-heavy compared to the `brew install` they do for everything else. This child makes `brew install beyondeye/aitasks/aitasks` work, with automatic formula bumps on every release.

Also introduces the reusable `release-packaging.yml` workflow that t623_3/4/5 extend.

## Key Files to Modify

- `packaging/homebrew/aitasks.rb.template` (new) — Ruby formula template with `VERSION_PLACEHOLDER` and `SHA256_PLACEHOLDER`.
- `packaging/homebrew/README.md` (new) — maintainer runbook for creating the `beyondeye/homebrew-aitasks` tap repo + `HOMEBREW_TAP_TOKEN` provisioning.
- `.github/workflows/release-packaging.yml` (new, reusable `workflow_call` workflow) — contains a `publish-homebrew` job.
- `.github/workflows/release.yml` (modified) — after release is published, `uses: ./.github/workflows/release-packaging.yml` (passing the version as an input).

## Reference Files for Patterns

- `aiplans/archived/p623/p623_1_*.md` (once t623_1 archives) — **primary reference** for shim path, release-asset URL, and deps lookup table.
- `aidocs/packaging_strategy.md` (from t623_1) — formula structure + secrets runbook.
- `sinelaw/fresh/.github/workflows/aur-publish.yml` — exact structure for downloading release asset → computing SHA256 → template substitution. We adapt this pattern for Homebrew.
- Existing `.github/workflows/release.yml:133-145` — `softprops/action-gh-release` pattern; the publishing job must run after this step.

## Implementation Plan

1. Create `packaging/homebrew/aitasks.rb.template` with contents:
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
       output = shell_output("#{bin}/ait some-command 2>&1", 1)
       assert_match(/No ait project found/, output)
     end
   end
   ```
2. Create `packaging/homebrew/README.md` with:
   - One-time tap-repo creation steps (create `beyondeye/homebrew-aitasks` on GitHub with a `Formula/` directory).
   - `gh secret set HOMEBREW_TAP_TOKEN --repo beyondeye/aitasks` using a PAT with `repo` scope on the tap repo.
   - How to test the formula locally (`brew install --build-from-source ./Formula/aitasks.rb`).
3. Create `.github/workflows/release-packaging.yml`:
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
         - name: Render formula
           run: |
             mkdir -p tap-out
             sed -e "s/VERSION_PLACEHOLDER/${VERSION}/g" \
                 -e "s/SHA256_PLACEHOLDER/${{ steps.checksum.outputs.sha256 }}/g" \
                 packaging/homebrew/aitasks.rb.template > tap-out/aitasks.rb
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
             git commit -m "Update aitasks to v${VERSION}" || echo "No changes"
             git push origin main
   ```
4. Modify `.github/workflows/release.yml` to add a final job that calls `release-packaging.yml`:
   ```yaml
   packaging:
     needs: release
     uses: ./.github/workflows/release-packaging.yml
     secrets: inherit
     with:
       version: ${{ needs.plan.outputs.version }}
   ```
   Add a `plan` job per `sinelaw/fresh` pattern that extracts version from `GITHUB_REF_NAME` once and exposes it as an output, so both `release` and `packaging` consume it.

## Verification Steps

1. **Local formula test (on macOS):**
   - Clone `beyondeye/homebrew-aitasks` locally.
   - Render the formula manually from template.
   - `brew install --build-from-source ./Formula/aitasks.rb`.
   - `brew test aitasks` passes.
   - `which ait` resolves to `$(brew --prefix)/bin/ait`.
   - `ait setup` in a fresh empty git repo succeeds.
2. **CI dry-run:** Tag a prerelease (e.g., `v0.17.1-rc.1`) — trigger `release.yml` in test mode. Verify the `packaging` job runs and pushes to the tap repo.
3. **End-to-end:** After the real `v0.18.0` tag, verify:
   - Tap repo `Formula/aitasks.rb` updated within 2 min.
   - `brew update && brew install beyondeye/aitasks/aitasks` installs cleanly on a fresh macOS VM.
   - `ait --version` or `ait setup` output is sane (the shim doesn't know its own version — it reports the project-installed framework version; document this caveat).
4. Lint: `shellcheck .github/workflows/release-packaging.yml` is N/A (YAML); use `actionlint` or GitHub's built-in validator.
