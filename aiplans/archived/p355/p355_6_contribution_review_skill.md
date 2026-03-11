---
Task: t355_6_contribution_review_skill.md
Parent Task: aitasks/t355_check_for_existing_issues_overlap.md
Sibling Tasks: aitasks/t355/t355_7_documentation_and_seed_distribution.md
Archived Sibling Plans: aiplans/archived/p355/p355_1_*.md through p355_5_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

This is child task t355_6 of the contribution toolkit (t355). Previous siblings built:
- t355_1/t355_2: Fingerprint metadata in `<!-- aitask-contribute-metadata -->` blocks with 8 CONTRIBUTE_* globals
- t355_3: `aitask_contribution_check.sh` — overlap scoring, bot comment posting with `<!-- overlap-results top_overlaps: N:S,N:S -->` machine-readable block. **Has BASH_SOURCE guard on main() — designed to be sourced by t355_6.**
- t355_4: CI/CD wrappers that trigger the check script on issue open/label events
- t355_5: `--merge-issues N1,N2,...` flag in `aitask_issue_import.sh` for grouped imports

This task creates the **reviewer's primary tool** — a Claude Code skill backed by a helper script that encapsulates platform-specific issue fetching.

## Files to Create

1. `.aitask-scripts/aitask_contribution_review.sh` — Helper script that sources `aitask_contribution_check.sh` for platform backends
2. `.claude/skills/aitask-contribution-review/SKILL.md` — Skill definition that calls the helper script
3. `tests/test_contribution_review.sh` — Tests for the helper script

## Files to Modify

None — `aitask_contribution_check.sh` already has the BASH_SOURCE guard and all needed platform backends.

## Reference Files

- `.aitask-scripts/aitask_contribution_check.sh` — Source for platform backends (BASH_SOURCE guarded). Functions: `source_fetch_issue()`, `source_check_cli()`, `source_list_contribution_issues()`, `compute_overlap_score()`, `classify_overlap()`. Uses `CHECK_PLATFORM` global + `ARG_REPO`, `ARG_LIMIT` globals.
- `.aitask-scripts/lib/task_utils.sh:452-501` — `parse_contribute_metadata()` sets CONTRIBUTE_* globals
- `.aitask-scripts/lib/task_utils.sh:85-97` — `detect_platform()` returns github|gitlab|bitbucket
- `.aitask-scripts/aitask_issue_import.sh` — `--merge-issues` and `--issue` batch flags for import execution
- `.claude/skills/aitask-pr-import/SKILL.md` — Closest structural analog (fetch → analyze → import)

## Implementation Plan

### Step 1: Create `.aitask-scripts/aitask_contribution_review.sh`

Helper script that encapsulates all platform-specific operations. Sources `aitask_contribution_check.sh` (which has BASH_SOURCE guard) to reuse its platform backends.

**Design:**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/task_utils.sh"

# Source contribution_check for platform backends (BASH_SOURCE guarded)
source "$SCRIPT_DIR/aitask_contribution_check.sh"
```

**Globals:** `REVIEW_PLATFORM=""`, `REVIEW_REPO=""`, `REVIEW_LIMIT=50`

**Subcommands:**

#### `fetch <issue_num> [--platform P] [--repo R]`

Fetches a single issue with body and comments. Since `source_fetch_issue()` from contribution_check only returns `{number, title, body, labels, url}` (no comments), add platform-specific comment fetching:

- GitHub: `gh issue view <N> --json number,title,body,labels,url,comments,state`
- GitLab: `source_fetch_issue` + separate notes API call
- Bitbucket: `source_fetch_issue` + separate comments API call

Output format (structured, one field per line):
```
ISSUE_JSON:<full json with body and comments>
HAS_METADATA:true|false
CONTRIBUTOR:<name>
EMAIL:<email>
AREAS:<comma-separated>
FILE_PATHS:<comma-separated>
FILE_DIRS:<comma-separated>
CHANGE_TYPE:<type>
```

After fetching, calls `parse_contribute_metadata()` on the body and outputs parsed fields.

#### `find-related <issue_num> [--platform P] [--repo R]`

Finds related contribution issues from two sources:

**a. Bot comment overlap results:**
- Parse comments JSON for `<!-- overlap-results` marker
- Extract `top_overlaps:` field (format: `N:S,N:S,...`)
- Filter to score >= 4
- Output: `OVERLAP:<issue_num>:<score>` per line

**b. Linked issues from body/comments:**
- Scan body + all comments for `#(\d+)` patterns
- Exclude self-references and obvious non-issue refs
- For each candidate, fetch and check for `<!-- aitask-contribute-metadata` block
- Output: `LINKED:<issue_num>:<title>` per line

**c. If no bot comment found:**
- Output: `NO_BOT_COMMENT` line
- The skill can then decide to run `aitask_contribution_check.sh --dry-run` or proceed without overlap data

**d. Final deduplication:**
- If an issue appears in both sources, output: `BOTH:<issue_num>:<score>:<title>`

Output footer:
```
TOTAL_CANDIDATES:<count>
```

#### `fetch-multi <N1,N2,...> [--platform P] [--repo R]`

Fetches multiple issues for AI analysis. For each issue:
- Fetch full body via `source_fetch_issue()`
- Parse metadata
- Output per issue:
```
@@@ISSUE:<num>@@@
TITLE:<title>
CONTRIBUTOR:<name>
>>>BODY_START
<full body including diffs>
<<<BODY_END
```

This gives the skill the raw content needed for diff analysis.

#### `--help`

Standard help text documenting all subcommands and options.

**Key implementation details:**
- Set `CHECK_PLATFORM` (from contribution_check globals) before calling `source_*` dispatchers
- Set `ARG_REPO` for cross-repo operation
- Set `ARG_LIMIT` for issue listing limit
- BASH_SOURCE guard on `main()` for testability
- Platform-specific comment fetch functions: `review_github_fetch_comments()`, `review_gitlab_fetch_comments()`, `review_bitbucket_fetch_comments()` — these extend beyond what contribution_check provides

### Step 2: Create `.claude/skills/aitask-contribution-review/SKILL.md`

The skill orchestrates the helper script and AI analysis.

**Frontmatter:**
```yaml
---
name: aitask-contribution-review
description: Analyze a contribution issue, find related issues, and import as grouped or single task.
user-invocable: true
arguments: "<issue_number>"
---
```

**Workflow Steps:**

**Step 1: Validate and Fetch Target Issue**

```bash
./.aitask-scripts/aitask_contribution_review.sh fetch <N>
```

Parse structured output. If `HAS_METADATA:false`, inform user and abort. Display summary: issue number, contributor, areas, change type.

**Step 2: Gather Related Issues**

```bash
./.aitask-scripts/aitask_contribution_review.sh find-related <N>
```

Parse output lines for `OVERLAP:`, `LINKED:`, `BOTH:` entries.

If `NO_BOT_COMMENT` in output, offer to run local overlap check:
```bash
./.aitask-scripts/aitask_contribution_check.sh <N> --dry-run --silent
```
Parse the dry-run output for `<!-- overlap-results top_overlaps: ... -->` line.

If `TOTAL_CANDIDATES:0`, skip to Step 5 (single import recommendation).

**Step 3: Fetch Related Issue Details**

Collect candidate issue numbers from Step 2. Fetch them all:
```bash
./.aitask-scripts/aitask_contribution_review.sh fetch-multi <N1>,<N2>,<N3>
```

Parse structured output. Extract diffs from bodies (inline ` ```diff ` blocks and `<!-- full-diff:filename -->` HTML comments).

Present summary table to user:
```
| Issue | Title | Contributor | Source | Score | Changed Files |
|-------|-------|-------------|--------|-------|---------------|
```

**Step 4: AI Analysis of Code Modifications**

Read the actual diffs from all candidate issues plus the target. Analyze:
- Same files/functions touched? (strongest merge signal)
- Same bug fixed differently? (merge: pick best)
- Complementary changes? (merge: combine)
- Unrelated despite fingerprint similarity? (don't merge)

Generate structured recommendation with rationale.

**Step 5: Present Proposal to User (AskUserQuestion)**

a. If merge recommended:
   - Question: "Group these issues into one task: #42, #38, #15 — [rationale]"
   - Options: "Import as merged task" / "Import only #\<target\>" / "Skip"

b. If no merge:
   - Question: "Issue #N appears independent — no related contributions found worth merging"
   - Options: "Import as single task" / "Skip"

**Step 6: Execute Import**

- Merged: `./.aitask-scripts/aitask_issue_import.sh --batch --merge-issues <N1>,<N2>,<N3> --commit`
- Single: `./.aitask-scripts/aitask_issue_import.sh --batch --issue <N> --commit`
- Skip: End workflow

Display created task file path. **Key constraint:** ONE task per run.

**Notes section:** Document the skill produces at most one task per invocation, no execution profiles, no handoff to task-workflow (import-only), platform detection via helper script, score thresholds (>=7 "high", >=4 "likely", <4 "low").

### Step 3: Create `tests/test_contribution_review.sh`

Standard test pattern (assert_eq/assert_contains, PASS/FAIL counters).

Test cases:
1. `bash -n` syntax check
2. `--help` exits 0 with usage text
3. Parse bot comment for overlap results (mock comment with `<!-- overlap-results top_overlaps: 42:7,38:4 -->`)
4. Parse body for linked issue references (`#42`, `#38` patterns)
5. Handle missing bot comment (outputs `NO_BOT_COMMENT`)
6. Handle body without metadata (outputs `HAS_METADATA:false`)
7. Deduplication logic (issue in both overlap + linked → `BOTH:` line)

Source the script via BASH_SOURCE guard to test functions directly.

### Step 4: Add to allowlist files

Add `aitask_contribution_review.sh` to the script allowlists:
- `seed/claude/settings.local.json`
- `.claude/settings.local.json`
- Check if Gemini/OpenCode allowlists exist and add there too (same pattern as t355_3)

### Step 5: Commit

```bash
git add .aitask-scripts/aitask_contribution_review.sh tests/test_contribution_review.sh
git add .claude/skills/aitask-contribution-review/SKILL.md
git add seed/claude/settings.local.json .claude/settings.local.json
# Add other allowlist files if modified
```

## Verification

1. `bash -n .aitask-scripts/aitask_contribution_review.sh`
2. `shellcheck .aitask-scripts/aitask_contribution_review.sh`
3. `bash tests/test_contribution_review.sh`
4. `./.aitask-scripts/aitask_contribution_review.sh --help` — exits 0
5. Verify skill appears in Claude Code available skills
6. Verify all referenced scripts accept documented flags

## Final Implementation Notes

- **Actual work done:** Created `aitask_contribution_review.sh` (~340 lines) with 3 subcommands (`fetch`, `find-related`, `fetch-multi`), comment-fetching platform backends for GitHub/GitLab/Bitbucket, overlap parsing, and linked issue detection. Created `SKILL.md` with 6-step workflow (validate → gather related → fetch details → AI analysis → propose → import). Created test suite with 32 assertions. Added script to all 5 allowlist files (seed: claude, opencode, gemini; active: claude; gemini skill activation).
- **Deviations from plan:** Plan mentioned `review_github_fetch_comments()`, `review_gitlab_fetch_comments()`, `review_bitbucket_fetch_comments()` — implemented as designed. GitLab uses `glab issue view` with `.notes[]` extraction or curl fallback to notes API. Bitbucket uses curl to comments API. No structural deviations.
- **Issues encountered:** Test 9 (no linked issues) initially failed because `grep -c '[0-9]' || echo "0"` on empty input produced double "0" output. Fixed by checking for empty result before calling grep. Shellcheck SC2034 warning for `ARG_LIMIT` — suppressed with inline disable comment since the variable is used by sourced `aitask_contribution_check.sh` backends.
- **Key decisions:** Sourced `aitask_contribution_check.sh` directly (BASH_SOURCE guarded) rather than extracting functions to a shared lib — keeps changes minimal and builds on the explicit design from t355_3 which noted "BASH_SOURCE guard on main() is essential for t355_6". Added separate comment-fetching functions (`review_*_fetch_comments()`) since `source_fetch_issue()` from contribution_check only returns `{number, title, body, labels, url}` without comments.
- **Notes for sibling tasks:** The `aitask_contribution_review.sh` script sets `CHECK_PLATFORM`, `ARG_REPO`, and `ARG_LIMIT` globals from its own `REVIEW_*` variables before calling sourced `source_*` dispatchers. The skill SKILL.md is a standalone skill with no execution profiles or task-workflow handoff — it only creates tasks via `aitask_issue_import.sh` batch mode. t355_7 (documentation) should document the `aitask-contribution-review` skill usage and the helper script's subcommand interface.
