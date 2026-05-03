# Homebrew Maintainer Setup

This is the comprehensive first-time-setup walkthrough for the project owner
(or maintainer) wiring up the **Homebrew distribution channel** for the
`aitasks` framework. It is meant to be read once, end-to-end, when first
shipping the Homebrew tap.

For day-to-day reference (formula structure, how the CI is wired, where the
template lives) see:

- [`packaging/homebrew/README.md`](../packaging/homebrew/README.md) —
  directory-level reference for the formula template.
- [`aidocs/packaging_strategy.md`](packaging_strategy.md) — cross-PM strategy
  (why we ship a shim only, dependency-name mapping across PMs,
  release-cadence policy).

## 1. What a Homebrew "tap" is

[Homebrew](https://brew.sh) is the dominant package manager on macOS (and
also runs on Linux). Most users install software with
`brew install <pkg>`, which pulls from `homebrew-core`, the canonical
collection of formulas reviewed and merged by the Homebrew project itself.
Getting accepted into `homebrew-core` requires a multi-step review by
Homebrew maintainers — slow, gated, and aimed mostly at stable, widely-used
software.

A **tap** is a third-party formula repository hosted on any Git server
(GitHub, GitLab, etc.). Users add a tap once with `brew tap <owner>/<name>`,
after which `brew install <pkg>` resolves any formula in that tap's
`Formula/` subdirectory. Distribution via tap is fully self-served — no
review, no approval needed — and is the standard way third-party projects
ship Homebrew packages.

For aitasks, the tap is hosted at
**[`github.com/beyondeye/homebrew-aitasks`](https://github.com/beyondeye/homebrew-aitasks)**
(repo to be created in section 2). End-user install becomes:

```bash
brew tap beyondeye/aitasks       # one-time
brew install aitasks             # installs the global `ait` shim
```

The `homebrew-` prefix in the repo name (`homebrew-aitasks`) is a Homebrew
convention — `brew tap beyondeye/aitasks` automatically looks for
`github.com/beyondeye/homebrew-aitasks`. **Do not omit the prefix on the
GitHub repo name** or `brew tap` will fail to discover it.

References:
- <https://docs.brew.sh/Taps>
- <https://docs.brew.sh/How-to-Create-and-Maintain-a-Tap>

## 2. Create the tap repository

Done **once**, by hand, before the first release after this task lands.

1. **Sign in to GitHub** as the `beyondeye` org owner (or as a maintainer
   with repo-create permission on the org).

2. **Create a new public repository** with these settings:
   - Owner: `beyondeye`
   - Repository name: **`homebrew-aitasks`** (the `homebrew-` prefix is
     mandatory — see section 1)
   - Description (suggested): "Homebrew tap for the aitasks framework — auto-bumped on each beyondeye/aitasks release."
   - Visibility: Public
   - Initialize with: README ✓ (Homebrew shows the README on `brew tap`
     errors). License and `.gitignore` are not required.

3. **Clone the new repo locally** and add the `Formula/` subdirectory:

   ```bash
   git clone git@github.com:beyondeye/homebrew-aitasks.git
   cd homebrew-aitasks
   mkdir Formula
   ```

4. **Seed a placeholder formula** at `Formula/aitasks.rb` so
   `brew tap beyondeye/aitasks` does not error before the first auto-bump
   runs:

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

   This Ruby parses correctly, so `brew tap` succeeds; `brew install` would
   fail with the explicit message above (clearer than a SHA256 mismatch).
   The first real release (section 5) will overwrite this file via CI.

5. **Commit and push** to `main`:

   ```bash
   git add Formula/aitasks.rb
   git commit -m "Seed placeholder formula"
   git push origin main
   ```

## 3. Provision the `HOMEBREW_TAP_TOKEN` secret

The `publish-homebrew` CI job in
`.github/workflows/release-packaging.yml` needs a credential to push to
the tap repo. Use a **fine-grained** Personal Access Token (PAT) scoped
narrowly to the tap repo only — not a classic PAT with broad `repo` scope.

1. **Generate the PAT.** Visit
   <https://github.com/settings/personal-access-tokens/new> and fill in:

   | Field | Value |
   |---|---|
   | Token name | `aitasks-homebrew-tap-bot` |
   | Expiration | 1 year (set a calendar reminder for renewal — see section 6) |
   | Resource owner | `beyondeye` |
   | Repository access | "Only select repositories" → choose `beyondeye/homebrew-aitasks` |
   | Repository permissions → Contents | **Read and write** |
   | Repository permissions → Metadata | Read-only (auto-selected) |

   Click "Generate token". **Copy the token text immediately** — it is shown
   only once. Save it to a password manager.

2. **Set the secret on the source repo.** Run from any terminal where you
   are signed in to `gh`:

   ```bash
   gh secret set HOMEBREW_TAP_TOKEN --repo beyondeye/aitasks
   ```

   Paste the token at the prompt. `gh` encrypts and uploads it.

3. **Verify the secret is in place:**

   ```bash
   gh secret list --repo beyondeye/aitasks
   ```

   The output should include a row for `HOMEBREW_TAP_TOKEN` with a recent
   `Updated` timestamp.

## 4. End-to-end local test on macOS

Before tagging the first real release, sanity-check the formula on a
**macOS workstation** (this section requires Homebrew installed locally —
Linux machines cannot run `brew test`'s sandbox the same way).

```bash
# Pick the latest released aitasks version
VERSION=$(curl -fsSL https://api.github.com/repos/beyondeye/aitasks/releases/latest \
  | jq -r .tag_name | sed 's/^v//')
echo "Testing with v${VERSION}"

# Compute the shim's SHA256 from the release asset
SHA256=$(curl -fsSL "https://github.com/beyondeye/aitasks/releases/download/v${VERSION}/ait" \
  | shasum -a 256 | cut -d' ' -f1)
echo "Shim SHA256: ${SHA256}"

# Render the template into a working formula
sed -e "s/VERSION_PLACEHOLDER/${VERSION}/g" \
    -e "s/SHA256_PLACEHOLDER/${SHA256}/g" \
    packaging/homebrew/aitasks.rb.template > /tmp/aitasks.rb

# Build, install, and run the formula's test
brew install --build-from-source /tmp/aitasks.rb
brew test aitasks

# Sanity checks
which ait              # → $(brew --prefix)/bin/ait
ait setup              # in a fresh empty git repo: bootstraps successfully
```

**Notes:**

- `shasum -a 256` is the BSD form on macOS. CI uses `sha256sum` (GNU/Linux)
  because GitHub Actions runners are Ubuntu-based. Both produce identical
  hex output.
- `brew test aitasks` runs the formula's `test do` block, which invokes
  `ait` with a bogus subcommand and asserts the output matches
  `/No ait project found/`. Expected exit: 0 (test passed). If the shim's
  no-project error message ever changes, the formula's `test do` regex
  must be updated — see Troubleshooting in section 6.
- `python@3.12` is the Homebrew dependency — Homebrew installs a separate
  copy of Python 3.12 even if the user has another Python from `pyenv` /
  system / etc. To switch the formula to a newer Python (e.g.
  `python@3.13`), edit `packaging/homebrew/aitasks.rb.template` directly;
  Homebrew formulas can declare only one `python@N.M` as a hard dependency.
- After testing, uninstall: `brew uninstall aitasks`. The next section
  re-installs from the real tap.

## 5. Cut the first real release

After sections 2-4 are complete:

1. **Bump VERSION and tag a release** on `beyondeye/aitasks`:

   ```bash
   # Bump .aitask-scripts/VERSION (e.g., from 0.19.2 → 0.19.3)
   echo "0.19.3" > .aitask-scripts/VERSION
   git add .aitask-scripts/VERSION
   git commit -m "chore: Bump version to 0.19.3"
   git push
   git tag v0.19.3
   git push origin v0.19.3
   ```

2. **Watch the GitHub Actions run** at
   <https://github.com/beyondeye/aitasks/actions>. The job graph fires:
   `plan` → `release` → `packaging` (calling
   `release-packaging.yml`'s `publish-homebrew`).

3. **Verify the tap repo** received the new formula:

   ```bash
   git -C /tmp clone --depth 1 https://github.com/beyondeye/homebrew-aitasks.git tap-check
   cat tap-check/Formula/aitasks.rb
   ```

   The placeholder `odie "Placeholder formula …"` should be gone, replaced
   by the real `bin.install "ait"` formula with the new version and SHA.

4. **Verify end-user install** works (on a macOS box):

   ```bash
   brew untap beyondeye/aitasks 2>/dev/null   # ignore error if not previously tapped
   brew tap beyondeye/aitasks
   brew install aitasks
   ait setup                                  # in a fresh empty git repo
   ```

## 6. Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `packaging` job fails with `403 Forbidden` on `git push` | PAT lacks "Contents: Read and write" on the tap repo. Re-issue the token (section 3) with the correct permissions and update the secret. |
| `packaging` job fails with `404 Not Found` on `git clone` | Tap repo doesn't exist or PAT is not scoped to it. Confirm `beyondeye/homebrew-aitasks` exists and the PAT's "Repository access" lists that exact repo. |
| `packaging` job is **skipped** with annotation "HOMEBREW_TAP_TOKEN not set — skipping Homebrew tap publish" | This is the soft-skip guard. The `release` job succeeded; only the Homebrew publish was skipped because the secret is empty/unset. Set the secret (section 3) — next tag will publish. |
| User reports `brew install` fails with `unknown sha256` | The shim file the user downloaded does not match the SHA256 baked into the formula. Most likely cause: the release asset was re-uploaded after the formula was rendered. Re-tag the release to re-run the `publish-homebrew` job. |
| `brew test aitasks` fails with no match for `/No ait project found/` | The shim's no-project error message changed in `packaging/shim/ait`. Update the `test do` block in `packaging/homebrew/aitasks.rb.template` to match the new message wording. |
| Token expiration approaching (you set a 1-year expiry in section 3) | Generate a fresh PAT with the same name and permissions, then re-run `gh secret set HOMEBREW_TAP_TOKEN --repo beyondeye/aitasks` to overwrite the old value. |
| Need to remove the tap from a user's machine for testing | `brew untap beyondeye/aitasks` (this also `brew uninstall`s any installed formulas from the tap). |
