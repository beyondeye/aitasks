---
priority: medium
effort: high
depends: [3, 5]
issue_type: feature
status: Implementing
labels: [aitask_contribute]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-10 10:58
updated_at: 2026-03-11 14:00
---

## Context

This task creates a new AI-driven Claude Code skill `aitask-contribution-review` that analyzes a contribution issue, gathers related issues (from platform links and fingerprint overlaps), and proposes ONE task group for import. It uses the core contribution check script (t355_3) for fingerprint data and the merge-issues capability (t355_5) for grouped imports.

This is the reviewer's primary tool for processing contribution issues intelligently.

## Key Files to Create

- `.claude/skills/aitask-contribution-review/SKILL.md` — new skill definition

## Reference Files for Patterns

- `.claude/skills/aitask-contribute/SKILL.md` — existing skill with multi-step interactive workflow
- `.claude/skills/aitask-pr-import/SKILL.md` — existing skill for importing PRs (similar flow: fetch → analyze → import)
- `.aitask-scripts/aitask_contribution_check.sh` — core script (t355_3) for fingerprint overlap data
- `.aitask-scripts/aitask_issue_import.sh` — import script with `--merge-issues` flag (t355_5)

## Implementation Plan

### Skill definition: `.claude/skills/aitask-contribution-review/SKILL.md`

```yaml
---
name: aitask-contribution-review
description: Analyze a contribution issue, find related issues, and import as grouped or single task.
user-invocable: true
arguments: "<issue_number>"
---
```

### Workflow steps:

**Step 1: Fetch target issue**
- Use platform CLI to fetch the issue: `gh issue view <N> --json title,body,comments,labels,url`
- Verify it has `aitask-contribute-metadata` block (is a contribution issue)
- Parse the fingerprint metadata from the body

**Step 2: Gather related issues from two sources**

a. **Platform-linked issues:**
   - Parse the issue body and all comments for issue references (#N patterns)
   - For each referenced issue, check if it's also a contribution issue (fetch and check for metadata block)
   - Filter to only open contribution issues

b. **Fingerprint-overlapping issues:**
   - Look for the bot comment containing `<!-- overlap-results -->` (posted by the CI/CD workflow from t355_4)
   - Parse the `top_overlaps:` field: format is `issue_num:score,issue_num:score,...`
   - Filter to issues with score ≥ 4 (likely overlap threshold)
   - If no bot comment exists (workflow not set up), run the core script in dry-run mode to compute overlaps locally

**Step 3: Fetch related issue details**
- For each candidate related issue, fetch the full body
- Extract code diffs from:
  - Inline diff blocks (```diff sections)
  - Hidden full diffs in `<!-- full-diff:filename ... -->` HTML comment blocks
- Present a summary of each candidate: issue number, title, contributor, overlap score, changed files

**Step 4: AI analysis of code modifications**
- Read the actual diffs from all candidate issues
- Analyze:
  - Are they touching the same files/functions? (strongest merge signal)
  - Are they fixing the same bug in different ways? (merge: pick best approach)
  - Are they complementary changes? (merge: combine)
  - Are they unrelated despite fingerprint similarity? (don't merge)
- Generate a recommendation with rationale

**Step 5: Present proposal to user (AskUserQuestion)**
- If merge recommended:
  - "Group these issues into one task: #42, #38, #15 — [rationale]"
  - Options: "Import as merged task" / "Import only #42 (single)" / "Skip — don't import yet"
- If no merge:
  - "Issue #42 appears independent — no related contributions found"
  - Options: "Import as single task" / "Skip — don't import yet"

**Step 6: Execute import**
- If grouping approved: `./.aitask-scripts/aitask_issue_import.sh --merge-issues 42,38,15 --commit`
- If single import: `./.aitask-scripts/aitask_issue_import.sh 42 --commit`
- **ONE task group per skill run, never more**
- Display the created task file path

**Key constraint:** The skill produces at most ONE task. To process multiple unrelated contribution issues, run the skill multiple times.

## Verification Steps

1. Test with a real contribution issue on a test repo
2. Verify the skill correctly identifies linked and overlapping issues
3. Verify merge import creates a properly formatted task file
4. Verify single import works correctly when no merge is needed
