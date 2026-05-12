---
Task: t766_regroup_installation_pages_and_unify_linux.md
Base branch: main
plan_verified: []
---

# Plan — t766: Regroup installation pages and unify Linux

## Context

`website/content/docs/installation/` mixes OS-specific install pages (macOS, Windows/WSL) with three separate Linux-distro pages (Arch/AUR, Debian/.deb, Fedora/.rpm) and four cross-cutting topics (Terminal Setup, Known Issues, Git Remotes, PyPy). The flat weight ordering makes this fragile (`windows-wsl=20`, `macos=25`, `terminal-setup=30`, `known-issues=30`, `arch-aur=30`, `debian-apt=40`, `git-remotes=40`, `fedora-dnf=50`, `pypy=60` — multiple collisions). The task asks for:

1. One unified `linux.md` (Arch / Debian / Fedora as subsections).
2. `_index.md` groups OS-specific pages vs cross-cutting setup topics.
3. All inbound links pointing to the deleted distro pages are redirected.
4. `hugo build --gc --minify` runs clean.

## Files to change

### New file
- `website/content/docs/installation/linux.md` — unified Linux page (Arch/AUR, Debian/Ubuntu/WSL/.deb, Fedora/RHEL/Rocky/Alma/.rpm).

### Deleted
- `website/content/docs/installation/arch-aur.md`
- `website/content/docs/installation/debian-apt.md`
- `website/content/docs/installation/fedora-dnf.md`

### Modified
- `website/content/docs/installation/_index.md` — split platform table into "Operating systems" and "Setup topics" sections; update Linux row to point at unified `linux/` page.
- `website/content/docs/installation/windows-wsl.md` — redirect two `../debian-apt/` links to `../linux/#debian--ubuntu--wsl-deb`.
- `website/content/docs/installation/macos.md`, `terminal-setup.md`, `known-issues.md`, `git-remotes.md`, `pypy.md` — only `weight:` frontmatter adjustments (no body changes).
- `website/content/_index.md` — change the homepage Linux feature block `url="docs/installation/"` → `url="docs/installation/linux/"` so the icon links to the new unified page (parallels the existing Windows block linking directly to `docs/installation/windows-wsl/`).

## Step 1 — Content for `linux.md`

Single Hugo page with weight `24` (between macOS=22 and Windows=26). Structure:

```markdown
---
title: "Linux Installation"
linkTitle: "Linux"
weight: 24
description: "Install aitasks on Arch, Debian/Ubuntu, Fedora/RHEL, and other Linux distros"
---

Install aitasks on Linux. Pick the section matching your distro family — Arch/Manjaro (AUR), Debian/Ubuntu/WSL (.deb), or Fedora/RHEL/Rocky/Alma (.rpm). All three install paths place the same ~3 KB global `ait` shim on your `$PATH`; the framework itself is downloaded by `ait setup` when you run it in a project.

## What you get

[Shared "global shim" explainer — single copy, with a per-distro path callout: /usr/bin/ait for Arch/Debian/Fedora.]

## Arch / Manjaro (AUR)
[Body lifted verbatim from arch-aur.md, sections renamed to H3:
- Install (### With an AUR helper, ### Without an AUR helper)
- First project
- Upgrade
- Uninstall
- Roadmap]

## Debian / Ubuntu / WSL (.deb)
[Body lifted verbatim from debian-apt.md:
- Supported versions (Bullseye/Jammy, Focal workaround)
- Install (### With gh, ### Without gh — curl, ### Manual download)
- First project
- WSL notes
- Upgrade
- Uninstall
- Roadmap]

## Fedora / RHEL / Rocky / Alma (.rpm)
[Body lifted verbatim from fedora-dnf.md:
- Supported distros (Fedora 40+, Rocky/Alma/RHEL 9 + EPEL callout)
- Install (### With gh, ### Without gh — curl, ### Manual download)
- First project
- Upgrade
- Uninstall
- Roadmap]

## See also
- [GitHub Releases](https://github.com/beyondeye/aitasks/releases/latest) — `.deb` and `.rpm` artifacts.
- [AUR package page](https://aur.archlinux.org/packages/aitasks)
- [Packaging Distribution Status & Roadmap](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_distribution_status.md)
- [`ait setup`](../commands/setup-install/)
- [Windows/WSL Installation Guide](windows-wsl/) — for the WSL2 host-side setup that precedes the Debian/Ubuntu .deb install.
- [Getting Started]({{< relref "/docs/getting-started" >}})
```

**Anchor IDs** (Hugo's default anchor generation lower-kebabs the heading):
- `#arch--manjaro-aur`
- `#debian--ubuntu--wsl-deb`
- `#fedora--rhel--rocky--alma-rpm`

I will verify final anchor slugs after the page renders (Hugo collapses runs of non-word chars to `-`); the inbound-link updates use these slugs.

**Shim explainer dedup:** All three existing pages have an identical "What you get" block. Keep one canonical copy at the top of `linux.md`; the per-distro sections start at "Install".

## Step 2 — Delete old distro pages

```bash
git rm website/content/docs/installation/arch-aur.md
git rm website/content/docs/installation/debian-apt.md
git rm website/content/docs/installation/fedora-dnf.md
```

## Step 3 — Rework `_index.md`

Change two things:

1. **Replace the single platform table** with two sections under H2 headings:

```markdown
## Operating systems

Pick your platform:

| Platform | Install command |
|----------|-----------------|
| **macOS** | `brew install beyondeye/aitasks/aitasks` — see the [Homebrew guide](macos/) |
| **Linux** (Arch / Debian / Ubuntu / Fedora / RHEL / Rocky / Alma / WSL) | Distro-specific install paths — see the [Linux guide](linux/) |
| **Windows / WSL** | Use a WSL2 Ubuntu/Debian shell, then follow the Linux .deb path — see the [Windows / WSL guide](windows-wsl/) |
| **Other (any POSIX)** | `curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh \| bash` |

[Existing global-shim / `ait setup` follow-up paragraphs unchanged.]

## Setup topics

After installing, see these guides for the rest of the environment:

- [Terminal Setup]({{< relref "terminal-setup" >}}) — terminal emulator + tmux, `ait ide` workflow.
- [Git Remotes]({{< relref "git-remotes" >}}) — auth for GitHub / GitLab / Bitbucket (required for locking, sync, issues).
- [Known Agent Issues]({{< relref "known-issues" >}}) — current Claude Code / Gemini CLI / Codex CLI / OpenCode caveats.
- [PyPy Runtime]({{< relref "pypy" >}}) — optional faster runtime for long-running TUIs.
```

2. **Leave the rest of `_index.md` intact** (Cloning a Repo, What Gets Installed) — those sections are not weight-ordered children, they are body content.

3. **Delete the "Platform Support" table** (currently lines ~80-88 of `_index.md`) entirely — the per-OS pages already cover supported versions in detail (macOS ≥12 in `macos.md`; Debian/Ubuntu/Focal-workaround in the `.deb` section of `linux.md`; Rocky/Alma/RHEL 9 EPEL note in the `.rpm` section; WSL2 path in `windows-wsl.md`). The summary table is redundant once the OS-specific pages are linked from the new "Operating systems" section above.

The "Already have the global `ait` shim?" / "Windows users" / "macOS users" / "Agent caveats" callouts currently sit between the table and the "Cloning a Repo" section; keep them between the two new H2 sections (right after "Operating systems" platform table) since they are platform-table commentary.

## Step 4 — Update weights so the sidebar reflects the grouping

Docsy renders the section sidebar in `weight` order. Set weights to two contiguous bands so OS-specific pages appear above Setup topics:

| File | Current weight | New weight |
|------|---------------|-----------|
| `_index.md` | 10 | 10 (unchanged) |
| `macos.md` | 25 | 22 |
| `linux.md` (new) | — | 24 |
| `windows-wsl.md` | 20 | 26 |
| `terminal-setup.md` | 30 | 40 |
| `git-remotes.md` | 40 | 50 |
| `pypy.md` | 60 | 60 (unchanged) |
| `known-issues.md` | 30 | 70 |

Result: sidebar shows macOS → Linux → Windows/WSL → Terminal Setup → Git Remotes → PyPy Runtime → Known Issues.

## Step 5 — Update inbound links

The full repo audit (grep `arch-aur|debian-apt|fedora-dnf` across `website/`) returned exactly four call sites — all easy to fix:

1. **`website/content/docs/installation/windows-wsl.md` line 40** — `[Debian/Ubuntu guide](../debian-apt/)` → `[Linux guide — .deb section](../linux/#debian--ubuntu--wsl-deb)`
2. **`website/content/docs/installation/windows-wsl.md` line 48** — `[Debian/Ubuntu guide](../debian-apt/)` → `[Linux guide — .deb section](../linux/#debian--ubuntu--wsl-deb)`
3. **`_index.md` lines 17–19** — replaced wholesale by the new "Operating systems" table in Step 3.
4. **`website/content/_index.md` line 118** — homepage Linux block `url="docs/installation/"` → `url="docs/installation/linux/"`. The macOS block at line 122 already routes through the OS-grouped index so it stays put; the Windows block (line 126) already deep-links to `windows-wsl/` and stays put.

No `relref` shortcodes reference the deleted pages anywhere (grep confirms).

## Step 6 — Verification

```bash
cd website
npm install              # if first time
hugo --gc --minify       # must complete with no broken-ref warnings
```

Spot-check manually:
- Sidebar order at `/docs/installation/` shows the new grouping.
- `/docs/installation/linux/` renders with three distro subsections.
- Anchors resolve: `/docs/installation/linux/#arch--manjaro-aur`, `#debian--ubuntu--wsl-deb`, `#fedora--rhel--rocky--alma-rpm`.
- `/docs/installation/windows-wsl/` links from "the cleanest install is the official `.deb` package — same as native Ubuntu" land on the `.deb` subsection of `linux.md`.
- `/` homepage Linux icon now routes directly to `/docs/installation/linux/`.

If `hugo` emits a "REF_NOT_FOUND" or similar warning, re-grep and fix any missed link.

## Step 7 — Commit & push

One commit, code only (no aitasks/aiplans paths):

```bash
git add website/content/docs/installation/linux.md \
        website/content/docs/installation/_index.md \
        website/content/docs/installation/windows-wsl.md \
        website/content/docs/installation/macos.md \
        website/content/docs/installation/terminal-setup.md \
        website/content/docs/installation/known-issues.md \
        website/content/docs/installation/git-remotes.md \
        website/content/docs/installation/pypy.md \
        website/content/_index.md
git rm   website/content/docs/installation/arch-aur.md \
        website/content/docs/installation/debian-apt.md \
        website/content/docs/installation/fedora-dnf.md
git commit -m "documentation: Regroup installation pages and unify Linux (t766)"
```

Then proceed to Step 9 of task-workflow (archival).

## Out of scope

- Renaming `windows-wsl.md` to `windows.md` (frontmatter `linkTitle: "Windows/WSL"` already disambiguates).
- Moving `terminal-setup.md` or `git-remotes.md` out of `installation/` into a new `setup/` section — the task only asks for visual grouping, not directory restructuring.
- Updating the AUR / Homebrew / Debian / Fedora source packaging configs (those live outside `website/` and are not what t766 is about).

## Post-Review Changes

### Change Request 1 (2026-05-12 — drop Platform Support table)
- **Requested by user:** Remove the "Platform Support" table at the end of `_index.md` — per-OS pages already cover supported versions in detail.
- **Changes made:** Deleted the `## Platform Support` section (5 rows + heading) from `_index.md`. "What Gets Installed" now follows "Cloning a Repo".
- **Files affected:** `website/content/docs/installation/_index.md`.

### Change Request 2 (2026-05-12 — generalize Windows/WSL agent install)
- **Requested by user:** The "Install Claude Code" section in windows-wsl.md applies to all supported agents — rename to "Install Coding Agents" and mention Gemini CLI, Codex CLI, OpenCode.
- **Changes made:** Renamed the H2, added a single shared Node.js install step, added one-line install commands for each agent (Claude Code, Gemini CLI, Codex CLI, OpenCode) with upstream doc links, and noted that `ait setup` auto-detects installed agents.
- **Files affected:** `website/content/docs/installation/windows-wsl.md`.

### Change Request 3 (2026-05-12 — remove Warp from Windows page)
- **Requested by user:** Remove the Warp Terminal section.
- **Changes made:** Deleted the `### Warp Terminal` H3 + body from the Terminal Options section. Also removed the "Warp" mention from the "Legacy console" bullet under Known Issues for consistency.
- **Files affected:** `website/content/docs/installation/windows-wsl.md`.

### Change Request 4 (2026-05-12 — split PyPy doc)
- **Requested by user:** PyPy installation subpage is too technical — keep install-related details there and move the rest to a new pypy subpage under Development.
- **Changes made:**
  - Created `website/content/docs/development/pypy.md` (weight 30 in Development section) with: resolver semantics, list of fast-path TUIs, CPython-only TUI rationale (monitor / minimonitor / stats-tui), `AIT_USE_PYPY` override table, diagnostics, background link.
  - Slimmed `website/content/docs/installation/pypy.md` to: intro + install command + disable/remove. Cross-linked to `development/pypy/` for the deeper material.
  - Existing inbound refs in `setup-install.md` and `_index.md` continue to point at `installation/pypy/` (the install flow) and now flow through to `development/pypy/` for technical depth via the cross-link.
- **Files affected:** `website/content/docs/installation/pypy.md`, `website/content/docs/development/pypy.md` (new).

## Final Implementation Notes

- **Actual work done:** Unified the three Linux distro pages into `linux.md` with H2 sections per distro family (Arch/AUR, Debian/Ubuntu/WSL/.deb, Fedora/RHEL/Rocky/Alma/.rpm) and a shared "What you get" shim explainer. Deleted `arch-aur.md`, `debian-apt.md`, `fedora-dnf.md`. Reorganized `_index.md` into "Operating systems" and "Setup topics" H2 sections, dropped the redundant "Platform Support" summary table. Updated weights so the sidebar renders macOS → Linux → Windows/WSL → Terminal Setup → Git Remotes → PyPy → Known Issues. Generalized the Windows/WSL agent install section to cover all four supported agents. Removed the Warp section. Split PyPy doc between installation (install flow) and development (resolver internals). Redirected all inbound links (windows-wsl.md, homepage Linux block).
- **Deviations from plan:** Four post-review change requests (see above) expanded the original scope: dropped Platform Support table, generalized agent install on Windows page, dropped Warp Terminal section, split PyPy doc into install-only vs internals. None of these changed the original t766 acceptance criteria; they ran alongside.
- **Issues encountered:** Hugo's default heading-anchor algorithm collapses runs of non-word chars to multi-dash anchors (`#arch--manjaro-aur`, `#debian--ubuntu--wsl-deb`, `#fedora--rhel--rocky--alma-rpm`). Verified by inspecting the rendered HTML before redirecting inbound links. The build also leaves stale public/ output for deleted pages; cleaned up `public/docs/installation/{arch-aur,debian-apt,fedora-dnf}/` manually post-build (the deploy pipeline regenerates `public/` from scratch, so this is a local-cleanup only).
- **Key decisions:**
  - Used H2 + weight bands (22 / 24 / 26 for OS, 40+ for setup) instead of separate Hugo subsections — preserves all existing relrefs (`{{< relref "terminal-setup" >}}` etc.) while still grouping the sidebar visually.
  - Per-distro sections in `linux.md` use H2 (top-level) so each gets its own anchor for deep-linking from `windows-wsl.md`. H3 was rejected — H3 anchors are nested under the (now absent) prior H2 and would be harder to reach.
  - Cross-link from `installation/pypy` → `development/pypy` rather than wholesale-moving the page, since `setup-install.md` and the installation `_index.md` already deep-link to `installation/pypy`. Renaming would have required updating multiple call sites.
- **Upstream defects identified:** None.
- **Build verification:** `hugo --gc --minify` clean (189 pages, no broken refs). Anchor IDs verified by inspecting `public/docs/installation/linux/index.html`.
