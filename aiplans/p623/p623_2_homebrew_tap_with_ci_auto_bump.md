---
Task: t623_2_homebrew_tap_with_ci_auto_bump.md
Parent Task: aitasks/t623_more_installation_methods.md
Sibling Tasks: aitasks/t623/t623_1_*.md (archived), t623_3_*.md, t623_4_*.md, t623_5_*.md, t623_6_*.md
Archived Sibling Plans: aiplans/archived/p623/p623_1_packaging_strategy_and_shim_extraction.md (primary reference)
Worktree: (none — working on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-03 16:25
---

# Implementation Plan: t623_2 — Homebrew tap with CI auto-bump

## Context

Second child of t623 (multi-installer effort). Makes
`brew install beyondeye/aitasks/aitasks` work on macOS, with formula auto-bumps
on every release. Also introduces the reusable `release-packaging.yml`
workflow that t623_3/4/5 will extend with AUR / .deb / .rpm jobs.

Builds directly on t623_1 (archived) which extracted the global shim to
`packaging/shim/ait` and added `packaging/shim/ait` as a release asset.

### Release-flow continuity (clarification)

t623_1's changes are entirely additive — the existing curl-bash install path
keeps working unchanged across the transition. Specifically:

- Released tarballs ≤ v0.19.2 (built before t623_1 merged) still install
  cleanly: their bundled `aitask_setup.sh` uses the OLD heredoc and does not
  need `packaging/`.
- The next release (after t623_1) will bundle `packaging/` inside the tarball,
  and the bundled `aitask_setup.sh` `cp`s the shim from there. Also works.
- The new release will additionally publish `packaging/shim/ait` as a
  separate release asset (the URL Homebrew/AUR/.deb/.rpm formulas will curl
  from). Until t623_2/3/4/5 land, this asset has no consumer — it is
  harmless extra metadata.

**After t623_2 lands**, each `v*` tag also fires the new `packaging` job
which pushes the rendered formula to `beyondeye/homebrew-aitasks`. If the
manual maintainer prerequisites (tap repo + `HOMEBREW_TAP_TOKEN` secret)
are not yet in place, the `packaging` job will fail visibly **but the main
release artifact in the upstream `release` job will still publish
successfully**. A soft-skip guard (Step 3 below) downgrades the missing-secret
case from "job fails" to "job warns and exits 0" so red workflow runs on
release tags don't false-alarm.

## Plan Verification (2026-05-03 — verify path entry)

Verified before re-entering plan mode:

- **t623_1 outputs in place**: `packaging/shim/ait` exists (87 lines, executable);
  `aidocs/packaging_strategy.md` exists with all required sections;
  `.github/workflows/release.yml` (commit `d627c0f5`) lists `packaging/` in the
  tarball file list (line 102) and `packaging/shim/ait` in BOTH
  `softprops/action-gh-release` `files:` blocks (lines 138-140 and 147-149).
- **No prior t623_2 commits**: a previous agent locked the task at 12:58 but
  appears to have crashed before writing any code. `packaging/homebrew/` and
  `.github/workflows/release-packaging.yml` do NOT exist. No `packaging/` files
  are tracked beyond `packaging/shim/ait`. Working tree clean except for stale
  unrelated untracked files (`os`, `shutil`, `subprocess`, `time`, `unittest`,
  `.claude/projects/`) that are out of scope.
- **Current `release.yml` structure**: a single `release` job extracts version
  inline at step `version` (line 17-19) using `${{ steps.version.outputs.version }}`.
  The plan refactors this into a separate `plan` job (per the `sinelaw/fresh`
  pattern), then makes both `release` and the new `packaging` job consume
  `${{ needs.plan.outputs.version }}`.
- **Current VERSION**: `0.19.2` (irrelevant for templates, just noting).

Minor concerns flagged by verification (resolved by plan as-written):

1. **License accuracy.** `LICENSE` file says "Apache License, Version 2.0 and
   the Commons Clause restriction below". The plan's formula template uses
   bare `license "Apache-2.0"`. Homebrew's strict license linter may emit a
   warning. Decision: keep `license "Apache-2.0"` in the formula for now — the
   Commons Clause is a non-OSI restriction Homebrew has no first-class
   representation for, and the Strategy doc itself uses "MIT" / "Apache-2.0"
   loosely. If Homebrew lint fails on the tap CI, this can be revisited
   (`license :cannot_represent` or a custom expression). NOT a blocker for
   shipping the formula.
2. **`desc` text.** Plan template uses `"File-based task management framework
   for AI coding agents"`. Strategy doc skeleton says `"File-based task
   framework for AI coding agents"`. Use the plan's longer form (more
   descriptive); within the 80-char Homebrew limit (61 chars actual).
3. **`homepage`.** Plan template uses `"https://aitasks.io/"`. Strategy doc
   skeleton uses the GitHub URL. The aitask_setup.sh codebase references
   `aitasks.io` as the project domain. Use the plan's `https://aitasks.io/`.

No blocking changes — the plan stands. Proceeding.

## Prerequisites

1. ✓ t623_1 merged (provides `packaging/shim/ait` and `aidocs/packaging_strategy.md`).
2. (Manual, out-of-scope for this task) Maintainer creates the
   `beyondeye/homebrew-aitasks` repo on GitHub (one-time, per the runbook
   we author in Step 2).
3. (Manual, out-of-scope) `HOMEBREW_TAP_TOKEN` secret is set on
   `beyondeye/aitasks` (PAT with `repo` scope on the tap repo).

The CI workflow we ship will fail loudly until prerequisites 2 and 3 are met,
but no `beyondeye/aitasks` release is degraded by the failure: the
`packaging` job is in its own reusable workflow.

## Steps

### 0. Author the maintainer first-time-setup walkthrough

`aidocs/homebrew_maintainer_setup.md` (new). This is the comprehensive
"how do I actually do this from scratch" walkthrough for the project owner
(once, when first wiring up the Homebrew distribution channel). It is
deliberately separate from `packaging/homebrew/README.md` (which is a
directory-level reference) and from `aidocs/packaging_strategy.md` (which is
the cross-PM strategy doc, not a step-by-step).

Required sections:

1. **What a Homebrew "tap" is.** Two-paragraph orientation: a tap is a
   third-party repository of formulas; users add it once with
   `brew tap beyondeye/aitasks`, then `brew install aitasks` works (the
   tap-name prefix becomes optional after tapping). The tap itself is a
   regular GitHub repo at `github.com/beyondeye/homebrew-aitasks` with
   a `Formula/` directory containing one `.rb` file per formula. No
   Homebrew account, no review process — distribution is fully self-served
   for taps (vs. core Homebrew which requires review). Cross-link
   <https://docs.brew.sh/Taps> and <https://docs.brew.sh/How-to-Create-and-Maintain-a-Tap>.

2. **Step-by-step: create the tap repo.**
   - Sign in to GitHub as the `beyondeye` org owner (or a maintainer with
     repo-create permission on the org).
   - Create a new public repository named exactly `homebrew-aitasks` (the
     `homebrew-` prefix is required by Homebrew's tap-discovery convention).
     Description suggestion: "Homebrew tap for the aitasks framework — auto-bumped on each beyondeye/aitasks release."
   - Initialize with a README (Homebrew shows it on `brew tap` errors).
   - Clone locally:
     ```bash
     git clone git@github.com:beyondeye/homebrew-aitasks.git
     cd homebrew-aitasks
     mkdir Formula
     ```
   - Seed a placeholder `Formula/aitasks.rb` so `brew tap beyondeye/aitasks`
     does not fail before the first auto-bump runs:
     ```ruby
     class Aitasks < Formula
       desc "File-based task management framework for AI coding agents"
       homepage "https://aitasks.io/"
       url "https://github.com/beyondeye/aitasks/archive/refs/tags/v0.0.0.tar.gz"
       sha256 "0000000000000000000000000000000000000000000000000000000000000000"
       license "Apache-2.0"
       def install
         odie "Placeholder formula — wait for the next aitasks release to populate."
       end
     end
     ```
     Commit + push to `main`. The first real release will overwrite this
     file via the CI flow this task ships.

3. **Step-by-step: provision `HOMEBREW_TAP_TOKEN`.**
   - Generate a fine-grained Personal Access Token at
     <https://github.com/settings/personal-access-tokens/new>:
     - Token name: `aitasks-homebrew-tap-bot`
     - Resource owner: `beyondeye`
     - Repository access: "Only select repositories" → `beyondeye/homebrew-aitasks`
     - Repository permissions: **Contents: Read and write**, **Metadata: Read-only**
     - Expiration: 1 year (calendar a renewal reminder)
   - Save the token text to a password manager.
   - Set it as a secret on the source repo:
     ```bash
     gh secret set HOMEBREW_TAP_TOKEN --repo beyondeye/aitasks
     # (paste the token at the prompt; gh stores it encrypted)
     ```
   - Verify with `gh secret list --repo beyondeye/aitasks` — should show
     `HOMEBREW_TAP_TOKEN` with an `Updated` timestamp.

4. **Step-by-step: end-to-end local test on macOS** (before the first
   real release). Walk the user through manually rendering a formula and
   installing it from a local file:
   ```bash
   # Pick the latest released version
   VERSION=$(curl -fsSL https://api.github.com/repos/beyondeye/aitasks/releases/latest | jq -r .tag_name | sed 's/^v//')

   # Compute the shim's SHA256 directly from the release asset
   SHA256=$(curl -fsSL "https://github.com/beyondeye/aitasks/releases/download/v${VERSION}/ait" | shasum -a 256 | cut -d' ' -f1)

   # Render the template
   sed -e "s/VERSION_PLACEHOLDER/${VERSION}/g" \
       -e "s/SHA256_PLACEHOLDER/${SHA256}/g" \
       packaging/homebrew/aitasks.rb.template > /tmp/aitasks.rb

   # Build + install + test
   brew install --build-from-source /tmp/aitasks.rb
   brew test aitasks
   which ait                   # → $(brew --prefix)/bin/ait
   ait setup                   # in a fresh git repo: should bootstrap
   ```
   - Use `shasum -a 256` (BSD on macOS) instead of `sha256sum` (GNU/Linux);
     CI uses `sha256sum` because runners are Ubuntu.
   - Document the expected `brew test` output line.
   - Document the `python@3.12` Homebrew dep — newer / older Python
     versions can be substituted by editing the template (only one Homebrew
     `python@N.M` package can be the formula's hard dependency).

5. **Step-by-step: cut the first real release.**
   - Tag a small bump (e.g. patch the VERSION file from `0.19.2` to
     `0.19.3` and tag `v0.19.3`).
   - Watch the GitHub Actions run on the source repo: the `plan` →
     `release` → `packaging` job graph fires.
   - Verify the tap repo: `Formula/aitasks.rb` should be overwritten by
     the CI commit; the placeholder is gone.
   - Verify end-user install:
     ```bash
     brew untap beyondeye/aitasks 2>/dev/null
     brew tap beyondeye/aitasks
     brew install aitasks
     ait setup
     ```

6. **Troubleshooting.**
   - **`packaging` job fails with `403 Forbidden` on `git push`.** PAT lacks
     `Contents: Read and write` on the tap repo. Re-issue the token with
     correct permissions.
   - **`packaging` job fails with `404 Not Found` on `git clone`.** Tap repo
     doesn't exist or PAT cannot see it (PAT scoped to wrong org / repo).
   - **`packaging` job is skipped with the warning "HOMEBREW_TAP_TOKEN not
     set, skipping".** This is the soft-skip guard from Step 3 below. The
     main release succeeded; set the secret to enable Homebrew publishing
     on the next tag.
   - **`brew install` shows `unknown sha256` error.** The shim file the user
     downloaded (the release asset) does not match the SHA256 baked into
     the formula. Most likely cause: the release asset was re-uploaded
     after the formula was rendered. Re-run the `publish-homebrew` job by
     re-tagging.
   - **`brew test` fails with no match for `/No ait project found/`.**
     The shim's no-project error message changed in `packaging/shim/ait`.
     Update the formula template's `test do` block to match the current
     wording.
   - **Token expiration.** When the calendar reminder fires, regenerate
     the PAT with the same scopes and re-run
     `gh secret set HOMEBREW_TAP_TOKEN --repo beyondeye/aitasks`.

7. **Cross-references.**
   - `packaging/homebrew/README.md` — directory-level reference (formula
     template, brief local-test).
   - `aidocs/packaging_strategy.md` — cross-PM rationale, dep mapping,
     release-cadence policy.

### 1. Create the formula template


`packaging/homebrew/aitasks.rb.template` (new):

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

Note: the test asserts a `/No ait project found/` substring — verified against
`packaging/shim/ait` which exits 1 with that message when invoked outside an
`ait` project. The exit code 1 is the second arg to `shell_output`.

### 2. Create the directory-level README

`packaging/homebrew/README.md` (new). This is a slim reference for someone
browsing `packaging/homebrew/` — NOT the first-time-setup walkthrough (that
lives in `aidocs/homebrew_maintainer_setup.md`). Sections:

1. **What's here:**
   - `aitasks.rb.template` — Ruby formula template with
     `VERSION_PLACEHOLDER` / `SHA256_PLACEHOLDER` markers. Rendered by
     `.github/workflows/release-packaging.yml`'s `publish-homebrew` job
     on every release tag, then pushed to the
     `beyondeye/homebrew-aitasks` tap repo.
   - This README.

2. **First-time setup:** Pointer to `aidocs/homebrew_maintainer_setup.md`
   (one paragraph: "If you are setting up Homebrew distribution for
   aitasks for the first time — creating the tap repo, provisioning
   the bot token — see [aidocs/homebrew_maintainer_setup.md].").

3. **Local-test snippet (macOS):**
   ```bash
   VERSION=$(cat .aitask-scripts/VERSION)
   SHA256=$(shasum -a 256 packaging/shim/ait | cut -d' ' -f1)
   sed -e "s/VERSION_PLACEHOLDER/${VERSION}/g" \
       -e "s/SHA256_PLACEHOLDER/${SHA256}/g" \
       packaging/homebrew/aitasks.rb.template > /tmp/aitasks.rb
   brew install --build-from-source /tmp/aitasks.rb
   brew test aitasks
   ```
   Note: this snippet uses the LOCAL shim file and the LOCAL VERSION, so it
   tests the upcoming-release shape without needing an existing GitHub
   release. The `url` in the rendered formula will point at a
   `vVERSION/ait` release asset that does not exist yet — `brew install
   --build-from-source` against a local file path bypasses the URL fetch,
   so the test still works.

4. **Why shim-only:** one paragraph plus pointer to
   `aidocs/packaging_strategy.md` for the full rationale.

### 3. Create the reusable packaging workflow

`.github/workflows/release-packaging.yml` (new):

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
      TAP_TOKEN: ${{ secrets.HOMEBREW_TAP_TOKEN }}
    steps:
      - name: Soft-skip if HOMEBREW_TAP_TOKEN is not set
        id: gate
        run: |
          if [ -z "${TAP_TOKEN}" ]; then
            echo "::warning::HOMEBREW_TAP_TOKEN not set — skipping Homebrew tap publish."
            echo "::warning::See aidocs/homebrew_maintainer_setup.md for first-time setup."
            echo "skip=true" >> "$GITHUB_OUTPUT"
          else
            echo "skip=false" >> "$GITHUB_OUTPUT"
          fi

      - uses: actions/checkout@v4
        if: steps.gate.outputs.skip == 'false'

      - name: Download shim from release & compute SHA256
        if: steps.gate.outputs.skip == 'false'
        id: checksum
        run: |
          curl -fsSL "https://github.com/beyondeye/aitasks/releases/download/v${VERSION}/ait" -o ait
          SHA256=$(sha256sum ait | cut -d' ' -f1)
          echo "sha256=$SHA256" >> "$GITHUB_OUTPUT"
          echo "Shim SHA256: $SHA256"

      - name: Render formula
        if: steps.gate.outputs.skip == 'false'
        run: |
          mkdir -p tap-out
          sed -e "s/VERSION_PLACEHOLDER/${VERSION}/g" \
              -e "s/SHA256_PLACEHOLDER/${{ steps.checksum.outputs.sha256 }}/g" \
              packaging/homebrew/aitasks.rb.template > tap-out/aitasks.rb
          echo "--- Rendered formula ---"
          cat tap-out/aitasks.rb

      - name: Push to tap repo
        if: steps.gate.outputs.skip == 'false'
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

Key points:

- `secrets: inherit` will be used at the caller side (in `release.yml`'s
  `packaging` job) so `HOMEBREW_TAP_TOKEN` flows through to this reusable
  workflow.
- **Soft-skip guard.** The `gate` step inspects `secrets.HOMEBREW_TAP_TOKEN`
  via the `env:` mapping (secrets cannot be referenced directly in `if:`
  conditions, only via `env`). If the secret is empty/unset, the job emits
  GitHub Actions `::warning::` annotations and all subsequent steps are
  skipped via `if: steps.gate.outputs.skip == 'false'` — the job exits 0
  (green) so the workflow run does not show red on tags cut before the
  one-time maintainer setup completes. Once the secret is set, future tags
  publish normally without changes here.
- Idempotency via `git diff --cached --quiet`: re-running the same tag does
  not produce empty commits in the tap repo.
- Sibling-friendly: future PMs in t623_3/4/5 will add `publish-aur`,
  `build-deb` / `test-deb`, `build-rpm` / `test-rpm` jobs alongside
  `publish-homebrew` in this same file. They will all consume `inputs.version`.
  Note: t623_3 (AUR) will need its own secret-presence soft-skip guard
  (`AUR_SSH_PRIVATE_KEY` etc.); the pattern from this job is reusable.

### 4. Wire the packaging workflow into the release workflow

Modify `.github/workflows/release.yml`:

**4a. Add a `plan` job at the top** that extracts the version once and exposes
it as a job-level output:

```yaml
jobs:
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

**4b. Make the existing `release` job depend on `plan` and consume its
output** for the verify-version step:

```yaml
  release:
    needs: plan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Verify VERSION file matches tag
        run: |
          file_version=$(cat .aitask-scripts/VERSION)
          tag_version="${{ needs.plan.outputs.version }}"
          if [ "$file_version" != "$tag_version" ]; then
            echo "ERROR: VERSION file ($file_version) does not match tag ($tag_version)"
            exit 1
          fi

      # ... (remaining steps unchanged: skills/codex/opencode/gemini directory
      #     builds, tarball creation, changelog extraction, both
      #     softprops/action-gh-release steps using ${{ github.ref_name }}
      #     for the tag — those uses of github.ref_name remain correct)
```

The existing inline `steps.version` step (lines 17-19) is removed since the
`plan` job now provides it.

**4c. Add a `packaging` job at the end** that calls the reusable workflow:

```yaml
  packaging:
    needs: [plan, release]
    uses: ./.github/workflows/release-packaging.yml
    secrets: inherit
    with:
      version: ${{ needs.plan.outputs.version }}
```

Why `needs: [plan, release]`: `plan` for the version output, `release` so the
packaging job runs only after the GitHub Release (and its `ait` asset) is
live and the `curl` in `release-packaging.yml` will succeed.

### 5. Validate workflow YAML

Run a YAML syntax check + actionlint where available:

```bash
# YAML lint (built-in to Python — no install needed)
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release-packaging.yml'))"
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"

# actionlint (optional, only if installed)
command -v actionlint && actionlint .github/workflows/release-packaging.yml .github/workflows/release.yml || \
  echo "actionlint not installed — skipping (CI will catch any issues)"
```

Fix any errors. `actionlint` warnings about expression context are acceptable
when they refer to `secrets.*` (which are resolved at workflow time).

## Verification Checklist

**Automated, runs locally without releasing:**

- [ ] `aidocs/homebrew_maintainer_setup.md` exists, covers all 7 required sections from Step 0.
- [ ] `packaging/homebrew/aitasks.rb.template` exists.
- [ ] `packaging/homebrew/README.md` exists, covers all 4 required sections from Step 2 and points at `aidocs/homebrew_maintainer_setup.md`.
- [ ] `.github/workflows/release-packaging.yml` exists, parses as valid YAML, includes the soft-skip `gate` step.
- [ ] `.github/workflows/release.yml` parses as valid YAML and contains a `plan` job, `release: needs: plan`, and a `packaging` job at the end.
- [ ] `python3 -c "import yaml; ..."` (Step 5) succeeds for both workflow files.
- [ ] (Optional) `actionlint` clean if installed.
- [ ] Render the formula with a placeholder substitution and verify Ruby syntax:
  ```bash
  sed -e 's/VERSION_PLACEHOLDER/0.0.0/g' -e 's/SHA256_PLACEHOLDER/0000000000000000000000000000000000000000000000000000000000000000/g' \
      packaging/homebrew/aitasks.rb.template > /tmp/aitasks-test.rb
  ruby -c /tmp/aitasks-test.rb   # expect: "Syntax OK"
  rm /tmp/aitasks-test.rb
  ```

**Manual, deferred to t623_7 (manual verification task):**

- [ ] Local formula install on macOS: `brew install --build-from-source /tmp/aitasks.rb` succeeds; `brew test aitasks` passes.
- [ ] `which ait` after `brew install` points at `$(brew --prefix)/bin/ait`; `ait setup` in a fresh empty git repo bootstraps successfully.
- [ ] After tagging a prerelease (`v0.17.1-rc.1` or similar), the tap repo at `beyondeye/homebrew-aitasks` receives a commit within 2 min.
- [ ] Subsequent re-runs of the same tag produce no duplicate empty commits in the tap repo (idempotency).

## Out of scope

- Implementing AUR / .deb / .rpm packaging — those are t623_3 / t623_4 / t623_5,
  each adding sibling jobs to `.github/workflows/release-packaging.yml`.
- Updating user docs / website — t623_6.
- Hash-based skip-if-unchanged for the tap-bump CI — listed as a deferred
  follow-up in `aidocs/packaging_strategy.md`.
- Manual maintainer steps (creating the tap repo, provisioning
  `HOMEBREW_TAP_TOKEN`) — those are documented in
  `packaging/homebrew/README.md` (Step 2) but executed by the maintainer
  outside this task.

## Final Implementation Notes

- **Actual work done:** All five plan deliverables landed:
  1. `aidocs/homebrew_maintainer_setup.md` (new) — comprehensive 6-section
     first-time-setup walkthrough: tap concepts, repo creation,
     `HOMEBREW_TAP_TOKEN` PAT provisioning (fine-grained, scoped to the
     tap repo only), end-to-end local test snippet on macOS, first-real-release
     procedure, troubleshooting table.
  2. `packaging/homebrew/aitasks.rb.template` (new) — Ruby formula
     template with `VERSION_PLACEHOLDER` / `SHA256_PLACEHOLDER` markers,
     `python@3.12` + `bash` + `fzf` + `jq` + `git` + `zstd` + `curl` deps,
     `bin.install "ait"`, and a `test do` block asserting the shim's
     no-project error message.
  3. `packaging/homebrew/README.md` (new) — slim directory-level reference
     pointing at `aidocs/homebrew_maintainer_setup.md` for first-time
     setup, plus the local-test snippet (which uses the LOCAL shim file
     and LOCAL VERSION rather than a hypothetical release asset).
  4. `.github/workflows/release-packaging.yml` (new) — reusable
     `workflow_call` workflow with one `publish-homebrew` job. Includes a
     soft-skip `gate` step that warns and exits 0 when
     `HOMEBREW_TAP_TOKEN` is unset (so first releases after this task
     lands don't show a red workflow run before the maintainer manual
     prerequisites are met). Idempotent: `git diff --cached --quiet`
     prevents empty no-op commits in the tap repo on re-runs.
  5. `.github/workflows/release.yml` (modified) — extracted version
     extraction into a new `plan` job, made the existing `release` job
     `needs: plan` and consume `${{ needs.plan.outputs.version }}`, and
     added a final `packaging: needs: [plan, release]` job that calls
     `release-packaging.yml` with `secrets: inherit` and `version:` input.

- **Deviations from plan:** None. The plan was already verified against the
  live codebase before implementation began (see "Plan Verification" section
  near the top of this file) and executed as written.

- **Issues encountered:** None. Static validation passed:
  - `python3 -c "import yaml; yaml.safe_load(...)"` succeeded for both
    `release-packaging.yml` and `release.yml`.
  - `ruby -c` on the rendered formula (with placeholder substitution)
    returned `Syntax OK`.
  - `actionlint` not installed locally — deferred to GitHub Actions'
    built-in workflow validator on the next push.

- **Key decisions:**
  - **Soft-skip guard via env-mapped secret + step-output `if:`.** GitHub
    Actions does not allow secrets in `if:` expressions directly, so the
    pattern is: bind `TAP_TOKEN: ${{ secrets.HOMEBREW_TAP_TOKEN }}` at
    the job's `env:`, then a first `gate` step inspects `${TAP_TOKEN}`
    and writes `skip=true|false` to `$GITHUB_OUTPUT`, and every
    subsequent step has `if: steps.gate.outputs.skip == 'false'`. This
    is the canonical idiom for "skip this job if a secret is missing
    without failing the workflow" and is reusable for sibling PMs (t623_3
    AUR will need the same pattern for `AUR_SSH_PRIVATE_KEY`).
  - **`packaging: needs: [plan, release]` not just `needs: release`.**
    Both deps are real: `release` so the GitHub Release (and its `ait`
    asset) is published before `release-packaging.yml`'s `curl` runs;
    `plan` so the `version` output is in scope without redundant
    re-extraction.
  - **Maintainer doc lives in `aidocs/`, not in `packaging/homebrew/`.**
    `packaging/homebrew/README.md` is a directory-level reference (what
    these files are, where they're used) and
    `aidocs/homebrew_maintainer_setup.md` is the first-time-setup
    walkthrough. They cross-reference. Pulled this apart in response to
    user feedback during planning ("can you write instructions on how to
    do it in aidocs?"). The walkthrough format is a heavy how-to with
    troubleshooting; the directory README stays light.
  - **Local-test snippet uses the LOCAL shim file**, not the GitHub
    release asset URL. Maintainers can validate the formula template on
    a workstation without needing a release to already exist —
    `brew install --build-from-source` against a local file path bypasses
    the URL fetch even though the formula's `url` field points at a
    non-existent release asset. Only the formula code (deps, install,
    test) is exercised, not the URL-fetch path. Documented this behavior
    in `packaging/homebrew/README.md` so it isn't surprising.
  - **Bare `license "Apache-2.0"`** kept in the formula even though the
    actual `LICENSE` is "Apache-2.0 with Commons Clause restriction".
    Homebrew has no first-class representation for non-OSI restrictions
    like Commons Clause; the strategy doc itself uses "Apache-2.0"
    loosely. If `brew audit` rejects this on the live tap, can be
    revisited (`license :cannot_represent` or a custom expression).

- **Upstream defects identified:** None.

- **Notes for sibling tasks:** (every later child reads this)
  - **`needs.plan.outputs.version` is the canonical version source.**
    t623_3/4/5 must consume `${{ needs.plan.outputs.version }}` — do NOT
    re-extract from `GITHUB_REF_NAME` independently. The `plan` job
    exists precisely so the version computation is single-sourced
    across all packaging jobs.
  - **`release-packaging.yml`'s `inputs.version` is the canonical input
    contract.** When t623_3 (AUR), t623_4 (deb), t623_5 (rpm) each add a
    new sibling job to `release-packaging.yml`, they consume
    `${{ inputs.version }}` from the workflow_call inputs — they should
    NOT add new top-level inputs unless genuinely needed. This keeps
    the contract between `release.yml`'s `packaging:` step and the
    reusable workflow stable.
  - **Soft-skip guard pattern is reusable.** t623_3 should mirror the
    `gate` step structure for `AUR_SSH_PRIVATE_KEY` / `AUR_USERNAME` /
    `AUR_EMAIL`; t623_4/t623_5 don't need a guard (they only use the
    default `GITHUB_TOKEN` for the initial release-attached-package
    phase, per the strategy doc).
  - **`packaging:` calls a reusable workflow** (`uses:`), not a job that
    runs steps directly. This is intentional — keeps each PM's
    publishing logic in `release-packaging.yml` and the top-level
    `release.yml` short. Sibling PRs add new jobs INSIDE
    `release-packaging.yml`, not new jobs in `release.yml`.
  - **Tap-repo placeholder formula**: documented in
    `aidocs/homebrew_maintainer_setup.md` §2 step 4. Maintainer must
    create `homebrew-aitasks` repo with a placeholder `Formula/aitasks.rb`
    (a Ruby class that `odie`s) before the first release auto-bump runs;
    otherwise `brew tap beyondeye/aitasks` errors out before the first
    auto-bump publishes the real formula.
  - **Formula `test do` block asserts** `/No ait project found/`. If the
    shim's no-project error message ever changes in `packaging/shim/ait`,
    the formula template's `test do` regex must be updated in lockstep
    (otherwise `brew test aitasks` will start failing on the tap CI).
  - **Manual verification deferred to t623_7.** End-to-end live testing
    (tag a real release, watch the workflow fire, verify the tap repo
    receives a commit, install via `brew tap … && brew install`) is
    explicitly out of scope here and is covered by the t623_7 manual
    verification sibling. Do not attempt live verification as part of
    t623_3/4/5 either — t623_7 is the single point of truth.
