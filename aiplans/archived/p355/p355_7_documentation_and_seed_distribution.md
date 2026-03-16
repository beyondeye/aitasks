---
Task: t355_7_documentation_and_seed_distribution.md
Parent Task: aitasks/t355_check_for_existing_issues_overlap.md
Sibling Tasks: aitasks/t355/t355_7_documentation_and_seed_distribution.md
Archived Sibling Plans: aiplans/archived/p355/p355_1_*.md through p355_6_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: t355_7 — Documentation and Seed Distribution

## Context

Tasks t355_1 through t355_6 built a three-layer contribution analysis system: fingerprint metadata in issues, automated CI/CD overlap scoring, and an AI-powered review skill. The existing `contribute-and-manage.md` workflow page predates these additions and needs comprehensive updates. This task creates documentation for the full incoming contribution analysis workflow and updates all affected pages.

## Documentation Structure

- Convert `contribute-and-manage.md` → `contribute-and-manage/_index.md` (directory with subpages)
- Add `contribution-flow.md` subpage documenting the full contribution analysis workflow
- Add `aitask-contribution-review.md` skill page
- Update `aitask-contribute.md` skill page

## Files to Create/Modify

### 1. Convert `contribute-and-manage.md` → `_index.md` + update content

**Move:** `website/content/docs/workflows/contribute-and-manage.md` → `website/content/docs/workflows/contribute-and-manage/_index.md`

**Content updates to `_index.md`:**

**a. Intro paragraph (line 8):**
- "Three complementary features" → "Four complementary features"

**b. "The Three Paths" → "The Four Paths" — add 4th path after path 3:**

```markdown
### 4. Review and Import Contributions — `/aitask-contribution-review`

The [`/aitask-contribution-review`](../../skills/aitask-contribution-review/) skill provides AI-powered review of contribution issues. It fetches the target issue, searches for duplicates and related contributions (using fingerprint overlap scores and linked issue references), analyzes code diffs, and recommends whether to merge multiple issues into one task, import individually, fold into existing tasks, or update an existing task directly.

**Who uses it:** Maintainers reviewing incoming contribution issues.

**Flow:**
```
Contribution issue → /aitask-contribution-review → Duplicate check → Overlap analysis
    → AI diff review → Merge/single/fold/update decision → ait issue-import → aitask
```

See [Contribution Flow](contribution-flow/) for the full workflow and technical details.
```

**c. Path 3 description (lines 39-52):** Add after step 5:
```
6. The issue includes fingerprint metadata (areas, file paths, change type) that enables automatic overlap detection
```

**d. End-to-End Lifecycle diagram (lines 54-82):** Replace with updated version showing the new steps:

```
Contributor's local repo                      Destination repository
──────────────────────                        ──────────────────────

1. Make local modifications
        │
2. /aitask-contribute
        │
3. AI analyzes changes ──────────────────────► Issue created (GH/GL/BB)
   + embeds fingerprint metadata                with fingerprint metadata
                                                       │
                                            3a. CI/CD overlap analysis
                                                (automatic, if configured)
                                                       │
                                               4. /aitask-contribution-review
                                                  - duplicate check
                                                  - related issue search
                                                  - AI diff analysis
                                                       │
                                               5. Import decision
                                                  (merge / single / fold /
                                                   update existing)
                                                       │
                                               6. aitask created (with
                                                  contributor metadata)
                                                       │
                                               7. /aitask-pick
                                                       │
                                               8. Implementation
                                                       │
                                               9. Commit with
                                                  Co-authored-by trailer
                                                       │
                                              10. Issue auto-closed
                                                  with notes
```

**e. Contributor Attribution (lines 84-98):** Update to mention multi-contributor attribution:
- After the existing 3-step flow, add note about merged imports:

```markdown
For merged contributions (multiple issues imported as one task via `/aitask-contribution-review`):
- The primary contributor (largest diff) gets the `Co-authored-by` trailer
- Additional contributors are listed in the commit body
- All source issue URLs are stored in the task's `related_issues` frontmatter
```

**f. Comparison table (lines 100-110):** Update the `/aitask-contribute` column to reflect the full workflow (including overlap detection and review on the maintainer side):

| Aspect | Traditional PR | `/aitask-contribute` workflow |
|--------|---------------|-------------------------------|
| Requires fork | Yes | No |
| Requires branch | Yes | No |
| Code review | Manual PR review | AI-powered analysis + overlap detection |
| Duplicate detection | Manual | Automatic (fingerprint scoring + AI review) |
| Merge | Direct merge or rebase | Re-implemented through aitask workflow |
| Attribution | Git history | `Co-authored-by` trailer (multi-contributor for merged imports) |
| Multiple changes | One PR per change | Multiple issues from one session, grouped automatically |
| Maintainer effort | Review + merge | AI-assisted review → import → implement |

**g. "When to Use Each Path" (lines 112-117):** Add 4th entry:
```markdown
- **Review and Import Contributions** — When multiple contribution issues may overlap or when you want AI-assisted analysis before importing
```

### 2. `website/content/docs/workflows/contribute-and-manage/contribution-flow.md`

New subpage.

**Frontmatter:**
```yaml
---
title: "Contribution Flow"
linkTitle: "Contribution Flow"
weight: 10
description: "How incoming contribution issues are analyzed for duplicates, scored for overlap, and reviewed with AI"
---
```

**Content sections:**

1. **Overview** — The contribution analysis workflow on the receiving side: once a contribution issue arrives, the system can automatically detect overlaps (CI/CD layer) and maintainers can review with AI assistance (review skill).

2. **Fingerprint Metadata** — Format of the `<!-- aitask-contribute-metadata -->` block (all fields: `contributor`, `contributor_email`, `based_on_version`, `fingerprint_version`, `areas`, `file_paths`, `file_dirs`, `change_type`, `auto_labels`). Embedded automatically by `/aitask-contribute`. Version scheme (`fingerprint_version: 1`).

3. **Automated Overlap Analysis** — CI/CD workflow that runs on new contribution issues:
   - Scoring: file path ×3, directory ×2, area ×2, change type ×1
   - Thresholds: ≥7 "high", 4-6 "likely", <4 filtered
   - Bot comment with overlap table + label suggestions
   - Machine-readable: `<!-- overlap-results top_overlaps: N:S,N:S overlap_check_version: 1 -->`
   - Idempotent (skips if comment already posted)
   - CLI: `aitask_contribution_check.sh <issue> [--platform P] [--repo R] [--limit N] [--dry-run] [--silent]`

4. **Reviewing with `/aitask-contribution-review`** — Full 10-step workflow:
   - Issue resolution (argument or interactive listing)
   - Validation + metadata extraction
   - Duplicate import check (prevents re-importing already-imported issues)
   - Related issue gathering from overlap scores and linked issue references
   - Optional local overlap check when CI/CD bot comment is missing
   - Candidate summary table presentation
   - AI diff analysis (same files? same bug? complementary? unrelated?)
   - Import decision: merge multiple / single / skip
   - Overlapping existing tasks: fold into new / update existing / ignore
   - Multi-contributor attribution for merged imports

5. **CI/CD Setup** — Per-platform configuration:
   - **GitHub Actions**: `issues.labeled` event trigger, `$GITHUB_TOKEN` auto-provided, `gh` CLI pre-installed, no extra setup needed
   - **GitLab CI**: Requires `$GITLAB_TOKEN` project access token with `api` scope (NOT `CI_JOB_TOKEN`), webhook-triggered or scheduled mode, uses `glab` CLI or curl fallback
   - **Bitbucket Pipelines**: Requires `$BITBUCKET_API_USER` + `$BITBUCKET_API_TOKEN`, scheduled scan only (no event triggers), curl-only (no CLI), no label API support
   - `ait setup` auto-detects platform, creates `contribution` label, installs CI/CD workflow
   - Manual setup instructions for each platform (without `ait setup`)

6. **Platform Support Matrix** — Table covering: label filtering, event-driven triggers, scheduled scans, CLI tool, token source, label creation, comment posting

7. **Programmatic Integration** — Machine-readable formats for third-party tools: `<!-- aitask-contribute-metadata ... -->` and `<!-- overlap-results ... -->` field specs

### 3. `website/content/docs/skills/aitask-contribution-review.md` (weight: 24)

New skill page after `aitask-contribute.md` (weight: 23).

**Sections:**
- Usage: `/aitask-contribution-review <issue_number>` or `/aitask-contribution-review` (interactive)
- Note: Requires platform CLI (`gh`/`glab`), same as `/aitask-contribute`
- Step-by-step summary of the full workflow
- Key capabilities (platform-agnostic, duplicate detection, overlap analysis, merge/fold/update, multi-contributor attribution)
- Note: Produces at most one task per invocation
- Workflows link to contribute-and-manage + contribution-flow

### 4. `website/content/docs/skills/aitask-contribute.md`

Add to "Key Capabilities" list:
```markdown
- **Embeds fingerprint metadata** — Each contribution includes fingerprint data (areas, file paths, directories, change type) that enables automatic overlap detection on the receiving side. See [Contribution Flow](../../workflows/contribute-and-manage/contribution-flow/) for details.
```

## Implementation Steps

### Step 1: Convert contribute-and-manage to directory
```bash
mkdir -p website/content/docs/workflows/contribute-and-manage
mv website/content/docs/workflows/contribute-and-manage.md website/content/docs/workflows/contribute-and-manage/_index.md
```

### Step 2: Update `_index.md` with all changes (a-g above)

### Step 3: Create `contribution-flow.md` subpage

### Step 4: Create `aitask-contribution-review.md` skill page

### Step 5: Update `aitask-contribute.md` skill page

### Step 6: Build verification
```bash
cd website && hugo build --gc --minify
```

## Verification

1. `cd website && hugo build --gc --minify` — builds without errors
2. Verify `/docs/workflows/contribute-and-manage/` still renders correctly
3. Verify `/docs/workflows/contribute-and-manage/contribution-flow/` renders
4. Verify `/docs/skills/aitask-contribution-review/` renders
5. Check all cross-links resolve (contribute → contribution-flow → review skill)
6. Cross-check documented steps, scoring formula, CLI flags, and platform details against actual `.aitask-scripts/` and `.claude/skills/` implementations

## Final Implementation Notes
- **Actual work done:** Converted `contribute-and-manage.md` to a directory with `_index.md` (updated with 4th path, new lifecycle diagram, multi-contributor attribution, updated comparison table) + `contribution-flow.md` subpage (full technical docs: fingerprint metadata format, overlap scoring, 10-step review skill workflow, per-platform CI/CD setup, platform matrix, programmatic integration). Created `aitask-contribution-review.md` skill page. Updated `aitask-contribute.md` with fingerprint metadata bullet. Hugo builds clean (110 pages).
- **Deviations from plan:** User feedback shaped the approach: (1) detail page is a subpage of contribute-and-manage rather than a standalone workflow page; (2) named `contribution-flow` not `contribution-overlap` to reflect the full workflow focus; (3) comparison table updated as a single column reflecting the full `/aitask-contribute` workflow rather than adding a separate `/aitask-contribution-review` column (since they're part of the same workflow).
- **Issues encountered:** None. Hugo build succeeded on first attempt.
- **Key decisions:** Reviewed the actual current SKILL.md of `/aitask-contribution-review` (significantly evolved from original task spec — includes Steps 0/1b/5b/6b, subcommands `list-issues`/`check-imported`/`post-comment`). Documented all 10 current workflow steps. The "seed distribution" part of the task title was already handled by t355_4 (CI/CD templates in `seed/ci/`) — this task documents how those templates work.
- **Notes for sibling tasks:** This is the final child task (t355_7). All documentation now references actual implementation from t355_1-6. The conversion to a directory (`contribute-and-manage/`) means any existing links to `/docs/workflows/contribute-and-manage/` still work (Hugo serves `_index.md` at the directory URL).
