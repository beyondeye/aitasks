---
Task: t176_create_web_site.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: t176 — Create Hugo Website with Docsy Theme for GitHub Pages

## Context

The aitasks project needs a documentation website. Currently, docs exist as 7 markdown files in `docs/` plus `README.md`, but there's no web presence. The task requests a Hugo static site using the Docsy theme, deployed automatically to GitHub Pages via GitHub Actions.

The task explicitly requests splitting into child tasks due to complexity.

## Architecture Decisions

1. **Hugo Modules** (not git submodules) for Docsy — recommended by Docsy, cleaner for CI
2. **`website/` subdirectory** — keeps Hugo files separate from the main project
3. **Content as adapted copies** — `website/content/docs/` contains Hugo-ready versions of `docs/` files with Docsy frontmatter added
4. **Modern GitHub Pages deployment** — uses `actions/deploy-pages` (not gh-pages branch), triggered on push to main
5. **Site URL:** `https://beyondeye.github.io/aitasks/`

## Child Task Breakdown (5 tasks)

### t176_1: Hugo site scaffold with Docsy module
- **Priority:** high | **Effort:** medium | **Depends:** none
- Create `website/` directory, init Hugo, set up Docsy module, create `hugo.toml`, placeholder SCSS files, minimal `content/_index.md` and `content/docs/_index.md`
- **Verify:** `hugo server` runs without errors from `website/`

### t176_2: Content migration — docs pages with Docsy frontmatter
- **Priority:** high | **Effort:** medium | **Depends:** t176_1
- Adapt all 7 docs files into `website/content/docs/` with proper frontmatter (title, weight, description, linkTitle)
- Remove H1 titles (Docsy renders title from frontmatter), update internal cross-links
- Create `website/content/about/_index.md`

### t176_3: Landing page content and site customization
- **Priority:** medium | **Effort:** medium | **Depends:** t176_1
- Build landing page with Docsy shortcodes (hero, features, quick install)
- Customize brand colors in `_variables_project.scss`
- Can run in parallel with t176_2 and t176_4

### t176_4: GitHub Actions workflow for Hugo deployment
- **Priority:** high | **Effort:** small | **Depends:** t176_1
- Create `.github/workflows/hugo.yml` — builds Hugo site, deploys to GitHub Pages
- Triggers on push to main + workflow_dispatch
- Document one-time manual step: GitHub Settings → Pages → Source → "GitHub Actions"
- Can run in parallel with t176_2 and t176_3

### t176_5: Update README and contributor docs
- **Priority:** low | **Effort:** small | **Depends:** t176_2, t176_4
- Add docs website badge/link to `README.md`
- Create `website/README.md` explaining Hugo site structure, local development, how to add content

## Dependency Graph

```
t176_1 (scaffold)
  ├── t176_2 (content migration)  ──┐
  ├── t176_3 (landing page)        ├── t176_5 (README update)
  └── t176_4 (CI workflow)  ───────┘
```

Tasks 2, 3, 4 can run in parallel after task 1 completes. Task 5 is last.

## Implementation Steps

1. Create child task files using `aitask_create.sh --batch --parent 176`
2. Use `--no-sibling-dep` for t176_3 and t176_4 (they don't depend on t176_2)
3. Manually adjust depends for t176_5 to include both t176_2 and t176_4
4. Revert parent status to Ready (child tasks handle their own status)
5. Start with t176_1

## Key Technical Details for Child Tasks

**hugo.toml critical settings:**
- `baseURL = "https://beyondeye.github.io/aitasks/"`
- `theme = ["github.com/google/docsy"]`
- Hugo modules config with `proxy = "direct"`
- `[markup.goldmark.renderer] unsafe = true`

**GitHub Actions workflow:**
- Hugo extended v0.156.0 + Go 1.23.x + Dart Sass 1.97.3
- Uses `actions/configure-pages`, `actions/upload-pages-artifact`, `actions/deploy-pages@v4`
- `working-directory: website` for Hugo build step

**Content weight ordering:** commands(10), workflows(20), skills(30), task-format(40), board(50), development(60), installing-windows(70)

## Verification

After all child tasks complete:
1. Push to main triggers GitHub Actions build
2. Site accessible at `https://beyondeye.github.io/aitasks/`
3. All 7 doc pages render correctly with navigation
4. Landing page shows hero, features, quick install
5. Internal cross-links work between doc pages

## Step 9 Reference

Post-implementation: archive each child task via `aitask_archive.sh`, then archive parent when all children complete.
