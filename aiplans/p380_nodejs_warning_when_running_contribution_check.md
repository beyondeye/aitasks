---
Task: t380_nodejs_warning_when_running_contribution_check.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

GitHub Actions deprecated Node.js 20 runners (announced Sept 2025). Starting March 2026, workflows using actions built on Node 20 show deprecation warnings. The `contribution-check.yml` workflow uses `actions/checkout@v4` which runs on Node 20. `actions/checkout@v5` uses Node 24 and is available.

## Plan

### Step 1: Update `.github/workflows/contribution-check.yml`

- Change `actions/checkout@v4` → `actions/checkout@v5` (line 16)

### Step 2: Update `seed/ci/github/contribution-check.yml`

- Change `actions/checkout@v4` → `actions/checkout@v5` (line 21)

### Step 3: Sync missing "Install jq" step

The seed template has an "Install jq" step (lines 23-24) that the active workflow is missing. Add this step to `.github/workflows/contribution-check.yml` for consistency:
```yaml
      - name: Install jq
        run: command -v jq >/dev/null 2>&1 || sudo apt-get install -y jq
```

### Files to modify
- `.github/workflows/contribution-check.yml`
- `seed/ci/github/contribution-check.yml`

### Verification
- Review the diff to confirm only the checkout version changed and the jq step was added
- No tests to run — this is a CI workflow change

### Step 4: Post-Implementation (Step 9)
Archive task and clean up.
