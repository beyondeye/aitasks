---
Task: t623_more_installation_methods.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
---

# Plan: Add more installation methods for the aitasks framework

## Context

**Problem.** Currently the only supported install is `curl -fsSL .../install.sh | bash`. This is friction-heavy for users who manage their toolchain with standard package managers (Homebrew on macOS, AUR on Arch, apt on Debian/Ubuntu/WSL, dnf on Fedora/RHEL). Adoption, discoverability, and upgrade hygiene all suffer.

**Goal.** Add four additional install channels (Homebrew, AUR, `.deb`, `.rpm`) with automated release-publishing. Update the README + website to document them.

**Scope confirmed (via AskUserQuestion):** Homebrew, Arch AUR, Debian/Ubuntu `.deb`, Fedora/RHEL `.rpm`. WSL is covered by the `.deb` channel.

**Packaging model (confirmed via AskUserQuestion — user's insight):** **shim-only**. Each PM ships only the ~87-line global shim (the body of `install_global_shim()` in `.aitask-scripts/aitask_setup.sh:555-648`, extracted as a standalone script). The shim walks up the directory tree looking for a project-local `ait`; if none and the user runs `ait setup`, it bootstrap-downloads the current `install.sh` from GitHub `main`, which downloads the latest release tarball.

**Why shim-only:** decouples framework release cadence from PM release cadence. The shim barely changes, so PMs only need a version bump when the shim **logic** changes — not on every framework release. Framework releases can ship 5× per week without touching any PM. CI is dramatically simpler. Trade-offs accepted: no offline install via PMs; PM version labels become symbolic after the first publish.

**Non-goals.**
- No nix / scoop / chocolatey / snap / flatpak (deferred).
- No bundling of `.aitask-scripts/`, `skills/`, or `seed/` into PM packages.
- No changes to `install.sh` or `aitask_setup.sh` beyond possibly extracting the shim heredoc into a standalone file.
- No APT/RPM repo hosting (direct `.deb`/`.rpm` asset download from GitHub releases only; repo hosting deferred).

**Reference implementation consulted.** [`sinelaw/fresh/.github/workflows/`](https://github.com/sinelaw/fresh/tree/master/.github/workflows). Patterns adopted: reusable `workflow_call` workflows (`linux-packages.yml`, `aur-publish.yml`); AUR publish via `KSXGitHub/github-actions-deploy-aur@v4.1.2`; PKGBUILD template with `VERSION_PLACEHOLDER` / `SHA256_PLACEHOLDER` substitution. We diverge from `fresh` on two points: (a) we use `nfpm` instead of `cargo-deb`/`cargo-generate-rpm` since we ship shell + Python, no compile step; (b) install-test matrices are narrower because we only need to verify a shell-script shim runs — not a binary.

## Why this task must be decomposed

Each package manager is an independent stream of work (different manifest format, different CI integration, different end-user docs). Doing them in one commit would produce a large unreviewable PR. Also, the packaging decisions (shim-only, CI structure, `aitask_setup.sh` extraction point) need to be recorded once in a strategy doc so later children don't re-litigate.

Decomposition rule: **one packaging channel = one child**, bracketed by a design spike + docs consolidation + manual-verification aggregate sibling.

---

## Child task breakdown

Parent task `t623` decomposes into **6 implementation children**, plus **1 manual-verification aggregate sibling**.

---

### t623_1 — Packaging strategy, shim extraction & design spike

**Purpose.** Produce `aidocs/packaging_strategy.md` + extract the shim into a standalone script. This is the only cross-cutting child; all others are orthogonal packaging streams that reference this one.

**Deliverables:**

1. **`aidocs/packaging_strategy.md`** documenting:
   - The shim-only decision and its rationale (release-cycle decoupling).
   - Per-PM manifest skeletons showing only shim + deps declaration.
   - Required GitHub Actions secrets: `HOMEBREW_TAP_TOKEN`, `AUR_USERNAME`, `AUR_EMAIL`, `AUR_SSH_PRIVATE_KEY`. Maintainer must add these **before** merging t623_2/t623_3 — otherwise CI fails silently on the first tag.
   - Dependency name mapping table per PM (Arch `python` vs Debian `python3` vs Fedora `python3`; `github-cli` package names per PM; etc.). Source of truth for every child's manifest.
   - Version strategy: `.aitask-scripts/VERSION` remains canonical. PM packages consume it on every release. Users asking for a specific version via PM get a shim whose behavior is identical across versions — documented prominently in each PM's doc page.
   - Release-cadence policy: all four PMs bump on every tag even if the shim file hash is unchanged, to keep users informed of availability. CI could skip re-publish if shim hash unchanged (optimization deferred).
   - Required secret provisioning runbook (step-by-step gh-secret-set commands + SSH key generation for AUR).

2. **Shim extraction.** Extract the heredoc body from `.aitask-scripts/aitask_setup.sh:560-648` (lines between `<< 'SHIM'` and `SHIM`) into a standalone file at `packaging/shim/ait` (or similar path decided in the spike). Modify `install_global_shim()` to `cat` from that file instead of inlining. This makes the shim the single source of truth consumed by both `install.sh` flow AND every PM package.

**Files touched:**

- `aidocs/packaging_strategy.md` (new)
- `packaging/shim/ait` (new — extracted standalone)
- `.aitask-scripts/aitask_setup.sh` (modified — `install_global_shim()` now reads from `packaging/shim/ait` instead of heredoc)
- `.github/workflows/release.yml` (modified — include `packaging/shim/ait` in the tarball so `install.sh` can find it post-extraction)
- `install.sh` (modified if extracting the shim breaks `install_global_shim()`'s access to it during bootstrap — the spike determines the exact patch, e.g., copy `packaging/shim/ait` to a known path during `install.sh` flow so the setup script can find it). **Critical check:** don't break the curl-install path.

**Verification:**

- `bash install.sh` on a fresh directory still installs the global shim identically (diff-free when compared to a pre-change install).
- Existing tests in `tests/` still pass.
- The standalone `packaging/shim/ait` script is executable and self-contained — no sourcing of other framework files.

---

### t623_2 — Homebrew tap with CI auto-bump

**Purpose.** Make `brew install beyondeye/aitasks/aitasks` work on macOS and Linuxbrew.

**Approach.**

- Maintainer creates separate repo `beyondeye/homebrew-aitasks` manually (one-time; documented in t623_1 spike).
- In this monorepo:
  - Add `packaging/homebrew/aitasks.rb.template` — Ruby formula template with `VERSION_PLACEHOLDER`, `SHA256_PLACEHOLDER`.
  - Add `packaging/homebrew/README.md` — tap-repo setup instructions.
  - Add `.github/workflows/release-packaging.yml` — reusable `workflow_call` workflow. Its `publish-homebrew` job:
    1. Downloads `aitasks-vX.Y.Z.tar.gz` from the just-published release.
    2. Extracts `packaging/shim/ait` from it; computes SHA256 of the shim file.
    3. Renders the formula template → `Formula/aitasks.rb` with version + shim-file URL + SHA256.
    4. Pushes the rendered formula to `beyondeye/homebrew-aitasks` via `HOMEBREW_TAP_TOKEN` (direct push; tap has no reviewers).
  - Modify `.github/workflows/release.yml` to `uses: ./.github/workflows/release-packaging.yml` after the release is published.
- Formula contents (generated from template, shim-only model):
  - `url "https://github.com/beyondeye/aitasks/releases/download/vX.Y.Z/ait"` — the raw shim file, **not** the tarball. Simplest brew install possible.
  - `sha256 "..."` — of the shim file.
  - `depends_on "bash"`, `"python@3.12"`, `"fzf"`, `"jq"`, `"git"`, `"zstd"`, `"curl"`.
  - `def install`: `bin.install "ait"`. That's it. Three lines.
  - `test do`: `assert_match /No aitasks project found/, shell_output("#{bin}/ait some-command 2>&1", 1)` — verifies the shim runs and emits its expected no-project-found message.
- The release workflow must upload the raw shim file (`packaging/shim/ait`) as a release asset alongside the tarball. Extend the existing `softprops/action-gh-release` files list.

**Files touched:**

- `packaging/homebrew/aitasks.rb.template` (new)
- `packaging/homebrew/README.md` (new)
- `.github/workflows/release-packaging.yml` (new)
- `.github/workflows/release.yml` (modified — `uses:` + extend release-asset list to include the shim file)

**Verification:**

- `brew install --build-from-source ./Formula/aitasks.rb` on macOS (from a local clone of the tap).
- `brew test aitasks` passes.
- Tag a prerelease; within 2 min the tap repo has a new commit with the bumped formula.
- `which ait` after `brew install` resolves to brew's bin dir; `ait setup` in a fresh empty git repo works.

---

### t623_3 — Arch AUR package with CI auto-bump

**Purpose.** Make `yay -S aitasks` (or `paru -S aitasks`) work on Arch/Manjaro.

**Note on `pacman`.** Plain `pacman -S aitasks` will NOT work after this child — the package lives in the AUR, not the official Arch repos, and pacman only installs from configured repos. Arch users install AUR packages via an AUR helper (`yay`, `paru`, `pikaur`) or by cloning + `makepkg -si`. To get true `pacman -S aitasks`, we would need either (a) official Arch repo submission (slow, popularity-gated, separate from this task) or (b) host our own unofficial pacman repo at e.g. `pacman.aitasks.io` that users add to `pacman.conf`. Option (b) is in the same "future extension" tier as hosting our own APT/DNF repos — deferred; documented in t623_1 spike as a follow-up task. The t623_6 docs page must explain this explicitly to Arch users.

**Approach (following `sinelaw/fresh`'s aur-publish.yml pattern exactly):**

- Add `packaging/aur/PKGBUILD.template` with `VERSION_PLACEHOLDER`, `SHA256_PLACEHOLDER`:
  - `pkgname=aitasks`, `pkgver=VERSION_PLACEHOLDER`, `pkgrel=1`, `arch=('any')`.
  - `depends=('bash>=4' 'python>=3.9' 'fzf' 'jq' 'git' 'zstd' 'tar' 'curl')`.
  - `optdepends=('github-cli: GitHub integration' 'glab: GitLab integration')`.
  - `source=("ait::https://github.com/beyondeye/aitasks/releases/download/v$pkgver/ait")` — raw shim file, not tarball.
  - `sha256sums=('SHA256_PLACEHOLDER')`.
  - `package() { install -Dm755 "$srcdir/ait" "$pkgdir/usr/bin/ait"; }` — one line.
- Add a `publish-aur` job to `.github/workflows/release-packaging.yml`:
  1. Download the shim file from the release.
  2. Substitute placeholders in PKGBUILD.template.
  3. Regenerate `.SRCINFO` via `makepkg --printsrcinfo` in an `archlinux:base-devel` container.
  4. Publish via `KSXGitHub/github-actions-deploy-aur@v4.1.2` (exact version used by `fresh`).
- First-time submission: maintainer creates the `aitasks` AUR package page via the AUR web UI before the first tag push. Runbook in t623_1.
- Add `packaging/aur/README.md` documenting SSH key generation + AUR account setup.

**Files touched:**

- `packaging/aur/PKGBUILD.template` (new)
- `packaging/aur/README.md` (new — first-time AUR setup + SSH key runbook)
- `.github/workflows/release-packaging.yml` (modified — adds `publish-aur` job)

**Verification:**

- Local: render PKGBUILD from template with a known version, then `makepkg -si` on an Arch container.
- `namcap PKGBUILD` passes.
- After tagging, AUR receives the commit within 2 minutes.
- `yay -S aitasks` on a fresh Manjaro VM; `ait setup` in a new project works.

---

### t623_4 — Debian/Ubuntu `.deb` (covers WSL)

**Purpose.** Make `sudo apt install ./aitasks_<ver>_all.deb` (downloaded from GitHub releases) work on Debian/Ubuntu, including WSL2 Ubuntu.

**Approach.** Use [`nfpm`](https://nfpm.goreleaser.com/) — single YAML config → both `.deb` and `.rpm`. This child ships `.deb`; t623_5 extends the same config to `.rpm`.

- Add `packaging/nfpm/nfpm.yaml` (shared with t623_5):
  - `name: aitasks`, `arch: all`, `version_schema: semver`.
  - `depends` (deb): `bash (>= 4.0)`, `python3 (>= 3.9)`, `fzf`, `jq`, `git`, `zstd`, `tar`, `curl`.
  - `recommends`: `gh | glab | bkt`.
  - `contents:` — shim only: `src: ./packaging/shim/ait`, `dst: /usr/bin/ait`, `file_info: { mode: 0755 }`.
  - `scripts.postinstall:` — print "Run `ait setup` in your project to bootstrap." That's it.
  - No postremove script needed (dpkg removes files on uninstall).
- Add `build-deb` job to `.github/workflows/release-packaging.yml`:
  1. Install nfpm via `goreleaser/nfpm-action@v4` (pinned).
  2. Read version from `needs.plan.outputs.version`.
  3. `nfpm package --packager deb --target aitasks_${VERSION}_all.deb --config packaging/nfpm/nfpm.yaml`.
  4. Upload as GitHub release asset via `gh release upload`.
- Add `test-deb` job (matrix: `ubuntu:22.04`, `ubuntu:24.04`, `debian:12`): install `.deb`, run `ait setup` in `/tmp/testproj` (after `git init`), verify it completes, uninstall, verify `/usr/bin/ait` is gone.

**WSL notes (in t623_6 docs):**

- `dpkg -i` inside WSL2 Ubuntu works identically. No special flags.
- Future: APT repo at `apt.aitasks.io` — out of scope for this task.

**Files touched:**

- `packaging/nfpm/nfpm.yaml` (new — shared with t623_5)
- `.github/workflows/release-packaging.yml` (modified — adds `build-deb` + `test-deb` jobs)

**Verification:**

- Local: `nfpm package --packager deb --config packaging/nfpm/nfpm.yaml` produces a valid `.deb`.
- CI matrix passes on ubuntu:22.04, ubuntu:24.04, debian:12.
- `lintian aitasks_*_all.deb` — warnings triaged and documented; errors must be zero.
- Tagged release has `aitasks_X.Y.Z_all.deb` asset.
- Manual: WSL2 Ubuntu 24.04 install + `ait setup` works.

---

### t623_5 — Fedora/RHEL `.rpm`

**Purpose.** Make `sudo dnf install aitasks-<ver>-1.noarch.rpm` (downloaded from GitHub releases) work on Fedora 40+, Rocky Linux 9, Alma, RHEL.

**Approach.** Extend `packaging/nfpm/nfpm.yaml` with RPM-specific overrides. Same shim, same single-file content list.

- Extend `packaging/nfpm/nfpm.yaml` with `overrides.rpm`:
  - `depends`: `bash >= 4.0`, `python3 >= 3.9`, `fzf`, `jq`, `git`, `zstd`, `tar`, `curl` (Fedora names happen to match).
  - `recommends`: `gh`, `glab` (Fedora package names).
- Add `build-rpm` job to `.github/workflows/release-packaging.yml` (mirror of `build-deb`):
  - `nfpm package --packager rpm --target aitasks-${VERSION}-1.noarch.rpm`.
  - `gh release upload`.
- Add `test-rpm` job (matrix: `fedora:40`, `fedora:41`, `rockylinux:9`): same verification shape as `test-deb`.

**Files touched:**

- `packaging/nfpm/nfpm.yaml` (modified — adds rpm overrides)
- `.github/workflows/release-packaging.yml` (modified — adds `build-rpm` + `test-rpm` jobs)

**Verification:**

- Local: `nfpm package --packager rpm --config packaging/nfpm/nfpm.yaml` produces a valid `.rpm`.
- `rpmlint aitasks-*.rpm` — warnings triaged; errors zero.
- CI matrix passes on all three distros.
- Tagged release has `aitasks-X.Y.Z-1.noarch.rpm` asset.

---

### t623_6 — Documentation consolidation

Depends on t623_2..t623_5 merged so the commands being documented actually work.

**Files touched:**

- `README.md` — rewrite Quick Install section into per-platform table. For each row (macOS, Arch, Debian/Ubuntu/WSL, Fedora/RHEL, Other Linux) show: primary PM command + curl fallback. Emphasize: PM install gives you the shim; `ait setup` in your project bootstraps the framework (same as curl).
- `website/content/docs/installation/_index.md` — mirror the README table; link to per-platform sub-pages.
- `website/content/docs/installation/macos-brew.md` (new) — Homebrew walkthrough: tap setup, install, upgrade, uninstall.
- `website/content/docs/installation/arch-aur.md` (new) — AUR walkthrough: `yay`/`paru` install, upgrade, uninstall. **Must include explicit note** that plain `pacman -S aitasks` does NOT work (AUR vs official repos) and show the `makepkg -si` alternative for users who don't have an AUR helper.
- `website/content/docs/installation/debian-apt.md` (new) — `.deb` walkthrough + WSL notes + uninstall.
- `website/content/docs/installation/fedora-dnf.md` (new) — `.rpm` walkthrough + uninstall.
- `website/content/docs/installation/windows-wsl.md` — update to prefer `.deb` over curl inside WSL.
- **Important docs note:** each PM page must explain the shim-only model clearly: "`brew install aitasks` (or equivalent) installs only the aitasks global shim. The framework itself is downloaded on demand when you run `ait setup` in your project." This prevents confusion about "why is my brew-installed aitasks the same size regardless of version?"

Follow the project's documentation convention: current state only, no version-history prose.

**Verification:**

- `cd website && ./serve.sh`; click through each new page.
- Grep `README.md` + `website/` for `curl -fsSL` — confirm it's now documented as a fallback, not the only option.
- Each per-platform page has: install command, `ait setup` next-step, upgrade, uninstall.

---

### t623_7 (manual-verification aggregate sibling — offered after children are written)

Created via `aitask_create_manual_verification.sh` with `--verifies 623_2,623_3,623_4,623_5,623_6`. Checklist seeded from each child's "Verification" section:

- `[t623_2] brew install beyondeye/aitasks/aitasks` on macOS → `ait setup` in fresh repo → create task t1 → archive.
- `[t623_2] brew test aitasks` passes.
- `[t623_2] Homebrew tap repo receives bump commit within 2 min of release tag.`
- `[t623_3] yay -S aitasks` on Manjaro VM → `ait setup` → create+archive task.
- `[t623_3] makepkg -si` on clean Arch container; `namcap PKGBUILD` clean.
- `[t623_3] AUR page updated within 2 min of release tag.`
- `[t623_4] sudo apt install ./aitasks_*_all.deb` on Debian 12 → `ait setup` → create+archive task.
- `[t623_4] sudo apt install ./aitasks_*_all.deb` inside WSL2 Ubuntu 24.04.
- `[t623_4] lintian clean on .deb.`
- `[t623_5] sudo dnf install aitasks-*.noarch.rpm` on Fedora 40 → `ait setup` → create+archive task.
- `[t623_5] sudo dnf install aitasks-*.noarch.rpm` on Rocky Linux 9.
- `[t623_5] rpmlint clean on .rpm.`
- `[t623_6] README.md renders correctly on GitHub`; every website page loads.
- `[t623_6] Each per-platform page mentions the shim-only model explicitly.`
- `[Cross-PM upgrade sanity]` install via each PM, then trigger a release; verify each PM's channel gets the new version automatically.

---

## Child task creation commands (for execution phase)

After this plan is approved, the parent-task planning flow will (per `planning.md` "Child Task Documentation Requirements"):

1. For each of t623_1..t623_6: `aitask_create.sh --batch --parent 623 --name <name> --issue-type <type> --priority <pri> --effort <effort> --desc-file ...` with full per-child context (Context / Key Files / Reference Files / Implementation Plan / Verification Steps).
2. Write each child's initial plan file at `aiplans/p623/p623_<N>_<name>.md`.
3. `./ait git add aiplans/p623/ && ./ait git commit -m "ait: Add t623 child implementation plans"`.
4. Revert parent `t623` to `status: Ready` and clear `assigned_to`.
5. Release parent lock.
6. Offer the manual-verification aggregate sibling (`aitask_create_manual_verification.sh --parent 623 --verifies 623_2,623_3,623_4,623_5,623_6 ...`).
7. Present child checkpoint: "Start first child" / "Stop here".

## Reference to Step 9

Per `task-workflow/SKILL.md`, after all children merge + archive:

- Parent auto-archives once `children_to_implement` is empty.
- `release.yml` unchanged in its tarball-building behavior; `release-packaging.yml` (added in t623_2, extended in t623_3/4/5) fans out from the same tag event.

## Critical files referenced

- `.aitask-scripts/aitask_setup.sh` (lines 555–648 `install_global_shim()`) — source of the shim body that t623_1 extracts to `packaging/shim/ait`. Also source of the dependency list for every PM's manifest (lines 104–303, 500–510).
- `.github/workflows/release.yml` (lines 96–110 tarball contents; lines 133–145 release creation) — extension points for t623_1 (include shim asset) and t623_2 (invoke packaging workflow).
- `install.sh` — should stay largely unchanged; t623_1 verifies the shim extraction doesn't break its curl-install path.
- `create_new_release.sh` — unchanged; packaging jobs trigger off the tag it pushes.
- `.aitask-scripts/VERSION` — single source of truth for version in every PM's manifest.
- `website/content/docs/installation/_index.md` — top of the docs tree that t623_6 rewrites.
- **External reference:** [`sinelaw/fresh/.github/workflows/linux-packages.yml`](https://github.com/sinelaw/fresh/blob/master/.github/workflows/linux-packages.yml), [`aur-publish.yml`](https://github.com/sinelaw/fresh/blob/master/.github/workflows/aur-publish.yml).

## Risks & mitigations

- **Secrets management.** `HOMEBREW_TAP_TOKEN`, `AUR_SSH_PRIVATE_KEY`, `AUR_USERNAME`, `AUR_EMAIL` must be added to repo secrets **before** merging t623_2/t623_3. t623_1's runbook makes this explicit. Without them, CI jobs fail silently on the first tag.
- **First-time AUR submission.** Needs a human to create the `aitasks` AUR package page via the web UI. t623_1 documents; t623_3 flags as blocking prereq.
- **Shim extraction regression.** The heredoc-to-file refactor in t623_1 is the riskiest change (touches the install path that every existing user goes through). Tests in `tests/` should include a "install script produces identical shim content before/after refactor" check. Golden-file comparison.
- **Release asset URL stability.** All four PMs reference `https://github.com/beyondeye/aitasks/releases/download/vX.Y.Z/ait` — GitHub's URL scheme is stable, but the release workflow must upload that exact filename. t623_1 lists this as a hard requirement of the modified `release.yml`.
- **`.deb`/`.rpm` dep version pins.** `python3 (>= 3.9)` works on Debian 12, Ubuntu 22.04+, Fedora 40+, Rocky 9. Ubuntu 20.04 (3.8) and Debian 11 are on the edge — document support matrix in t623_6.

## Verification (end-to-end, for the parent as a whole)

After all 7 children merge:

1. Bump version to e.g. `0.18.0`; push `v0.18.0` tag.
2. Watch `release.yml` → `release-packaging.yml`: 4 publish jobs pass, 4 test-install matrices pass.
3. Check:
   - Homebrew tap repo has a new commit with the bumped formula.
   - AUR page shows the new `pkgver`.
   - GitHub release has `ait` (raw shim), `aitasks_X.Y.Z_all.deb`, and `aitasks-X.Y.Z-1.noarch.rpm` assets.
4. On four clean VMs (macOS, Arch, Ubuntu-WSL, Fedora), install via the new channel, verify `which ait` resolves, run `ait setup` in a fresh project, create + archive a task. All four succeed.
5. `curl -fsSL .../install.sh | bash` unchanged on all four.
6. Tag another patch release the same day; verify all four PMs get the new version automatically.
