---
priority: low
effort: low
depends: [4, 6]
issue_type: documentation
status: Done
labels: [aitask_contribute]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-10 10:59
updated_at: 2026-03-16 10:23
completed_at: 2026-03-16 10:23
---

## Context

This task adds documentation for the entire contribution overlap detection system and distributes the CI/CD workflow templates via `ait setup`. It covers the fingerprint metadata format, the contribution check workflow, the contribution-review skill, and setup instructions for each platform.

## Key Files to Create/Modify

- `website/content/docs/workflows/` — new or updated workflow documentation
- `website/content/docs/skills/aitask-contribution-review.md` — new skill documentation page
- `.claude/skills/aitask-contribute/SKILL.md` — update to reference fingerprint/overlap features
- Existing contribute/import documentation — update references

## Reference Files for Patterns

- `website/content/docs/workflows/contribute-and-manage.md` — existing contribution workflow docs
- `website/content/docs/skills/aitask-contribute.md` — existing contribute skill docs
- `website/content/docs/workflows/releases.md` — example workflow documentation page

## Implementation Plan

### 1. New documentation page: Contribution Overlap Detection

Create `website/content/docs/workflows/contribution-overlap.md` covering:
- Overview of the three-layer architecture
- Fingerprint metadata format specification (all fields, versions, encoding)
- How the CI/CD workflow processes issues
- How the contribution-review skill groups issues
- Platform support matrix (GitHub/GitLab/Bitbucket capabilities)

### 2. New skill documentation: aitask-contribution-review

Create `website/content/docs/skills/aitask-contribution-review.md` covering:
- Usage: `/aitask-contribution-review <issue_number>`
- What the skill does (fetch, analyze, propose, import)
- Example output and workflow
- Prerequisites (contribution label, CI/CD workflow optional but recommended)

### 3. Update existing documentation

- `website/content/docs/workflows/contribute-and-manage.md` — add section on fingerprint metadata and overlap detection
- `website/content/docs/skills/aitask-contribute.md` — mention fingerprint fields in metadata section
- Document that `contribution` label is assumed to exist (created by `ait setup` or manually)

### 4. Setup instructions

Add a section in documentation covering:
- How `ait setup` creates the `contribution` label (per platform)
- How `ait setup` installs CI/CD wrappers (per platform)
- Manual setup for repos not using `ait setup`
- How to pre-create area/scope labels for auto-label features

### 4a. Per-platform CI/CD token configuration requirements

Documentation must cover token configuration for `aitask_contribution_check.sh`:
- **GitHub Actions**: `$GITHUB_TOKEN` is auto-provided by Actions, no extra setup needed. The `gh` CLI is pre-installed.
- **GitLab CI**: `CI_JOB_TOKEN` does NOT have access to issues/notes/labels API endpoints. Must create a project access token with `api` scope and store as `$GITLAB_TOKEN` CI/CD variable. The script uses `glab` CLI if available, with curl + REST API fallback.
- **Bitbucket Pipelines**: Must create an API token (app passwords deprecated, fully disabled June 2026) and store as `$BITBUCKET_USER` + `$BITBUCKET_TOKEN` repository variables. The script uses curl + REST API only (no CLI dependency). Note: Bitbucket issues API does not support labels, so label operations are silent no-ops.

### 5. Third-party integration docs

Document the fingerprint metadata format in a way that third-party tools can parse it:
- Field names and types
- Version numbering scheme
- The `<!-- overlap-results -->` comment format
- How to consume the data programmatically

## Verification Steps

1. Build Hugo site: `cd website && hugo build --gc --minify`
2. Review rendered documentation for completeness and accuracy
3. Check all internal links resolve correctly
4. Verify documentation matches actual implementation
