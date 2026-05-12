---
Task: t767_getting_started_page_fixes.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: t767 — Getting Started page fixes

## Context

The website's Getting Started page (`website/content/docs/getting-started.md`)
currently duplicates the platform-specific install table that lives on the
Installation page (`website/content/docs/installation/_index.md`). Section 1
"Install aitasks" contains its own per-platform install command table (macOS
Homebrew, AUR, `.deb`, `.rpm`, curl-pipe-bash) alongside an `ait setup` block.

The task ask: section 1 should NOT contain platform-specific install
instructions; it should reference the installation page instead. This keeps a
single source of truth and prevents drift between the two pages (the
Installation page is the canonical "pick your platform" surface).

## Change

In `website/content/docs/getting-started.md`, replace the body of section
"## 1. Install aitasks" so that:

- The per-platform install command table is removed.
- The narrative directs the reader to the [Installation guide](../installation/)
  to pick the right channel for their OS.
- The `ait setup` step is preserved (it is the universal post-install step
  every reader needs to run from the project root, not a platform-specific
  install command).
- The "Run `ait setup` from the project root" callout is preserved (clarifies
  that aitasks must be invoked from the repo root).
- The trailing "See the Installation guide for platform-specific details and
  troubleshooting" line is removed (now redundant with the new opening
  sentence).

### Before (lines 11–32)

```markdown
## 1. Install aitasks

Pick the install command for your platform (full per-platform walkthroughs in the [Installation guide](../installation/)):

| Platform | Install command |
|----------|-----------------|
| **macOS** | `brew install beyondeye/aitasks/aitasks` |
| **Arch / Manjaro** (AUR) | `yay -S aitasks` |
| **Debian / Ubuntu / WSL** | Download the `.deb` from [Releases](https://github.com/beyondeye/aitasks/releases/latest), then `sudo apt install ./aitasks_*.deb` |
| **Fedora / RHEL / Rocky / Alma** | Download the `.rpm` from [Releases](https://github.com/beyondeye/aitasks/releases/latest), then `sudo dnf install ./aitasks-*.noarch.rpm` |
| **Other (any POSIX)** | `curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh \| bash` |

> **Run `ait setup` from the project root.** aitasks expects to be invoked from the directory containing `.git/` — the root of your project's git repository. It uses git branches for task IDs, locking, and syncing, and task and plan files are committed to your repository.

In your project directory (the root of the git repository, where `.git/` lives), run the setup to install dependencies and configure supported agent integrations:

```bash
cd /path/to/your-project
ait setup
```

See the [Installation guide](../installation/) for platform-specific details and troubleshooting.
```

### After

```markdown
## 1. Install aitasks

See the [Installation guide]({{< relref "/docs/installation" >}}) for platform-specific install commands (macOS, Linux distros, Windows/WSL, and POSIX fallback) and troubleshooting.

> **Run `ait setup` from the project root.** aitasks expects to be invoked from the directory containing `.git/` — the root of your project's git repository. It uses git branches for task IDs, locking, and syncing, and task and plan files are committed to your repository.

In your project directory (the root of the git repository, where `.git/` lives), run the setup to install dependencies and configure supported agent integrations:

```bash
cd /path/to/your-project
ait setup
```
```

Note: prefer `{{< relref "/docs/installation" >}}` over the relative path
`../installation/` for the new link, matching the link style used elsewhere in
the same file (e.g., the `ide-model` and `workflows` refs at lines 110, 117).
The original mixed style had several `../installation/...` relative links;
keeping the new top-level link as `relref` is more robust to page moves.

## Files modified

- `website/content/docs/getting-started.md` — section 1 rewritten as above.
  No other sections touched.

## Verification

1. Render check (Hugo): the link `{{< relref "/docs/installation" >}}` must
   resolve. Confirm by running `cd website && hugo build --gc --minify` and
   checking it does not emit a REF_NOT_FOUND error. (Skip if Hugo is not
   available; the relref form is identical to the one used at line 110 and
   117 in the same file, so resolution should be consistent.)
2. Visual check: open `website/content/docs/getting-started.md` and confirm:
   - Section 1 no longer has a platform table.
   - Section 1 still has the project-root callout and the `ait setup` block.
   - All later sections (2–7) are unchanged.
3. Grep that no stale references remain in section 1:
   `grep -n "brew install\|yay -S\|\.deb\|\.rpm" website/content/docs/getting-started.md`
   — should return no hits inside section 1.

## Final Implementation Notes

- **Actual work done:** Section 1 "Install aitasks" in `website/content/docs/getting-started.md` was rewritten to remove the per-platform install command table and the trailing duplicate "See the Installation guide" line. A single intro line now points readers to the Installation guide via `{{< relref "/docs/installation" >}}`. The "Run `ait setup` from the project root" callout and the `ait setup` shell block were preserved as planned.
- **Deviations from plan:** None. Applied exactly as drafted.
- **Issues encountered:** None.
- **Key decisions:** Used `{{< relref "/docs/installation" >}}` (Hugo shortcode) rather than `../installation/` to match the link style already used elsewhere in the same file (lines for `ide-model` and `workflows` use `relref`), and to be robust to future page moves.
- **Upstream defects identified:** None.

## Step 9 (Post-Implementation)

Standard archive flow:
- Commit code change (`documentation: ...` per `issue_type: documentation`).
- Commit and push the plan file.
- Run `./.aitask-scripts/aitask_archive.sh 767`.
- Push.
