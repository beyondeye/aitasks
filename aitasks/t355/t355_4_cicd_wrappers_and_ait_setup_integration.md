---
priority: medium
effort: medium
depends: [3]
issue_type: feature
status: Ready
labels: [aitask_contribute]
created_at: 2026-03-10 09:56
updated_at: 2026-03-10 09:56
---

## Context

This task creates thin CI/CD wrapper files for each platform (GitHub Actions, GitLab CI, Bitbucket Pipelines) that call the core `aitask_contribution_check.sh` script (t355_3). It also adds `ait setup` integration to auto-detect the git remote, create the `contribution` label, and install the appropriate CI/CD wrapper.

## Key Files to Create/Modify

- `seed/ci/github/contribution-check.yml` — GitHub Actions workflow template
- `seed/ci/gitlab/contribution-check-job.yml` — GitLab CI job snippet template
- `seed/ci/bitbucket/contribution-check-pipeline.yml` — Bitbucket Pipelines snippet template
- `.github/workflows/contribution-check.yml` — workflow for the aitasks repo itself
- `.aitask-scripts/aitask_setup.sh` — add contribution label creation + CI/CD wrapper installation

## Reference Files for Patterns

- `.github/workflows/release.yml` — existing GitHub Actions workflow pattern
- `.github/workflows/hugo.yml` — existing workflow with `workflow_run` trigger
- `.aitask-scripts/aitask_setup.sh:104-128` — `install_cli_tools()` platform detection
- `.aitask-scripts/aitask_setup.sh:71-88` — `_detect_git_platform()` inline function
- `.aitask-scripts/aitask_setup.sh:1006-1016` — seed file copying pattern

## Implementation Plan

### 1. GitHub Actions workflow (`seed/ci/github/contribution-check.yml`)

```yaml
name: Contribution Check
on:
  issues:
    types: [opened, labeled]
jobs:
  check-contribution:
    if: contains(github.event.issue.labels.*.name, 'contribution')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check for overlapping contributions
        run: ./.aitask-scripts/aitask_contribution_check.sh ${{ github.event.issue.number }} --platform github --repo ${{ github.repository }}
        env:
          GH_TOKEN: ${{ github.token }}
```

### 2. GitLab CI job snippet (`seed/ci/gitlab/contribution-check-job.yml`)

Two modes:
- **Webhook-triggered:** Receives `$ISSUE_IID` from pipeline trigger variable
- **Scheduled:** Scans recent issues (last hour) for new contributions

```yaml
contribution-check:
  stage: deploy
  rules:
    - if: '$CI_PIPELINE_SOURCE == "trigger" && $ISSUE_IID'
    - if: '$CI_PIPELINE_SOURCE == "schedule"'
  script:
    - |
      if [ -n "$ISSUE_IID" ]; then
        ./.aitask-scripts/aitask_contribution_check.sh "$ISSUE_IID" --platform gitlab --repo "$CI_PROJECT_PATH"
      else
        # Scheduled mode: scan recent issues
        ./.aitask-scripts/aitask_contribution_check.sh --scan-recent --platform gitlab --repo "$CI_PROJECT_PATH"
      fi
```

### 3. Bitbucket Pipelines snippet (`seed/ci/bitbucket/contribution-check-pipeline.yml`)

Scheduled-only (Bitbucket has no issue event triggers):
```yaml
pipelines:
  custom:
    contribution-check:
      - step:
          name: Check contribution overlaps
          script:
            - ./.aitask-scripts/aitask_contribution_check.sh --scan-recent --platform bitbucket --repo "$BITBUCKET_WORKSPACE/$BITBUCKET_REPO_SLUG"
  schedules:
    - cron: '0 */6 * * *'
      pipeline: custom.contribution-check
```

### 4. `ait setup` additions

Add a new function `setup_contribution_check()` called from `main()`:

a. **Create `contribution` label** (platform-aware):
   - GitHub: `gh label create "contribution" --color "0e8a16" --description "External contribution via aitask-contribute" 2>/dev/null || true`
   - GitLab: `glab label create "contribution" --color "#0e8a16" --description "External contribution via aitask-contribute" 2>/dev/null || true`
   - Bitbucket: skip (no label API), warn user
   - Guard: only attempt if remote is configured and CLI is authenticated
   - If no remote: warn that label must be created manually

b. **Install CI/CD wrapper** (with user opt-in):
   - Interactive: ask user if they want to install contribution check workflow
   - Batch: `--with-contribution-check` flag
   - Detect platform, copy appropriate file from `seed/ci/`
   - GitHub: copy to `.github/workflows/contribution-check.yml`
   - GitLab: append job to `.gitlab-ci.yml` (create if missing)
   - Bitbucket: append pipeline to `bitbucket-pipelines.yml` (create if missing)

## Verification Steps

1. Run `shellcheck` on any bash scripts
2. Verify workflow YAML syntax with `yq` or manual inspection
3. Test `ait setup` in a mock environment to verify platform detection and file installation
4. Verify GitHub Actions workflow triggers correctly on issue creation (manual test)
