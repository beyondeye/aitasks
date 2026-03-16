---
title: "Contribution Flow"
linkTitle: "Contribution Flow"
weight: 10
description: "How incoming contribution issues are analyzed for duplicates, scored for overlap, and reviewed with AI"
---

When a contribution issue arrives on your repository (created by [`/aitask-contribute`](../../../skills/aitask-contribute/) or manually), the aitasks framework provides two layers of analysis before import: an automated CI/CD overlap check and an AI-powered review skill. Together they help maintainers detect duplicates, find related contributions, and make informed import decisions.

## Fingerprint Metadata

Each contribution issue created by `/aitask-contribute` includes a hidden metadata block:

```html
<!-- aitask-contribute-metadata
contributor: username
contributor_email: user@example.com
based_on_version: v1.2.3
fingerprint_version: 1
areas: scripts,claude-skills
file_paths: .aitask-scripts/foo.sh,.aitask-scripts/bar.sh
file_dirs: .aitask-scripts
change_type: enhancement
auto_labels: area:scripts,scope:enhancement
-->
```

**Fields:**

| Field | Description |
|-------|-------------|
| `contributor` | Username of the contributor |
| `contributor_email` | Email address for attribution |
| `based_on_version` | Git tag or commit the changes are based on |
| `fingerprint_version` | Schema version (currently `1`) |
| `areas` | Comma-separated code area names |
| `file_paths` | Sorted, comma-separated list of changed files |
| `file_dirs` | Unique parent directories of changed files |
| `change_type` | One of: `bug_fix`, `enhancement`, `new_feature`, `documentation` |
| `auto_labels` | Suggested labels in `key:value` format |

This metadata is embedded automatically by `/aitask-contribute` and parsed by downstream tools for overlap detection and label suggestions.

## Automated Overlap Analysis

When CI/CD is configured (via `ait setup` or manually), a workflow runs automatically on new contribution issues. It compares the incoming issue's fingerprint against all other open contribution issues.

### Scoring Formula

Each pair of issues is scored based on fingerprint similarity:

| Signal | Weight | Description |
|--------|--------|-------------|
| File path match | ×3 | Number of shared file paths |
| Directory match | ×2 | Number of shared directories |
| Area match | ×2 | Number of shared code areas |
| Change type match | ×1 | Bonus if both issues have the same change type |

### Overlap Thresholds

| Score | Classification | Meaning |
|-------|---------------|---------|
| ≥ 7 | High | Very likely related — strong merge candidate |
| 4–6 | Likely | Worth investigating — may be related |
| < 4 | Low | Probably unrelated (filtered from results) |

### Bot Comment

The CI/CD workflow posts a comment on the contribution issue with:

- A table of the top 5 overlapping issues with scores and links
- Suggested labels based on the issue's `auto_labels` field
- A machine-readable block for programmatic consumption:

```html
<!-- overlap-results top_overlaps: 42:7,38:4 overlap_check_version: 1 -->
```

The check is **idempotent** — if an `<!-- overlap-results -->` comment already exists, the workflow skips re-posting.

### CLI Usage

The overlap check can also be run manually:

```bash
./.aitask-scripts/aitask_contribution_check.sh <issue_number> [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `--platform github\|gitlab\|bitbucket` | Override auto-detected platform |
| `--repo OWNER/REPO` | Target repository (default: from git remote) |
| `--limit N` | Max issues to scan (default: 50) |
| `--dry-run` | Print comment to stdout instead of posting |
| `--silent` | Suppress informational output |

## Reviewing with `/aitask-contribution-review`

The [`/aitask-contribution-review`](../../../skills/aitask-contribution-review/) skill is the maintainer's primary tool for reviewing and importing contribution issues. It orchestrates the full review process:

### Workflow Steps

1. **Issue resolution** — Provide an issue number directly, or choose from an interactive listing of open contribution issues

2. **Validation** — Fetches the issue and verifies it has `aitask-contribute-metadata`. Displays a summary of the contributor, areas, change type, and affected files

3. **Duplicate check** — Checks whether the issue has already been imported as an aitask, preventing accidental re-imports

4. **Related issue gathering** — Searches for related contributions from two sources:
   - **Bot comment overlap scores** — Parses the `<!-- overlap-results -->` block for issues with score ≥ 4
   - **Linked issue references** — Scans the issue body and comments for `#N` references to other contribution issues
   - If no bot comment exists, offers to run a local overlap check

5. **Candidate presentation** — Displays a summary table of related issues with scores, contributors, and changed files

6. **AI diff analysis** — Reads the actual code diffs from all candidate issues and analyzes:
   - Same files or functions touched? (strongest merge signal)
   - Same bug fixed in different ways? (merge and pick best approach)
   - Complementary changes? (merge and combine)
   - Unrelated despite fingerprint similarity? (don't merge)

7. **Import proposal** — Recommends one of:
   - **Merge** multiple issues into a single task
   - **Import** the target issue as a single task
   - **Skip** (no import)

8. **Overlapping existing tasks** — Checks whether any existing aitasks already cover the contribution's scope. Options:
   - **Fold** the overlapping tasks into the newly imported task
   - **Update** an existing task with the contribution content (no new task created)
   - **Ignore** the overlap

9. **Import execution** — Calls `ait issue-import` with the appropriate flags (`--merge-issues` for merged imports, `--issue` for single imports)

10. **Multi-contributor attribution** — For merged imports, the primary contributor (largest diff) gets the `Co-authored-by` trailer. Additional contributors are listed in the commit body. A `contributors:` field in the task frontmatter tracks all contributors.

## CI/CD Setup

### Automatic Setup

Running `ait setup` in your repository automatically:
- Detects the git remote platform (GitHub, GitLab, or Bitbucket)
- Creates a `contribution` label on the repository
- Installs the appropriate CI/CD workflow template

### Per-Platform Configuration

#### GitHub Actions

- **Trigger:** `issues.labeled` event when the `contribution` label is applied
- **Token:** `$GITHUB_TOKEN` is auto-provided by GitHub Actions — no extra setup needed
- **CLI:** `gh` is pre-installed on GitHub-hosted runners

No additional configuration required.

#### GitLab CI

- **Trigger:** Webhook-triggered pipeline (via `$ISSUE_IID` variable) or scheduled scan (every 6 hours, queries recently updated issues)
- **Token:** Requires a **project access token** with `api` scope, stored as `$GITLAB_TOKEN` CI/CD variable. `CI_JOB_TOKEN` does **not** have access to issues/notes/labels API endpoints.
- **CLI:** Uses `glab` CLI if available, with curl + REST API fallback

#### Bitbucket Pipelines

- **Trigger:** Scheduled scan only (recommended every 6 hours) — Bitbucket does not support event-driven issue triggers
- **Token:** Requires `$BITBUCKET_API_USER` and `$BITBUCKET_API_TOKEN` repository variables (app passwords are deprecated and fully disabled June 2026)
- **CLI:** Uses curl + REST API only (no Bitbucket CLI dependency)
- **Limitation:** Bitbucket issues API does not support labels — label operations are silent no-ops

### Manual Setup

If not using `ait setup`, the CI/CD templates are available in `seed/ci/`:

```
seed/ci/github/contribution-check.yml        → .github/workflows/contribution-check.yml
seed/ci/gitlab/contribution-check-job.yml     → append to .gitlab-ci.yml
seed/ci/bitbucket/contribution-check-pipeline.yml → append to bitbucket-pipelines.yml
```

Create the `contribution` label manually on your platform (GitHub/GitLab only — Bitbucket has no label support).

## Platform Support Matrix

| Feature | GitHub | GitLab | Bitbucket |
|---------|--------|--------|-----------|
| Issue label filtering | Yes | Yes | No (scans all issues) |
| Event-driven triggers | Yes (`issues.labeled`) | Yes (webhook pipeline) | No |
| Scheduled scans | Optional | Yes (6-hour interval) | Yes (recommended) |
| CLI tool | `gh` (pre-installed) | `glab` + curl fallback | curl only |
| Token source | `$GITHUB_TOKEN` (auto) | `$GITLAB_TOKEN` (manual) | `$BITBUCKET_API_USER` + `$BITBUCKET_API_TOKEN` (manual) |
| Label creation | Yes | Yes | No (no label API) |
| Comment posting | Yes | Yes | Yes |

## Programmatic Integration

Third-party tools can consume the machine-readable data embedded in contribution issues and bot comments.

### Contribution Metadata Block

```html
<!-- aitask-contribute-metadata
field: value
...
-->
```

Fields are line-separated `key: value` pairs. The block is always at the end of the issue body. Parse by finding the opening `<!-- aitask-contribute-metadata` marker and extracting lines until `-->`.

### Overlap Results Block

```html
<!-- overlap-results top_overlaps: 42:7,38:4 overlap_check_version: 1 -->
```

Format: `top_overlaps:` followed by comma-separated `issue_number:score` pairs. `overlap_check_version: 1` indicates the scoring algorithm version. This block appears in a bot comment, not in the issue body.
