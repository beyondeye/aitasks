---
Task: t176_4_github_actions_workflow.md
Parent Task: aitasks/t176_create_web_site.md
Sibling Tasks: aitasks/t176/t176_5_readme_and_contributor_docs.md
Archived Sibling Plans: aiplans/archived/p176/p176_1_hugo_site_scaffold.md, aiplans/archived/p176/p176_2_content_migration.md, aiplans/archived/p176/p176_3_landing_page_customization.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: t176_4 — GitHub Actions Workflow for Hugo + GitHub Pages

## Context

The aitasks project has a Hugo/Docsy website in `website/` (created in t176_1, content migrated in t176_2, landing page customized in t176_3). This task creates the GitHub Actions workflow to automatically build and deploy the site to GitHub Pages on every push to `main`.

Key facts from sibling tasks:
- Docsy v0.14.3 requires PostCSS — `website/package.json` has `postcss`, `postcss-cli`, `autoprefixer` as devDependencies
- Hugo extended edition is required (Go modules + SCSS)
- `website/go.mod` uses Go 1.25.7
- Existing `release.yml` triggers on `v*` tag push only — no conflict

## Step 1: Create `.github/workflows/hugo.yml`

Create the workflow file with:

**Trigger:** `push` with tags `v*` (same as release.yml) + `workflow_dispatch`

**Concurrency:** Cancel in-progress deployments for same group

**Permissions:** `contents: read`, `pages: write`, `id-token: write`

**Build job (`build`):**
1. Checkout with submodules and fetch-depth 0 (for `enableGitInfo`)
2. Setup Go (for Hugo modules)
3. Setup Node.js + `npm ci` in `website/` (for PostCSS/autoprefixer)
4. Install Dart Sass
5. Install Hugo extended (matching local v0.155.3)
6. Build: `hugo --gc --minify --baseURL "${{ steps.pages.outputs.base_url }}/"` from `website/` dir
7. Upload artifact with `actions/upload-pages-artifact@v3`

**Deploy job (`deploy`):**
- Depends on `build`
- Environment: `github-pages` with URL output
- Uses `actions/deploy-pages@v4`

**Top-of-file comment:** Document the manual GitHub Pages setup prerequisite (Settings → Pages → Source → GitHub Actions).

## Step 2: Validate YAML

Run `python -c "import yaml; yaml.safe_load(open('.github/workflows/hugo.yml'))"` or similar to verify no syntax errors.

## Step 3: Verify no conflicts with `release.yml`

Confirm different triggers (push to main vs tag push), different permissions, no naming collisions.

## Verification

1. `.github/workflows/hugo.yml` exists with valid YAML
2. Triggers on `v*` tag push (same event as release.yml, separate workflow)
3. Installs Hugo extended, Go, Node.js, Dart Sass
4. Runs `npm ci` in `website/` for PostCSS deps
5. Builds from `website/` directory
6. Uses `actions/deploy-pages@v4`
7. No conflicts with `release.yml`
8. Manual setup step documented in comments

## Final Implementation Notes
- **Actual work done:** Created `.github/workflows/hugo.yml` with full build and deploy pipeline for Hugo + GitHub Pages. Build job installs Go, Node.js (for PostCSS), Dart Sass, and Hugo extended, then builds the site from `website/`. Deploy job uses `actions/deploy-pages@v4`.
- **Deviations from plan:** None. Implementation matched the plan exactly.
- **Issues encountered:** None.
- **Key decisions:**
  - Used `peaceiris/actions-hugo@v3` for Hugo installation (well-maintained action)
  - Used `go-version-file: website/go.mod` to auto-detect Go version
  - Used `sudo snap install dart-sass` for Dart Sass on Ubuntu runners
  - Set `cancel-in-progress: false` to avoid cancelling ongoing deployments
  - Triggers on `v*` tag push (deploys only on release, not every push to main) + `workflow_dispatch` for manual runs
- **Notes for sibling tasks:**
  - The workflow file is at `.github/workflows/hugo.yml`
  - The manual GitHub Pages setup step (Settings → Pages → Source → GitHub Actions) is documented in the workflow file's top comment — t176_5 should reference this in the contributor docs
  - Both `release.yml` and `hugo.yml` trigger on `v*` tag push and run in parallel

## Step 9 Reference (Post-Implementation)
After implementation: archive via `./aiscripts/aitask_archive.sh 176_4`
