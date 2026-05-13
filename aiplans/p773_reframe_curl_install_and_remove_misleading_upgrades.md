---
Task: t773_reframe_curl_install_and_remove_misleading_upgrades.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Reframe curl install as recommended; replace package-manager "Upgrade" sections

## Context

The website currently presents the curl-based install one-liner as a fallback ("Other (any POSIX)") at the bottom of platform-comparison tables on both the homepage and the installation index. The curl one-liner is in fact the simplest install method and works on every platform aitasks supports. Lead with it as the recommended primary method; keep platform-native packages as alternatives for users who prefer their distro package manager.

Additionally, each per-OS install page (macOS, Linux Arch/Debian/Fedora, Windows/WSL) contains an "Upgrade" subsection that recommends the OS package manager for framework upgrades (`brew upgrade`, `yay -Syu`, re-running `apt install ./aitasks_*.deb`, `dnf upgrade`). Per-project framework upgrades are handled by `ait upgrade`. Replace these subsections with concise guidance pointing users to `ait upgrade`. Per the user's direction, **do not mention technical rationale** in user-facing copy — present the actions matter-of-factly.

## Files to modify

1. `website/content/_index.md` — Homepage Quick Install section.
2. `website/content/docs/installation/_index.md` — Installation index Quick Install section.
3. `website/content/docs/installation/macos.md` — Replace `## Upgrade` section.
4. `website/content/docs/installation/linux.md` — Replace three `### Upgrade` subsections (Arch, Debian/Ubuntu, Fedora).
5. `website/content/docs/installation/windows-wsl.md` — Reframe so curl is the primary install path.

Per user direction: no "previously we recommended X" framing; describe current state only.

---

## Change 1 — Homepage (`website/content/_index.md`)

Replace the `## ⚡ Quick Install` block (currently lines 36–50) with a version that leads with the curl one-liner and presents native packages as an alternative.

**Current (curl as last "Other" row):**

```markdown
{{% blocks/section color="light" %}}
## ⚡ Quick Install

Pick your platform:

| Platform | Install command |
|----------|-----------------|
| **macOS** | `brew install beyondeye/aitasks/aitasks` |
| **Arch / Manjaro** (AUR) | `yay -S aitasks` |
| **Debian / Ubuntu / WSL** | `.deb` from [Releases](...), then `sudo apt install ./aitasks_*.deb` |
| **Fedora / RHEL / Rocky / Alma** | `.rpm` from [Releases](...), then `sudo dnf install ./aitasks-*.noarch.rpm` |
| **Other (any POSIX)** | `curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh \| bash` |

After installing, run `ait setup` in your project (the git repository root). See the [Installation guide](...) for per-platform walkthroughs and detailed setup instructions.
{{% /blocks/section %}}
```

**New:**

```markdown
{{% blocks/section color="light" %}}
## ⚡ Quick Install

The simplest way — works on every supported platform:

```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
```

Then run `ait setup` in your project (the git repository root).

### Prefer your distro's package manager?

| Platform | Install command |
|----------|-----------------|
| **macOS** | `brew install beyondeye/aitasks/aitasks` |
| **Arch / Manjaro** (AUR) | `yay -S aitasks` |
| **Debian / Ubuntu / WSL** | `.deb` from [Releases](https://github.com/beyondeye/aitasks/releases/latest), then `sudo apt install ./aitasks_*.deb` |
| **Fedora / RHEL / Rocky / Alma** | `.rpm` from [Releases](https://github.com/beyondeye/aitasks/releases/latest), then `sudo dnf install ./aitasks-*.noarch.rpm` |

See the [Installation guide]({{< relref "/docs/installation" >}}) for per-platform walkthroughs and detailed setup instructions.
{{% /blocks/section %}}
```

Note: the inner fenced code block must use a different fence width or be wrapped consistently with how Hugo renders. Inspect adjacent Hugo shortcode usage; if a literal triple-backtick fence inside a `{{% blocks/section %}}` shortcode breaks rendering in this template, fall back to a tilde-fenced block (`~~~bash`/`~~~`) or 4-space indented code. (Check by previewing locally; this is the only risk in the homepage edit.)

---

## Change 2 — Installation index (`website/content/docs/installation/_index.md`)

Restructure the top of the page (lines 8–37) so the curl one-liner leads and platform-native packages follow as an alternative. Keep the existing "Run from the project root." callout, the `ait setup` follow-up instruction, the global-shim explanation, and the WSL/macOS callouts.

**Section reorder:**

1. Keep: `## Quick Install` heading + the existing "Run from the project root" blockquote.
2. New: `### Recommended: install via curl` subsection containing the one-liner and the `ait setup` follow-up.
3. New: `### Alternative: native package for your OS` subsection containing the existing platform table (macOS, Linux, Windows/WSL — drop the existing "Other (any POSIX)" row since the curl path is now primary).
4. Keep: the "All install methods drop a single `ait` command…" paragraph (lines 23 — the global-shim explanation), moved below the alternative table.
5. Keep: the "Upgrade an existing installation: `ait upgrade latest`" block (lines 27–31).
6. Keep: the two callouts (Windows users, macOS users) and the "Already have the global `ait` shim?" callout.

Concretely:

```markdown
## Quick Install

> **Run from the project root.** aitasks expects to be invoked from the directory containing `.git/` — the root of your project's git repository. All install methods below assume you `cd` into that directory first. aitasks stores task files, plans, and configuration inside your repository and relies on git for task IDs, locking, syncing, and archival. Installing in a subdirectory or a non-git directory will not work correctly.

### Recommended: install via curl

The simplest method — works on every supported platform (macOS, Linux, WSL):

```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
```

Then `cd` into your project root (where `.git/` lives) and run `ait setup` to install dependencies and configure agent integrations. See [`ait setup`](../commands/setup-install/) for details.

### Alternative: native package for your OS

If you prefer your distro's package manager:

| Platform | Install command |
|----------|-----------------|
| **macOS** | `brew install beyondeye/aitasks/aitasks` — see the [Homebrew guide](macos/) |
| **Linux** (Arch / Debian / Ubuntu / Fedora / RHEL / Rocky / Alma / WSL) | Distro-specific install paths — see the [Linux guide](linux/) |
| **Windows / WSL** | Use a WSL2 Ubuntu/Debian shell — see the [Windows / WSL guide](windows-wsl/) |

All install methods drop a single `ait` command on your `$PATH` — the **global shim** (~3 KB). The shim downloads the framework on demand when you run `ait setup` in your project, so the installed package stays tiny and you do not need to re-install the package to get framework updates. For the design rationale see the [packaging strategy reference](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_strategy.md); for current limitations of each channel and the roadmap toward more official repos see the [packaging distribution status & roadmap](https://github.com/beyondeye/aitasks/blob/main/aidocs/packaging_distribution_status.md).

### Upgrade

Framework upgrades are per-project. Inside any project that already has aitasks set up, run:

```bash
ait upgrade latest
```

> **Windows users:** Run from a WSL shell, not PowerShell. See the [Windows/WSL guide](windows-wsl/).

> **macOS users:** Apple Terminal.app has limited tmux support (no truecolor, no right-click menu). See the [macOS guide](macos/) for recommended terminal emulators.

> **Already have the global `ait` shim?** Once any install method has placed `ait` on your PATH, you can bootstrap aitasks in any new project directory by running `ait setup` there — the shim auto-downloads the framework on first run. Make sure you are at the root of the git repository (where `.git/` lives), not in a subdirectory.
```

The rest of the file (Setup topics, Cloning a Repo, Symptoms before running setup, What Gets Installed) is unchanged.

---

## Change 3 — macOS install page (`website/content/docs/installation/macos.md`)

Replace the existing `## Upgrade` section (lines 43–50):

**Remove:**

```markdown
## Upgrade

```bash
brew update
brew upgrade aitasks
```

The Homebrew tap is auto-bumped on every aitasks release, so `brew upgrade` will pick up new versions on the normal Homebrew cadence.
```

**Replace with:**

```markdown
## Upgrade

Framework upgrades are per-project. Inside any project that already has aitasks set up, run:

```bash
ait upgrade latest
```
```

The `## Uninstall` section directly below it (`brew uninstall aitasks`) remains unchanged — it correctly removes the shim.

---

## Change 4 — Linux install page (`website/content/docs/installation/linux.md`)

Three `### Upgrade` subsections to replace, identical replacement copy for each. Keep the `### Uninstall` and roadmap subsections that immediately follow each unchanged.

### 4a. Arch `### Upgrade` (lines 57–65)

**Remove:**

```markdown
### Upgrade (Arch)

```bash
yay -Syu aitasks
# or
paru -Syu aitasks
```

The AUR package is auto-bumped on every aitasks release.
```

**Replace with:**

```markdown
### Upgrade (Arch)

Framework upgrades are per-project. Inside any project that already has aitasks set up, run:

```bash
ait upgrade latest
```
```

### 4b. Debian/Ubuntu `### Upgrade` (lines 136–144)

**Remove:**

```markdown
### Upgrade (Debian/Ubuntu)

Same flow as install — download the new `.deb` and:

```bash
sudo apt install ./aitasks_*.deb
```

apt detects the existing install and upgrades in place.
```

**Replace with:**

```markdown
### Upgrade (Debian/Ubuntu)

Framework upgrades are per-project. Inside any project that already has aitasks set up, run:

```bash
ait upgrade latest
```
```

### 4c. Fedora `### Upgrade` (lines 208–214)

**Remove:**

```markdown
### Upgrade (Fedora)

Download the new `.rpm` (same path as install) and:

```bash
sudo dnf upgrade ./aitasks-*.noarch.rpm
```
```

**Replace with:**

```markdown
### Upgrade (Fedora)

Framework upgrades are per-project. Inside any project that already has aitasks set up, run:

```bash
ait upgrade latest
```
```

---

## Change 5 — Windows / WSL install page (`website/content/docs/installation/windows-wsl.md`)

Reframe so the curl one-liner is the recommended path. Keep "Install WSL" intact at the top.

Replace the `## Install aitasks (recommended: .deb package)` section (lines 38–52) AND the `## Fallback: install via curl` section (lines 56–68) with a single restructured section:

**Remove (lines 38–68):**

```markdown
## Install aitasks (recommended: `.deb` package)

Once your WSL Ubuntu/Debian shell is up, the cleanest install is the official `.deb` package — same as native Ubuntu. See the [Linux guide — .deb section](../linux/#debian--ubuntu--wsl-deb) for the full walkthrough; the short version (with [GitHub CLI](https://cli.github.com/) installed):

```bash
gh release download --repo beyondeye/aitasks --pattern '*.deb'
sudo apt install ./aitasks_*.deb
ait setup
```

If you do not have `gh` installed, see the curl one-liner in the [Linux guide — .deb section](../linux/#debian--ubuntu--wsl-deb).

> **Ubuntu 20.04 (Focal) on WSL:** the `.deb` install is blocked by apt's dependency solver (Focal ships `python3 = 3.8`, the `.deb` requires `>= 3.9`). Use the [Fallback: install via curl](#fallback-install-via-curl) section below — `ait setup` provisions a modern Python user-scoped via [uv](https://github.com/astral-sh/uv) and sidesteps the system-package dependency.

After setup completes, see [Authentication with Your Git Remote](../#authentication-with-your-git-remote) to configure GitHub access for task locking, sync, and issue integration.

---

## Fallback: install via curl

If you cannot use the `.deb` (e.g., a custom WSL distro without working `apt`, or Ubuntu 20.04 / Debian 11 with an older Python), install via the curl-based bootstrap:

```bash
cd /path/to/your-project
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
ait setup
```

`ait setup` automatically detects WSL and installs dependencies via `apt`. It also installs a modern Python (3.11) user-scoped via [uv](https://github.com/astral-sh/uv) into `~/.aitask/python/` if your system Python is too old, so this path works on Ubuntu 20.04 / Debian 11 even when the `.deb` install would fail.

If you already have the global `ait` shim installed (from a previous project), you can skip the `curl` step and just run `ait setup` in the new project directory — it will auto-bootstrap the installation.
```

**Replace with:**

```markdown
## Install aitasks

The simplest install — works on any WSL distro (Ubuntu, Debian, and others):

```bash
cd /path/to/your-project
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
ait setup
```

`ait setup` automatically detects WSL and installs dependencies via `apt`. It also installs a modern Python (3.11) user-scoped via [uv](https://github.com/astral-sh/uv) into `~/.aitask/python/` if your system Python is too old.

If you already have the global `ait` shim installed (from a previous project), you can skip the `curl` step and just run `ait setup` in the new project directory.

After setup completes, see [Authentication with Your Git Remote](../#authentication-with-your-git-remote) to configure GitHub access for task locking, sync, and issue integration.

### Alternative: native `.deb` package

If you prefer your distro's package manager (Ubuntu 22.04+ / Debian 12+), install the official `.deb`. See the [Linux guide — .deb section](../linux/#debian--ubuntu--wsl-deb) for the full walkthrough; the short version (with [GitHub CLI](https://cli.github.com/) installed):

```bash
gh release download --repo beyondeye/aitasks --pattern '*.deb'
sudo apt install ./aitasks_*.deb
ait setup
```

### Upgrade

Framework upgrades are per-project. Inside any project that already has aitasks set up, run:

```bash
ait upgrade latest
```
```

The rest of the page (Install Coding Agents, Terminal Options, Known Issues) is unchanged.

---

## Cross-check

After making the edits, grep the website tree for any other place that recommends a package-manager upgrade for aitasks and verify each remaining reference is still appropriate:

```bash
grep -rn -E "brew upgrade aitasks|yay -Syu aitasks|paru -Syu aitasks|apt install \./aitasks_|dnf upgrade \./aitasks" website/
```

Expected: no remaining matches in user-facing install docs. Blog posts and roadmap references may keep historical/roadmap mentions (those describe channel state, not user-facing upgrade instructions).

Also verify `## Uninstall` sections are untouched on all five pages — they correctly remove the shim via the package manager.

## Verification

1. Build the website locally:
   ```bash
   cd website && hugo build --gc --minify
   ```
   Expected: build succeeds with no broken-link warnings introduced.

2. Visually scan rendered output for the four pages:
   - `website/content/_index.md` → renders curl one-liner first; native-package table second.
   - `website/content/docs/installation/_index.md` → leads with "Recommended: install via curl" subsection; "Alternative: native package" subsection follows.
   - `website/content/docs/installation/macos.md` → "Upgrade" subsection shows `ait upgrade latest`.
   - `website/content/docs/installation/linux.md` → all three "Upgrade" subsections (Arch / Debian / Fedora) show `ait upgrade latest`.
   - `website/content/docs/installation/windows-wsl.md` → "Install aitasks" section leads with curl; ".deb" appears as alternative; "Upgrade" subsection shows `ait upgrade latest`.

3. Grep cross-check (command above) reports no remaining package-manager upgrade recipes in user-facing install docs.

## Step 9 (Post-Implementation) reminder

Per task-workflow Step 9: review changes with the user, then commit (`documentation: <description> (t773)`), then archive the task.

## Final Implementation Notes

- **Actual work done:** Edited the 5 planned files. Homepage and installation index now lead with the curl one-liner and present native packages under a clearly subordinate "Prefer your distro's package manager?" / "Alternative: native package for your OS" heading. The four `Upgrade` subsections in macOS / Arch / Debian / Fedora install pages were replaced with identical "Framework upgrades are per-project … `ait upgrade latest`" copy. Windows/WSL page restructured: curl is now the primary install path, `.deb` becomes the alternative; the dedicated `## Fallback: install via curl` H2 was removed (its content was merged into the new primary "Install aitasks" section) and a new `### Upgrade` subsection was added pointing to `ait upgrade latest`.
- **Deviations from plan:** Minor — dropped the standalone `## Operating systems` H2 from `installation/_index.md`. In the original it served as the parent heading for the platform table; under the new structure the table sits beneath `### Alternative: native package for your OS` (a child of `## Quick Install`), so the standalone H2 was redundant. The triple-backtick code fence inside the `{{% blocks/section %}}` shortcode on the homepage rendered correctly (verified in the Hugo build output); the tilde-fence fallback noted in the plan was not needed.
- **Issues encountered:** None. `hugo build --gc --minify` completed in 788 ms with only pre-existing deprecation warnings (`Language.LanguageDirection`, `Site.AllPages`) unrelated to this task.
- **Key decisions:** Phrased the replacement "Upgrade" copy identically across all five touched pages so users see consistent guidance regardless of which install page they land on. Followed the user's directive not to mention technical rationale (no "shim is stable", no "package managers don't get framework updates") — just the action.
- **Upstream defects identified:** None.
