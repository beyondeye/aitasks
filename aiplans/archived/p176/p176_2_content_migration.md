---
Task: t176_2_content_migration.md
Parent Task: aitasks/t176_create_web_site.md
Sibling Tasks: aitasks/t176/t176_3_*.md, aitasks/t176/t176_4_*.md, aitasks/t176/t176_5_*.md
Archived Sibling Plans: aiplans/archived/p176/p176_1_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: t176_2 — Content Migration

## Context

The Hugo site scaffold was set up in t176_1 with Docsy v0.14.3. Now the 7 existing documentation files in `docs/` need to be migrated into `website/content/docs/` with proper Docsy frontmatter, and an About page needs to be created. Internal cross-links between docs must be rewritten for Hugo's URL scheme.

After migration, `website/content/docs/` becomes the **single source of truth** for documentation. Docsy's "Edit this page" links will point directly to these files on GitHub, enabling community contributions. The old `docs/` directory cleanup (replacing with a README redirect) will be handled by a separate follow-up sibling task after the full site is verified and deployed.

## Implementation Steps

### Step 1: Configure "Edit this page" links

Add `github_subdir = "website"` to `website/hugo.toml` `[params]` section so Docsy generates correct "Edit this page" links pointing to `website/content/docs/<file>` on GitHub.

### Step 2: Migrate Each Doc File

For each of 7 docs files:
1. Read source from `docs/`
2. Prepend Docsy frontmatter (title, linkTitle, weight, description)
3. Remove the `# H1 Title` line (Docsy renders title from frontmatter)
4. Write to `website/content/docs/<filename>`

| Source | Destination | Weight |
|--------|-------------|--------|
| `docs/commands.md` | `website/content/docs/commands.md` | 10 |
| `docs/workflows.md` | `website/content/docs/workflows.md` | 20 |
| `docs/skills.md` | `website/content/docs/skills.md` | 30 |
| `docs/task-format.md` | `website/content/docs/task-format.md` | 40 |
| `docs/board.md` | `website/content/docs/board.md` | 50 |
| `docs/development.md` | `website/content/docs/development.md` | 60 |
| `docs/installing-windows.md` | `website/content/docs/installing-windows.md` | 70 |

### Step 3: Rewrite Internal Cross-Links

Hugo renders pages as directories. Update link patterns:
- `(commands.md#anchor)` → `(../commands/#anchor)`
- `(board.md)` → `(../board/)`
- `(skills.md#anchor)` → `(../skills/#anchor)`
- `(../README.md#auth...)` → GitHub URL

### Step 4: Create About Page

Create `website/content/about/_index.md` with project info, author details, and license.

### Step 5: Verify

Run `cd website && hugo server` and check all pages render, links work, "Edit this page" works.

## Verification

```bash
cd website && hugo server
```
- Sidebar nav order: Commands, Workflows, Skills, Task Format, Board, Development, Windows/WSL
- Cross-links in workflows page resolve correctly
- About page in top nav
- "Edit this page" links point to correct GitHub file paths

## Final Implementation Notes
- **Actual work done:** Migrated all 7 docs files to `website/content/docs/` with Docsy frontmatter, rewrote 23 internal cross-links to Hugo-relative paths, created About page at `website/content/about/_index.md`, and added `github_subdir = "website"` to `hugo.toml` for correct "Edit this page" links.
- **Deviations from plan:** None. Implementation followed the plan exactly.
- **Issues encountered:** None — `hugo build` succeeded on first attempt with 16 pages, no warnings.
- **Key decisions:** Used `../commands/#anchor` style relative links (not Hugo `relref` shortcodes) for cross-links — simpler and more portable. Converted `installing-windows.md`'s `../README.md#authentication` link to a full GitHub URL since the README is not part of the Hugo site.
- **Notes for sibling tasks:**
  - `github_subdir = "website"` is now set in `hugo.toml` — the CI workflow (t176_4) does not need additional config for this
  - The `website/content/docs/` files are now the single source of truth. A future sibling task (t176_6) should be created to replace `docs/` with a README redirect after verifying the deployed site
  - The About page uses `menu.main.weight: 30` to appear in the top nav bar
  - All 7 doc pages use weight 10-70 in increments of 10 for sidebar ordering
  - `docs/website-development.md` (created in t176_1) was intentionally not migrated — it's meta-documentation about building the site itself

## Step 9 Reference (Post-Implementation)
After implementation: archive via `./aiscripts/aitask_archive.sh 176_2`
