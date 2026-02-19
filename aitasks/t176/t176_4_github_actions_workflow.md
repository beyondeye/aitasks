---
priority: high
effort: low
depends: [176_1]
issue_type: feature
status: Ready
labels: [web_site]
created_at: 2026-02-19 11:04
updated_at: 2026-02-19 11:04
---

## Context
This is the fourth child task of t176 (Create Web Site). After the Hugo site scaffold is set up (t176_1), this task creates the GitHub Actions workflow that builds and deploys the Hugo site to GitHub Pages. This task can run in parallel with t176_2 and t176_3.

**GitHub repo:** https://github.com/beyondeye/aitasks
**Target site URL:** https://beyondeye.github.io/aitasks/

The project already has one workflow at `.github/workflows/release.yml` (triggers on `v*` tag push, creates release tarballs). The new workflow must not conflict with it.

## Key Files to Create

1. **`.github/workflows/hugo.yml`** — GitHub Actions workflow for Hugo build and GitHub Pages deployment

## Reference Files for Patterns

- `.github/workflows/release.yml` — existing workflow to understand patterns and avoid conflicts
- `website/hugo.toml` — created in t176_1, needed to verify build works
- `website/go.mod` — created in t176_1, needed for Hugo modules in CI

## Implementation Plan

### Step 1: Create the workflow file

Create `.github/workflows/hugo.yml`. Key requirements:
- Triggers on push to `main` branch and `workflow_dispatch`
- Uses Hugo extended v0.156.0, Go 1.23.6, Dart Sass 1.97.3
- Sets permissions: `contents: read`, `pages: write`, `id-token: write`
- Build job: checkout, setup Go, configure pages, install Dart Sass, install Hugo extended, cache Hugo modules, build from `website/` directory with `--gc --minify --baseURL` using dynamic pages URL
- Deploy job: uses `actions/deploy-pages@v4` with github-pages environment

### Step 2: Document manual GitHub setup step

**CRITICAL ONE-TIME MANUAL STEP:** The repository owner must go to:
1. GitHub repo Settings → Pages
2. Under "Build and deployment" → Source
3. Change from "Deploy from a branch" to "GitHub Actions"

This cannot be automated from the workflow itself. Without this, the deploy step will fail with a permissions error.

Add a comment at the top of the workflow file documenting this prerequisite.

### Step 3: Verify locally
You cannot fully test GitHub Actions locally, but verify:
1. The YAML is valid (no syntax errors)
2. The workflow file is in the correct location
3. It does not conflict with the existing `release.yml` (different triggers, different permissions)

## Verification Steps

1. `.github/workflows/hugo.yml` exists and has valid YAML syntax
2. Workflow triggers on push to `main` (not on tag push like `release.yml`)
3. Workflow uses Hugo extended edition
4. Workflow uses `actions/deploy-pages@v4` for modern Pages deployment
5. No conflicts with existing `release.yml` workflow
6. Manual setup step is documented in the workflow file comments
