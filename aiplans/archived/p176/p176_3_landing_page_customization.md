---
Task: t176_3_landing_page_customization.md
Parent Task: aitasks/t176_create_web_site.md
Sibling Tasks: aitasks/t176/t176_4_*.md, aitasks/t176/t176_5_*.md
Archived Sibling Plans: aiplans/archived/p176/p176_1_*.md, aiplans/archived/p176/p176_2_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: t176_3 — Landing Page Customization

## Context

The Hugo/Docsy site scaffold (t176_1) and content migration (t176_2) are complete. The landing page at `website/content/_index.md` is a minimal placeholder with just a cover block and tagline. This task expands it into a full landing page with Docsy block shortcodes (hero with CTAs, feature cards, quick install section) and adds brand colors via SCSS variables.

**Note:** The About page (`website/content/about/_index.md`) was already created by t176_2 with comprehensive content — Step 3 from the task description is not needed.

## Files to Modify

| File | Action |
|------|--------|
| `website/content/_index.md` | Replace — full landing page with Docsy blocks |
| `website/assets/scss/_variables_project.scss` | Edit — add brand color overrides |

## Implementation Steps

### Step 1: Expand landing page with Docsy shortcodes

Replace `website/content/_index.md` with full content using Docsy block shortcodes:
- **Hero section** (`blocks/cover`): Title, tagline, Documentation + GitHub CTA buttons
- **Feature cards** (`blocks/section` + `blocks/feature`): Three cards — File-Based Tasks, Claude Code Integration, Parallel Development
- **Quick install section** (`blocks/section`): curl command + link to docs

### Step 2: Add brand colors to SCSS

Edit `website/assets/scss/_variables_project.scss` to set:
- `$primary: #7C3AED` (purple)
- `$secondary: #1E40AF` (deep blue)

### Step 3: Verify

Run `cd website && hugo server` and check rendering.

## Final Implementation Notes
- **Actual work done:** Expanded the landing page with Docsy block shortcodes (hero with CTA buttons, 3 feature cards, quick install section), added brand colors (purple primary, deep blue secondary), and integrated the project logo (dark theme variant) into the hero section.
- **Deviations from plan:** Added logo integration per user request — copied `imgs/aitasks_logo_dark_theme.png` to `website/static/imgs/` and added an `<img>` tag in the hero section. Removed the `title="aitasks"` from `blocks/cover` since the logo already contains the project name.
- **Issues encountered:** None — `hugo build` succeeded on first attempt with 16 pages and 31 static files.
- **Key decisions:** Used inline `<img>` tag for the logo rather than Docsy's cover background image mechanism, since the logo is a discrete image element, not a full-width background. Set `max-width: 300px` for appropriate sizing.
- **Notes for sibling tasks:**
  - Logo files are in `/imgs/` (project root) — dark and light theme variants available
  - Dark theme logo is copied to `website/static/imgs/` for the website
  - Brand colors: `$primary: #7C3AED` (purple), `$secondary: #1E40AF` (deep blue) — defined in `_variables_project.scss`
  - The About page was already created by t176_2, so it was skipped in this task

## Step 9 Reference (Post-Implementation)
After implementation: archive via `./aiscripts/aitask_archive.sh 176_3`
