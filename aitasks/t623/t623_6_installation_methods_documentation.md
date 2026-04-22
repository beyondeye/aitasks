---
priority: medium
effort: medium
depends: [t623_5]
issue_type: documentation
status: Ready
labels: [install_scripts, installation, packaging, documentation]
created_at: 2026-04-22 18:59
updated_at: 2026-04-22 18:59
---

## Context

Sixth (and last implementation) child of t623. Depends on t623_2..t623_5 being implemented + merged so the documented commands actually work.

**Why.** After shipping Homebrew, AUR, .deb, and .rpm install channels, the README + website must reflect them as primary options for their respective platforms, relegating the `curl -fsSL .../install.sh | bash` command to a fallback. Each PM also needs its own walkthrough page covering install / upgrade / uninstall.

**Documentation convention (from CLAUDE.md):** user-facing docs describe current state only. No "previously we only supported curl"; no version-history prose.

**Important framing for every PM page:** each must explain the shim-only model up front. Users will otherwise be confused about why their brew-installed aitasks is the same tiny size regardless of version and why `ait --version` shows one thing at the shell but another inside a project.

## Key Files to Modify

- `README.md` — rewrite the Quick Install section.
- `website/content/docs/installation/_index.md` — rewrite to mirror README + link to per-platform pages.
- `website/content/docs/installation/macos-brew.md` (new).
- `website/content/docs/installation/arch-aur.md` (new).
- `website/content/docs/installation/debian-apt.md` (new).
- `website/content/docs/installation/fedora-dnf.md` (new).
- `website/content/docs/installation/windows-wsl.md` — update to prefer `.deb` over curl inside WSL.

## Reference Files for Patterns

- `aiplans/archived/p623/p623_*_*.md` (all prior siblings) — primary reference for exact install commands, URLs, version ranges.
- `website/content/docs/installation/_index.md` (current state) — existing structure to preserve (weight: 10, Docsy frontmatter, intro wording).
- `website/content/docs/installation/windows-wsl.md` — existing page to update; prefer minimal edits that redirect to the new `.deb` path.
- `README.md` Quick Install section (lines 57–93) — current curl-only presentation; becomes the per-platform table.

## Implementation Plan

1. **README.md rewrite.** Replace the "Quick Install" block with a per-platform table:
   ```markdown
   ## ⚡ Quick Install

   Pick your platform:

   | Platform | Install command |
   |----------|-----------------|
   | macOS | `brew install beyondeye/aitasks/aitasks` |
   | Arch / Manjaro (AUR) | `yay -S aitasks` or `paru -S aitasks` |
   | Debian / Ubuntu / WSL | `curl -fsSL .../releases/latest/download/aitasks_<ver>_all.deb -o ait.deb && sudo apt install ./ait.deb` (see the [Debian/Ubuntu guide](https://aitasks.io/docs/installation/debian-apt/) for the version-resolution one-liner) |
   | Fedora / RHEL / Rocky / Alma | `sudo dnf install https://.../aitasks-<ver>-1.noarch.rpm` |
   | Other (any POSIX system) | `curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh \| bash` |

   After installing, run `ait setup` in your project to bootstrap the framework.
   ```
   Call out the shim-only model in a short paragraph beneath the table.

2. **`website/content/docs/installation/_index.md` rewrite.** Mirror the README table; link each row to its per-platform sub-page.

3. **`macos-brew.md` (new).** Sections:
   - What you get: the `ait` global shim via Homebrew.
   - Install: `brew install beyondeye/aitasks/aitasks`.
   - The shim-only model explanation (1 paragraph).
   - First project: `cd my-project && ait setup`.
   - Upgrade: `brew update && brew upgrade aitasks`.
   - Uninstall: `brew uninstall aitasks`.

4. **`arch-aur.md` (new).** Same structure as `macos-brew.md`, with:
   - Install via AUR helper: `yay -S aitasks` or `paru -S aitasks`.
   - **Explicit note:** plain `pacman -S aitasks` does NOT work (AUR vs official repos).
   - Manual install without AUR helper: `git clone https://aur.archlinux.org/aitasks.git && cd aitasks && makepkg -si`.
   - Upgrade / uninstall via yay/paru.

5. **`debian-apt.md` (new).** Same structure, with:
   - Install: latest-release resolution using `gh release download` or a shell one-liner that queries the GitHub API for the latest asset URL.
   - WSL notes: works identically inside WSL2 Ubuntu.
   - Supported versions: Ubuntu 22.04+, Debian 12+. Ubuntu 20.04 / Debian 11 are not supported (Python < 3.9).
   - Upgrade: download the new `.deb` and `sudo apt install ./new.deb`.
   - Uninstall: `sudo apt remove aitasks`.

6. **`fedora-dnf.md` (new).** Same structure, with:
   - Install via `sudo dnf install https://...noarch.rpm`.
   - Supported: Fedora 40+, Rocky/Alma 9, RHEL 9.
   - Upgrade: `sudo dnf upgrade aitasks-*.noarch.rpm` after downloading new.
   - Uninstall: `sudo dnf remove aitasks`.

7. **`windows-wsl.md` update.** Prepend a "Recommended: install via `.deb` inside WSL" section above the existing curl-based instructions. Keep curl path as a fallback for users who haven't set up `apt`.

## Verification Steps

1. `cd website && npm install && ./serve.sh` — open http://localhost:1313/docs/installation/ and click through every new page. All links resolve; frontmatter valid; Docsy nav generates a sub-entry for each new page.
2. `markdown-link-check website/content/docs/installation/*.md` — zero broken links.
3. Grep for `curl -fsSL` across `README.md` + `website/`:
   ```bash
   grep -r "curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh" README.md website/
   ```
   Confirm this command appears only in the "Other Linux" / fallback contexts, never as the primary recommendation for macOS/Arch/Debian/Fedora.
4. Each per-platform page has: install command, shim-only paragraph, `ait setup` next-step, upgrade section, uninstall section.
5. **Cross-reference the strategy doc.** Each page links to `/aidocs/packaging_strategy.md` (or an excerpt) for users who want to understand why the shim-only model was chosen.
6. Render README.md via `gh api markdown --field text="$(cat README.md)"` (or a browser preview on a PR) and confirm the install table renders correctly on GitHub.
