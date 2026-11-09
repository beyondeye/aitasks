---
title: "Contribution Flow"
linkTitle: "Contribution Flow"
weight: 10
description: "How incoming contribution issues are analyzed for duplicates, scored for overlap, and reviewed with AI"
depth: [advanced]
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

A contribution issue is any open issue that carries the `aitask-contribute-metadata` block or the `contribution` label. GitHub silently drops labels supplied by issue authors without push access, and GitLab silently drops labels supplied by authors who are not members of the project, so an external contributor's issue usually arrives unlabeled. The overlap check and the review listing therefore scan all open issues for the metadata block rather than relying on the label. The GitHub workflow applies the label itself when such an issue is opened, and the GitLab scheduled scan picks up unlabeled contribution issues by their metadata block.

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
- Suggested labels based on the issue's `auto_labels` field. Because the issue author writes that field, only labels in the `area:` and `scope:` namespaces that already exist in the repository are applied automatically; any other suggested label is listed in the comment only.
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
| `--platform github\|gitlab` | Override auto-detected platform |
| `--repo OWNER/REPO` | Target repository (default: from git remote) |
| `--limit N` | Max contribution issues to report (default: 50); all open issues are scanned and the limit applies after filtering |
| `--dry-run` | Print comment to stdout instead of posting |
| `--silent` | Suppress informational output |

## Finding contribution issues

Do not rely on the `contribution` label alone to find contributions. GitHub silently drops labels from issue authors without push access, and GitLab drops them from authors who are not project members, so an external contributor's issue can be open without it. On GitHub, `label:contribution` in the UI and `gh issue list --label contribution` will not show it. On GitLab, the label filter in the issue list, `glab issue list --label contribution` and the `labels=contribution` API filter will not show it either.

To list every open contribution issue, run `/aitask-contribution-review` without an issue number, or call its helper directly:

```bash
./.aitask-scripts/aitask_contribution_review.sh list-issues
```

The listing reads all open issues and keeps those that have the `contribution` label **or** contain the `<!-- aitask-contribute-metadata` block. Each entry reports `HAS_METADATA:true|false`; only entries with metadata can be imported.

On GitHub, the label filter is a reasonable shortcut once the workflow is installed, because the workflow labels each contribution issue when it is opened. It still misses issues opened before the workflow was installed and issues whose labeling step failed (the workflow logs a warning and continues), so use the listing when completeness matters. A GitHub search for the marker text is not a reliable substitute: the marker sits inside an HTML comment, and search may not index it. On GitLab nothing applies the label afterwards, so the listing is the only complete view.

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
- Detects the git remote platform (GitHub or GitLab)
- Creates a `contribution` label on the repository
- Installs the appropriate CI/CD workflow template

On GitHub, if `.github/workflows/contribution-check.yml` already exists, `ait setup` updates it when it is an unmodified earlier version of the shipped template. A workflow you have edited is left unchanged with a warning — merge the current template into it by hand.

On GitLab, `ait setup` creates `.gitlab-ci.yml` only when the file does not exist yet. An existing CI configuration is never edited: setup warns and leaves the merge to you (see [Manual Setup](#manual-setup)). For GitLab, the job uses `stage: test`, so that stage must be in your `stages:` list.

If `.gitlab-ci.yml` already has a `contribution-check:` job copied from an earlier template — one whose scheduled scan only lists issues labeled `contribution`, or computes its cutoff with `date -d '6 hours ago'` — setup warns that the job predates the current template and still leaves the file unchanged. Such a job misses contributions from authors who are not project members, or fails on the job's Alpine image. Copy the job again from the current template (see [Manual Setup](#manual-setup)).

### Per-Platform Configuration

#### GitHub Actions

- **Trigger:** `issues.opened` when the body carries the `aitask-contribute-metadata` block and the issue is not yet labeled (the run also applies the `contribution` label), or `issues.labeled` when the `contribution` label is applied
- **Concurrency:** runs for the same issue are queued one after another; events that do not qualify never enter the queue
- **Token:** `$GITHUB_TOKEN` is auto-provided by GitHub Actions — no extra setup needed
- **CLI:** `gh` is pre-installed on GitHub-hosted runners

No additional configuration required.

#### GitLab CI

- **Trigger:** Webhook-triggered pipeline (via `$ISSUE_IID` variable) or scheduled scan (every 6 hours). The scan reads open issues updated in the last 6 hours and checks those that carry the `contribution` label or the `aitask-contribute-metadata` block
- **Token:** Requires a **project access token** with `api` scope, stored as `$GITLAB_TOKEN` CI/CD variable. `CI_JOB_TOKEN` does **not** have access to issues/notes/labels API endpoints.
- **CLI:** Uses `glab` CLI if available, with curl + REST API fallback

#### Bitbucket

Bitbucket Cloud no longer has an issue tracker: Atlassian removed native Bitbucket Cloud Issues, and the API endpoints behind them, on 20 August 2026. There is nothing for an overlap check to read or comment on, so the contribution check and its CI pipeline are not available on Bitbucket. Running the check with `--platform bitbucket` stops with that explanation, and `ait setup` installs nothing on a Bitbucket remote.

If your `bitbucket-pipelines.yml` still has a `contribution-check` custom pipeline from an earlier setup, remove it and its schedule by hand: it reports success while checking nothing. `ait setup` warns when it finds one, and never edits the file itself.

### Manual Setup

If not using `ait setup`, or when your project already has a CI configuration, the CI/CD templates are available in `.aitask-scripts/ci_templates/`:

- **GitHub** — copy `.aitask-scripts/ci_templates/github/contribution-check.yml` to `.github/workflows/contribution-check.yml`. It is a complete workflow of its own.
- **GitLab** — with no `.gitlab-ci.yml` yet, copy `.aitask-scripts/ci_templates/gitlab/contribution-check-job.yml` to `.gitlab-ci.yml`. Otherwise add its `contribution-check:` job to your existing file, and check that the job's `stage: test` is in your `stages:` list (or change the job's stage to one you declare).

Create the `contribution` label manually on your platform.

## Platform Support Matrix

| Feature | GitHub | GitLab |
|---------|--------|--------|
| Contribution issue discovery | Label or metadata (scans all open issues) | Label or metadata (scans all open issues) |
| Event-driven triggers | Yes (`issues.opened`, `issues.labeled`) | Yes (webhook pipeline) |
| Scheduled scans | Optional | Yes (6-hour interval) |
| CLI tool | `gh` (pre-installed) | `glab` + curl fallback |
| Token source | `$GITHUB_TOKEN` (auto) | `$GITLAB_TOKEN` (manual) |
| Label creation | Yes | Yes |
| Comment posting | Yes | Yes |

Bitbucket is not in the matrix because Bitbucket Cloud has no issue tracker (see [Bitbucket](#bitbucket)).

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
