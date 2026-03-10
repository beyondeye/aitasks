---
Task: t355_4_cicd_wrappers_and_ait_setup_integration.md
Parent Task: aitasks/t355_check_for_existing_issues_overlap.md
Sibling Tasks: aitasks/t355/t355_5_*.md, aitasks/t355/t355_6_*.md, aitasks/t355/t355_7_*.md
Archived Sibling Plans: aiplans/archived/p355/p355_1_*.md, p355_2_*.md, p355_3_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Previous siblings (t355_1, t355_2, t355_3) added fingerprint metadata to contribution issues and created `aitask_contribution_check.sh` (~786 lines) which analyzes a single issue for overlaps. This task creates CI/CD wrapper templates that trigger the check script automatically and adds `ait setup` integration for label creation + workflow installation.

## Implementation Plan

### Step 1: Create seed CI template directories and files

Create `seed/ci/github/`, `seed/ci/gitlab/`, `seed/ci/bitbucket/`.

**File: `seed/ci/github/contribution-check.yml`**

GitHub Actions workflow triggered by issue open/label events:
- Trigger: `issues: [opened, labeled]`
- Condition: `contains(github.event.issue.labels.*.name, 'contribution')`
- Permissions: `issues: write`, `contents: read`
- Steps: checkout + run `aitask_contribution_check.sh` with issue number, `--platform github`, `--repo`
- Env: `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}`

**File: `seed/ci/gitlab/contribution-check-job.yml`**

GitLab CI job snippet with two modes:
- **Trigger mode**: `$ISSUE_IID` pipeline variable -> check single issue
- **Scheduled mode**: No `--scan-recent` exists in the core script, so the wrapper itself queries the GitLab API for issues updated in the last 6 hours (`updated_after` parameter), then loops calling the check script per issue
- Image: `alpine:latest` with `apk add bash curl jq git`
- Auth: `$GITLAB_TOKEN` (NOT `CI_JOB_TOKEN` -- documented limitation)
- Rules: `trigger` + `schedule` pipeline sources

**File: `seed/ci/bitbucket/contribution-check-pipeline.yml`**

Bitbucket Pipelines custom pipeline (scheduled via Bitbucket UI):
- Lists recent open issues via curl (no label filter -- Bitbucket limitation), loops calling the check script per issue
- Auth: `$BITBUCKET_API_USER` + `$BITBUCKET_API_TOKEN` mapped to `BITBUCKET_USER`/`BITBUCKET_TOKEN` at invocation
- Image: `alpine:latest` with `apk add bash curl jq git`

### Step 2: Create `.github/workflows/contribution-check.yml` for aitasks repo

Same as the GitHub seed template but without jq install step (ubuntu-latest has it).

### Step 3: Add `setup_contribution_check()` to `aitask_setup.sh`

Insert after `setup_review_guides()` (line 2167), before `commit_framework_files()`.

Three functions:
- `_create_contribution_label(platform)` -- Creates `contribution` label on remote (gh/glab/skip)
- `_install_contribution_ci_workflow(platform, project_dir, seed_ci_dir)` -- Copies CI template with idempotency checks
- `setup_contribution_check()` -- Orchestrator

### Step 4: Update `main()` in aitask_setup.sh

Insert `setup_contribution_check` call between `setup_review_guides` and `commit_framework_files`.

### Step 5: Update `commit_framework_files()` check_paths

Add `.github/workflows/` to `check_paths` array. Add conditional check for `.gitlab-ci.yml` and `bitbucket-pipelines.yml`.

### Step 6: Verification

1. `shellcheck .aitask-scripts/aitask_setup.sh` -- no new warnings
2. YAML validation of all 4 workflow files
3. `seed/` already in release.yml tarball (confirmed)

## Key Design Decisions

1. **No `--scan-recent` in core script**: GitLab/Bitbucket scheduled modes implement issue scanning in the CI wrapper YAML itself (API call + loop), keeping the core script focused on single-issue analysis.
2. **No CLI flags for setup**: Follow existing TTY-detection pattern (`[[ -t 0 ]]`) -- consistent with all other optional features.
3. **GitLab append strategy**: Append job snippet to `.gitlab-ci.yml` with comment marker. `grep -q "contribution-check"` prevents double-append.
4. **Bitbucket schedule**: Configured via Bitbucket UI (not YAML-declarable). Pipeline defined as `custom` target.

## Final Implementation Notes
- **Actual work done:** Created 3 seed CI templates (GitHub Actions, GitLab CI, Bitbucket Pipelines) and 1 live workflow for the aitasks repo. Added 3 functions to `aitask_setup.sh` (~173 lines): `_create_contribution_label()` for remote label creation, `_install_contribution_ci_workflow()` for CI template installation with idempotency, and `setup_contribution_check()` as orchestrator. Updated `main()` call chain and `commit_framework_files()` to include new CI paths.
- **Deviations from plan:** None -- implementation matched the plan exactly.
- **Issues encountered:** None. Shellcheck reported no new warnings. All YAML files validated successfully.
- **Key decisions:** GitLab/Bitbucket scheduled scanning loops are in the CI wrapper YAML rather than adding `--scan-recent` to the core script. Used `printf '%s'` instead of `echo` for `sed` URL-encoding in GitLab template. GitHub seed template includes `jq` install step as safety; live aitasks workflow omits it (ubuntu-latest has jq).
- **Notes for sibling tasks:** The `seed/ci/` directory is new and automatically included in the release tarball (release.yml already globs `seed/`). The `contribution` label is expected to exist on the remote for GitHub/GitLab event-driven workflows. t355_7 (documentation) should document the per-platform CI/CD token configuration requirements documented in the seed template comments. The `setup_contribution_check()` function follows the same pattern as `setup_review_guides()` and is called right after it in `main()`.
