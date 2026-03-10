---
Task: t355_check_for_existing_issues_overlap.md
Worktree: (current directory)
Branch: main
Base branch: main
---

# Plan: t355 — Check for Existing Issues Overlap

## Context

The `aitask-contribute` skill creates contribution issues on GitHub/GitLab/Bitbucket but has no mechanism to detect whether the same fix/change was already proposed in another contribution issue. The reviewer must manually import and inspect each issue one by one. Additionally, multiple related issues can't be merged into a single imported task.

This is a **brainstorming and design task**. The deliverable is a design document embedded in the task file with proposed child tasks for implementation.

## Architecture: Three-Layer, Platform-Agnostic Design

### Layer 1: Contributor side (aitask-contribute skill)
Embeds a composite fingerprint AND auto-label suggestions in the issue metadata comment. No label application or overlap checking during issue creation.

### Layer 2: Receiving repo side (core script + CI/CD wrappers)
A portable bash script (`aitask_contribution_check.sh`) with encapsulated platform-specific code. Thin CI/CD wrappers call it:
- **GitHub Actions**: event-driven (`issues.opened`/`issues.labeled`)
- **GitLab CI**: webhook-triggered pipeline or scheduled scan
- **Bitbucket Pipelines**: scheduled scan

`ait setup` auto-detects the git remote, creates the `contribution` label, and installs the appropriate CI/CD wrapper.

### Layer 3: Reviewer side (new AI skill)
New `aitask-contribution-review` skill. Takes a single issue number. Gathers related issues from GitHub-linked issues AND fingerprint overlaps. AI analyzes actual code diffs. Proposes ONE task group. Uses `aitask_issue_import.sh --merge-issues` to import.

## Key Codebase Integration Points

- **Metadata block**: `aitask_contribute.sh:612-617` — `build_issue_body()` emits `<!-- aitask-contribute-metadata -->`
- **Metadata parser**: `aitask_issue_import.sh:394-419` — `parse_contribute_metadata()` `while/case` loop
- **Platform detection**: `task_utils.sh:85-97` — `detect_platform()` returns `github|gitlab|bitbucket|""`
- **Setup flow**: `aitask_setup.sh` — `install_cli_tools()` already installs `gh`/`glab`/`bkt` per platform
- **Seed templates**: `seed/` — copied during `ait setup`, no CI/CD templates exist yet
- **Scoring reference**: `aitask_reviewguide_scan.sh:215` — `compute_label_overlap()` pattern

## Proposed Child Tasks (7 tasks)

### t355_1: Extend contribute metadata with fingerprint and auto-labels
**Priority: high, Effort: low, Depends: none**

Add fingerprint fields AND auto-label suggestions to `build_issue_body()` in `aitask_contribute.sh`:
```
fingerprint_version: 1
areas: scripts,claude-skills
file_paths: .aitask-scripts/foo.sh,.aitask-scripts/bar.sh
file_dirs: .aitask-scripts
change_type: enhancement
auto_labels: area:scripts,scope:enhancement
```

**Fingerprint fields** computed from existing function arguments:
- `areas`: from `$ARG_AREA` (framework mode) or resolved area name (project mode)
- `file_paths`: sorted `$files` list
- `file_dirs`: unique parent directories from file paths
- `change_type`: from `$scope` (bug-fix, enhancement, new-feature, documentation)

**Auto-labels** derived from areas + scope, embedded as metadata only — NOT applied during issue creation. The CI/CD workflow (t355_4) handles label application.

Files: `aitask_contribute.sh` (build_issue_body), `tests/test_contribute.sh`

### t355_2: Extend metadata parser for fingerprint fields
**Priority: high, Effort: low, Depends: t355_1**

Add parsing for new fields in `parse_contribute_metadata()` in `aitask_issue_import.sh`. New globals: `CONTRIBUTE_FINGERPRINT_VERSION`, `CONTRIBUTE_AREAS`, `CONTRIBUTE_FILE_PATHS`, `CONTRIBUTE_FILE_DIRS`, `CONTRIBUTE_CHANGE_TYPE`, `CONTRIBUTE_AUTO_LABELS`. Backwards compatible — absent fields stay empty.

Files: `aitask_issue_import.sh` (parse_contribute_metadata), tests

### t355_3: Core `aitask_contribution_check.sh` script
**Priority: high, Effort: medium-high, Depends: t355_1**

New portable bash script with encapsulated platform-specific code. All platform-specific operations dispatched through functions (same pattern as `aitask_contribute.sh` and `aitask_issue_import.sh`).

**Platform-agnostic core functions:**
- `parse_fingerprint_from_body()` — extract fingerprint fields from issue body HTML comment
- `compute_overlap_score()` — weighted scoring (file paths × 3, dirs × 2, areas × 2, change type × 1; thresholds: ≥ 4 "likely", ≥ 7 "high")
- `format_overlap_comment()` — generate the markdown comment body with overlap table + label suggestions
- `format_overlap_metadata()` — generate machine-readable `<!-- overlap-results -->` block

**Platform detection:** Two modes:
1. `--platform <github|gitlab|bitbucket>` flag (passed by CI/CD wrappers)
2. `detect_platform()` from git remote URL (when called manually or from skills)

**Encapsulated platform-specific functions** (dispatched via detected platform):
- `source_list_contribution_issues()` → `github_list_contribution_issues()` / `gitlab_list_contribution_issues()` / `bitbucket_list_contribution_issues()`
- `source_post_issue_comment()` → platform-specific comment posting
- `source_apply_issue_labels()` → platform-specific label application
- `source_get_repo_labels()` → check which labels exist on the repo

**Platform API access strategy** (CLI-first, curl fallback):

| Platform | CI/CD Environment | Manual/Skill Environment |
|----------|-------------------|--------------------------|
| GitHub | `gh` CLI (pre-installed on Actions runners) + `$GITHUB_TOKEN` | `gh` CLI (installed by `ait setup`) |
| GitLab | `curl` + GitLab REST API with `$CI_JOB_TOKEN` or `$GITLAB_TOKEN` | `glab` CLI (installed by `ait setup`) |
| Bitbucket | `curl` + Bitbucket REST API with `$BITBUCKET_TOKEN` | `bkt` CLI (installed by `ait setup`) |

Each platform function checks CLI availability first, falls back to `curl` + REST API:
```bash
gitlab_list_contribution_issues() {
    if command -v glab &>/dev/null; then
        glab issue list -l contribution ...
    else
        curl -sH "PRIVATE-TOKEN: ${GITLAB_TOKEN:-$CI_JOB_TOKEN}" \
            "$GITLAB_API/projects/$PROJECT_ID/issues?labels=contribution"
    fi
}
```

GitHub Actions pre-installs `gh`, so no fallback needed. GitLab/Bitbucket CI runners don't pre-install their CLIs, so `curl` fallback avoids adding CLI installation steps to pipelines.

**Input:** `aitask_contribution_check.sh <issue_number> [--repo <owner/repo>] [--platform <github|gitlab|bitbucket>]`

**Output:** Posts comment on the issue with:
- Top 5 overlapping issues (score, link, overlap details)
- Label suggestions (which auto_labels exist on repo → apply; which don't → suggest)
- Machine-readable `<!-- overlap-results top_overlaps: 42:7,38:4 overlap_check_version: 1 -->` block

**Comment format:**
```markdown
## Contribution Analysis

### Overlap Detection
Found 2 potentially overlapping contributions:

| Issue | Score | Overlap Details |
|-------|-------|----------------|
| #42 [Fix auth validation] | 7/10 (high) | Files: `src/auth/login.sh`; Area: `backend/auth` |
| #38 [Update middleware] | 4/10 (likely) | Directory: `src/middleware/` |

### Label Suggestions
- `area:scripts` — exists on repo, **applied**
- `scope:enhancement` — not found on repo

---
*Automated by aitask contribution check*
```

Files: `.aitask-scripts/aitask_contribution_check.sh` (new), `tests/test_contribution_check.sh` (new)

### t355_4: CI/CD wrappers + `ait setup` integration
**Priority: medium, Effort: medium, Depends: t355_3**

**CI/CD wrapper files** (thin — just call the core script):

**GitHub Actions** (`.github/workflows/contribution-check.yml`):
```yaml
on:
  issues:
    types: [opened, labeled]
jobs:
  check:
    if: contains(github.event.issue.labels.*.name, 'contribution')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ./.aitask-scripts/aitask_contribution_check.sh ${{ github.event.issue.number }}
        env:
          GH_TOKEN: ${{ github.token }}
```

**GitLab CI** (added to `.gitlab-ci.yml`):
- Triggered via webhook → pipeline trigger API, or scheduled (every 15 min)
- Scheduled mode: script scans recent issues (last hour) for contribution label, processes each
- Webhook mode: receives `ISSUE_IID` variable from trigger

**Bitbucket Pipelines** (added to `bitbucket-pipelines.yml`):
- Scheduled pipeline only (no issue event triggers)
- Scans recent issues periodically

**`ait setup` additions:**

1. **Create `contribution` label** (platform-aware):
   - GitHub: `gh label create "contribution" --color "0e8a16" --description "External contribution via aitask-contribute" 2>/dev/null || true`
   - GitLab: `glab label create "contribution" --color "#0e8a16" --description "..." 2>/dev/null || true`
   - Bitbucket: skip (no label API)
   - Guard: only attempt if remote is configured and CLI is authenticated
   - If no remote: warn that label must be created manually

2. **Install CI/CD wrapper** (platform-aware):
   - Detect platform via `_detect_git_platform()`
   - GitHub: copy workflow file to `.github/workflows/contribution-check.yml`
   - GitLab: append contribution-check job to `.gitlab-ci.yml`
   - Bitbucket: append scheduled pipeline to `bitbucket-pipelines.yml`
   - Guard: only if user opts in (interactive prompt) or `--with-contribution-check` flag

**Seed templates:**
- `seed/ci/github/contribution-check.yml`
- `seed/ci/gitlab/contribution-check-job.yml` (snippet to append)
- `seed/ci/bitbucket/contribution-check-pipeline.yml` (snippet to append)

Files: `seed/ci/` (new), `.aitask-scripts/aitask_setup.sh`, `.github/workflows/contribution-check.yml`

### t355_5: Add `--merge-issues` capability to `aitask_issue_import.sh`
**Priority: medium, Effort: medium, Depends: t355_2**

Add `--merge-issues N1,N2,...` flag to import multiple contribution issues as a single task.

**Merge logic:**
- Fetch all specified issues
- Combine descriptions with clear section boundaries (each issue as a subsection)
- Union file lists and diffs
- Resolve conflicting metadata: highest priority, highest effort, union of labels
- Track all source issue URLs: new `related_issues:` list field in frontmatter (primary issue URL stays in `issue:`)
- Post comment on each source issue linking to the created task

**Multi-contributor attribution:**
- Identify **primary contributor** (largest diff contribution by line count among grouped issues)
- Primary contributor stored in `contributor`/`contributor_email` (backwards compatible with existing Contributor Attribution Procedure)
- Additional contributors stored in new `contributors:` YAML list field:
  ```yaml
  contributors:
    - name: bob
      email: bob@example.com
      issue: https://github.com/owner/repo/issues/38
    - name: charlie
      email: charlie@example.com
      issue: https://github.com/owner/repo/issues/15
  ```
- Task-workflow Contributor Attribution Procedure updated: primary contributor gets `Co-Authored-By` trailer, others listed in commit body text (`Also based on contributions from: bob (#38), charlie (#15)`)

Files: `aitask_issue_import.sh`, possibly `aitask_create.sh` (multi-issue field), `procedures.md` (attribution update), tests

### t355_6: New `aitask-contribution-review` skill
**Priority: medium, Effort: high, Depends: t355_3, t355_5**

New AI-driven Claude Code skill at `.claude/skills/aitask-contribution-review/SKILL.md`.

**Input:** Single issue number (e.g., `/aitask-contribution-review 42`)

**Flow:**
1. **Fetch target issue** via platform CLI
2. **Parse fingerprint metadata** from issue body
3. **Gather related issues from two sources:**
   a. **Platform-linked issues:** Parse issue body + comments for issue references; check if they're contribution issues
   b. **Fingerprint-overlapping issues:** Parse the bot comment's `<!-- overlap-results -->` block for top overlap issue numbers + scores
4. **Fetch related issue details:** For each candidate, fetch body including code diffs (from `<!-- full-diff:... -->` blocks)
5. **AI analysis of actual code modifications:**
   - Are they touching the same files/functions?
   - Are they fixing the same bug in different ways?
   - Are they complementary changes that should be merged?
   - Are they unrelated despite fingerprint similarity?
6. **Present proposal to user** (AskUserQuestion):
   - "Group these issues into one task: #42, #38, #15" → merge import
   - "Issue #42 is independent" → single import
   - "Skip — don't import yet"
7. **Execute import:**
   - If grouping: `aitask_issue_import.sh --merge-issues 42,38,15 --commit`
   - If single: `aitask_issue_import.sh 42 --commit`
   - **ONE task group per skill run, never more**

Files: `.claude/skills/aitask-contribution-review/SKILL.md` (new)

### t355_7: Documentation + seed distribution
**Priority: low, Effort: low, Depends: t355_4, t355_6**

- Document the contribution analysis workflow in `website/content/docs/workflows/`
- Document the fingerprint metadata format for third-party tools
- Document the `aitask-contribution-review` skill usage
- Document that `contribution` label is assumed to exist (created by `ait setup` or manually)
- Update existing `aitask-contribute` docs to reference fingerprint/overlap features
- Add setup instructions for each platform (GitHub, GitLab, Bitbucket)

Files: `website/content/docs/`, skill SKILL.md files

## Dependency Graph

```
t355_1 (fingerprint + auto_labels in metadata)
   |
   +-----------+-----------+
   |                       |
   v                       v
t355_2                  t355_3
(extend parser)         (core check script)
   |                       |
   v                       v
t355_5                  t355_4
(--merge-issues)        (CI/CD wrappers + setup)
   |                       |
   +--------+--------------+
            |
            v
         t355_6
   (contribution-review skill)
            |
            v
         t355_7
         (documentation)
```

## Contributor Attribution for Merged Issues

The current task-workflow supports one contributor per task (`contributor`/`contributor_email` scalar fields). For merged issues:

- **New frontmatter field:** `contributors:` — YAML list of `{name, email, issue}` for secondary contributors
- **Primary contributor** stays in `contributor`/`contributor_email` (backwards compatible)
- **Commit message:** Primary contributor gets `Co-Authored-By` trailer; others in body text:
  ```
  feature: Implement auth validation (t42)

  Based on contribution issues: #42, #38, #15
  Also based on contributions from: bob (#38), charlie (#15)

  Co-Authored-By: alice <alice@example.com>
  Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
  ```

## Backwards Compatibility

- **Old issues without fingerprints**: parser returns empty fields, overlap score = 0 (no false matches)
- **fingerprint_version**: enables future schema evolution
- **CI/CD workflow guard**: only processes issues containing `aitask-contribute-metadata`
- **Label application**: workflow only applies labels that already exist on the repo — never creates labels
- **--merge-issues**: optional flag, existing single-issue import unchanged
- **contributors field**: new optional field, existing single-contributor flow unaffected

## Platform Support Matrix

| Feature | GitHub | GitLab | Bitbucket |
|---------|--------|--------|-----------|
| Contribution label creation | `gh label create` | `glab label create` | N/A (no label API) |
| Issue event trigger | Native (Actions) | Webhook → pipeline trigger | N/A |
| Scheduled scan | Supported | Supported | Supported |
| Post issue comment | `gh issue comment` | `glab issue note` | `bkt issue comment` |
| Apply labels | `gh issue edit --add-label` | `glab issue update --label` | N/A |

## Implementation Approach

The deliverable for t355 is **updating the task file** with this design, then **creating the 7 child tasks** using `aitask_create.sh --batch --parent 355`. No code changes in this task — code changes happen in the child tasks.

## Verification

1. Verify all 7 child task files created in `aitasks/t355/`
2. Verify dependency graph is correctly set in frontmatter `depends:` fields
3. Verify task descriptions include enough context for independent execution
4. Review with `./ait ls --children 355` to confirm prioritization
