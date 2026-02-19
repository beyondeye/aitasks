---
Task: t188_auto_web_site_rebuild_on_release_fails.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

When a new release tag (e.g., `v0.5.0`) is pushed, the Hugo deployment workflow (`.github/workflows/hugo.yml`) fails with: "Tag 'v0.5.0' is not allowed to deploy to github-pages due to environment protection rules."

The root cause: the Hugo workflow triggers on `push: tags: - 'v*'`, but GitHub Pages' `github-pages` environment has deployment branch protection rules that only allow deployments from the default branch (`main`). A tag push runs in the tag's ref context, which doesn't match the allowed branch.

## Fix

Change the Hugo workflow to trigger via `workflow_run` after the Release workflow completes, instead of directly on tag push. This runs in the default branch context, satisfying the environment protection rules.

### Step 1: Update Hugo workflow trigger

File: `.github/workflows/hugo.yml`

Replace `on: push: tags: - 'v*'` with `on: workflow_run: workflows: ["Release"]: types: [completed]`. Keep `workflow_dispatch` for manual runs.

### Step 2: Add success condition to build job

Add `if` condition to the `build` job so it only runs when the Release workflow succeeded (not on failure/cancellation), or when triggered manually via `workflow_dispatch`.

### Step 3: Update releases documentation

Update `website/content/docs/workflows/releases.md` to reflect that the Hugo workflow now triggers after the Release workflow completes, not directly on tag push.

## Final Implementation Notes
- **Actual work done:** Changed Hugo workflow trigger from `push: tags: - 'v*'` to `workflow_run` after the Release workflow, added success guard to the build job, and updated releases documentation.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Used `workflow_run` instead of having `release.yml` trigger `workflow_dispatch` because `workflow_run` is the standard GitHub Actions pattern for chaining workflows and doesn't require extra permissions.
