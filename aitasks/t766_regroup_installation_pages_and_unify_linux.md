---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [web_site, installation]
file_references: [website/content/docs/installation/_index.md, website/content/docs/installation/arch-aur.md, website/content/docs/installation/debian-apt.md, website/content/docs/installation/fedora-dnf.md, website/content/docs/installation/macos.md, website/content/docs/installation/windows-wsl.md, website/content/docs/installation/terminal-setup.md, website/content/docs/installation/known-issues.md, website/content/docs/installation/git-remotes.md, website/content/docs/installation/pypy.md]
created_at: 2026-05-12 10:50
updated_at: 2026-05-12 10:50
---

The installation pages at `website/content/docs/installation/` are flat and mix OS-specific install pages with cross-cutting installation topics. They should be regrouped so the index clearly separates the two categories, and all Linux distros (Arch/AUR, Debian/Ubuntu/.deb, Fedora/.rpm) should be unified into a single "Linux" page with per-distro subsections.

## Current state

`website/content/docs/installation/`:

OS-specific install pages:
- `macos.md` — macOS via Homebrew
- `windows-wsl.md` — Windows/WSL guide
- `arch-aur.md` — Arch / Manjaro via AUR
- `debian-apt.md` — Debian / Ubuntu / WSL via .deb
- `fedora-dnf.md` — Fedora / RHEL / Rocky / Alma via .rpm

Other installation topics:
- `terminal-setup.md` — Terminal Setup
- `known-issues.md` — Known Agent Issues
- `git-remotes.md` — Git Remotes
- `pypy.md` — PyPy Runtime (optional)

`_index.md` lists them in a single flat weight ordering.

## Desired changes

1. **Unify the three Linux distro pages into a single `linux.md`** with one subsection per distro (Arch/AUR, Debian/Ubuntu/.deb, Fedora/.rpm). Preserve all current content as subparagraphs of the unified page. Delete the per-distro source files after migration.

2. **Group OS-specific install pages together in `_index.md`** (macOS, Linux, Windows/WSL) under a clear "Operating systems" heading.

3. **Group remaining installation topics together** (Terminal Setup, Known Issues, Git Remotes, PyPy Runtime) under a separate clear heading like "Setup topics" or similar in `_index.md`.

4. **Update all inbound links** site-wide that point to the now-deleted distro pages so they point to the unified `linux.md` (with anchor to the relevant distro subsection when possible). Pages to scan include other `docs/installation/` pages, `docs/concepts/`, `docs/workflows/`, `docs/skills/`, the top-level `_index.md` / homepage shortcodes, and any `relref` shortcode references.

## Acceptance criteria

- `arch-aur.md`, `debian-apt.md`, `fedora-dnf.md` no longer exist; their content lives in `linux.md`.
- `_index.md` visibly groups OS-specific pages separately from cross-cutting topics (either via Hugo `weight` re-ordering with section headers, or section sub-indexes — whichever fits the Docsy theme cleanest).
- `hugo build --gc --minify` runs clean with no broken `relref` references.
- All previously working anchors / links still resolve (or redirect cleanly).
