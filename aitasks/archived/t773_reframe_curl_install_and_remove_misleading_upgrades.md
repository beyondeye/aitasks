---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Done
labels: [documentation, website, installation]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-13 11:25
updated_at: 2026-05-13 11:35
completed_at: 2026-05-13 11:35
---

Update website documentation so the curl one-liner is presented as the recommended primary install method, and remove misleading per-package-manager "Upgrade" instructions from the per-OS install pages.

## Background

The curl one-liner (`curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash`) is the simplest install method and works on every platform aitasks supports. Currently it is framed as a fallback option ("Other (any POSIX)") at the bottom of platform-comparison tables.

Additionally, the per-OS install pages document "Upgrade" steps that recommend the platform package manager (`brew upgrade`, `yay -Syu`, `apt install ./aitasks_*.deb`, `dnf upgrade`). For end users this is misleading: framework upgrades inside a project are performed by `ait upgrade`, not by the OS package manager.

## Scope

### 1. Homepage (`website/content/_index.md`)

In the "Quick Install" section (around lines 37–49):
- Reframe the introductory copy so the curl one-liner is presented first as the simplest method that works on every supported platform.
- Restructure the table (or replace it with a short paragraph + table) so the curl one-liner is the primary recommendation, with per-OS native packages shown afterward as alternatives for users who prefer their distro package manager.
- Keep the link to the Installation guide for per-platform walkthroughs.

### 2. Installation index (`website/content/docs/installation/_index.md`)

In the "Quick Install" section (around lines 8–37):
- Lead with the curl one-liner as the recommended method.
- Move the platform-specific commands (brew, AUR, .deb, .rpm) into a secondary "Alternative: native packages for your OS" section for users who prefer a system package manager.
- Keep the existing `ait setup` follow-up instruction and the note about the global shim being tiny.

### 3. Per-OS install pages

Update each install page so the "Upgrade" subsection no longer recommends the OS package manager. Replace with concise guidance pointing to `ait upgrade` for per-project framework upgrades.

- `website/content/docs/installation/macos.md`
  - "Upgrade" section (lines 43–50): remove the `brew update && brew upgrade aitasks` recommendation.
- `website/content/docs/installation/linux.md`
  - Arch "Upgrade" subsection (lines 57–65): remove the `yay -Syu` / `paru -Syu` recommendation.
  - Debian/Ubuntu "Upgrade" subsection (lines 136–144): remove the re-download-and-`apt install` recommendation.
  - Fedora "Upgrade" subsection (lines 208–214): remove the re-download-and-`dnf upgrade` recommendation.
- `website/content/docs/installation/windows-wsl.md`
  - Reframe so curl is the recommended path and the `.deb` is the alternative for users who prefer a system package, instead of the other way around.

### 4. Replacement guidance for "Upgrade" subsections

In each per-OS install page, replace the deleted "Upgrade" content with a short subsection that explains the upgrade flow lives at the project level. Suggested wording (adapt to each page):

> ### Upgrade
>
> Framework upgrades are per-project. Inside any project that already has aitasks set up, run:
>
> ```bash
> ait upgrade latest
> ```

Keep links to the installation index / `ait upgrade` command reference where appropriate.

### 5. Cross-check

- Search the website tree for any other place that recommends a package-manager upgrade for aitasks (e.g., `brew upgrade`, `apt install ./aitasks_*.deb`, `dnf upgrade`, `yay -Syu aitasks`, `paru -Syu aitasks`) outside of the install pages, and decide whether each reference is still appropriate.
- Verify the "Uninstall" subsections are unchanged — they remain accurate (the package manager owns the shim, so it should also remove it).

## Constraints

- User-facing docs describe the current state only. Do not include "previously we recommended X" / "this corrects an earlier mistake" framing.
- Keep the structure of each install page otherwise intact; do not reorganize prerequisites, terminal-emulator notes, or roadmap subsections.

## Acceptance

- Homepage and Installation index lead with the curl one-liner as the recommended method on every platform aitasks supports.
- Per-OS install pages' "Upgrade" subsections no longer recommend the OS package manager; they direct users to `ait upgrade`.
- Cross-references and roadmap links continue to work.
- `hugo build --gc --minify` (in `website/`) succeeds with no broken links or template errors.
