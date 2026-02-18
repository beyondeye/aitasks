---
Task: t163_5_merge_skill.md
Parent Task: aitasks/t163_review_modes_consolidate.md
Sibling Tasks: (none pending)
Archived Sibling Plans: aiplans/archived/p163/p163_1_vocabulary_files_and_install.md, aiplans/archived/p163/p163_2_add_reviewmode_metadata.md, aiplans/archived/p163/p163_3_reviewmode_scan_script.md, aiplans/archived/p163/p163_4_classify_skill.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Child task t163_5 of the review modes consolidation (t163). Creates a new Claude Code skill `.claude/skills/aitask-reviewmode-merge/SKILL.md` for comparing two similar reviewmode files and merging, deduplicating, or keeping them separate. The classify skill (t163_4) populates `similar_to` fields; this skill acts on those to consolidate overlapping review modes.

## Plan

### 1. Create skill directory and file

```bash
mkdir -p .claude/skills/aitask-reviewmode-merge
```

Create `.claude/skills/aitask-reviewmode-merge/SKILL.md` — single new file, the only deliverable.

### 2. Skill file structure

**Frontmatter:**
```yaml
---
name: aitask-reviewmode-merge
description: Compare two similar review mode files and merge, split, or keep separate.
---
```

**Step numbering follows classify skill convention:** Steps 1-7 for single-pair mode, Steps 8-13 for batch mode.

#### Steps 1-7: Single-Pair Mode

- Step 1: Mode Selection (two args → both fzf, one arg → fzf + similar_to, no args → batch)
- Step 2: Resolve Input Files (fzf pattern from classify skill)
- Step 3: Detailed Comparison (parse H2/H3 bullets, categorize as duplicate/unique, compute overlap %)
- Step 4: Propose Action (>70% merge, 30-70% either, <30% keep separate)
- Step 5: User Selection (AskUserQuestion: Merge A / Merge B / Keep separate / Cancel)
- Step 6: Execute Action (merge content + cleanup, or deduplicate)
- Step 7: Summary

#### Steps 8-13: Batch Mode

- Step 8: Find candidates via `--find-similar`
- Step 9: Optional environment filter
- Step 10: Present pairs with pagination
- Step 11: Execute single-pair workflow
- Step 12: Loop (re-run --find-similar after each merge)
- Step 13: Batch summary

### 3. Key design decisions

- **No seed sync**: Like classify, only writes to `aitasks/metadata/`. Seed managed separately.
- **No "split" in v1**: Options are merge/keep-separate/cancel only.
- **Semantic comparison**: LLM compares bullets by meaning, not string match.
- **Per-pair commits in batch**: Each merge committed individually.
- **similar_to cleanup**: Update dangling references after file deletion.

### Critical Files

| File | Action |
|------|--------|
| `.claude/skills/aitask-reviewmode-merge/SKILL.md` | **new** (main deliverable) |

### Verification

1. Read skill file and verify classify skill conventions
2. Verify script paths and output format references
3. Compare step structure for consistency
4. Verify commit message format
5. Verify vocabulary file update paths use `aitasks/metadata/reviewmodes/*.txt`

## Final Implementation Notes

- **Actual work done:** Created `.claude/skills/aitask-reviewmode-merge/SKILL.md` (280 lines) with single-pair mode (Steps 1-7: fzf resolution, semantic bullet comparison, merge/keep-separate execution) and batch mode (Steps 8-13: --find-similar scanning, environment filtering, pagination, looping). Also created two test reviewmode files for manual testing.
- **Deviations from plan:** (1) No seed sync per user feedback — skill only writes to `aitasks/metadata/`, consistent with classify skill pattern. The original task spec called for seed sync but user overrode this.
- **Issues encountered:** None. Single file creation, straightforward implementation.
- **Key decisions:** Followed classify skill conventions exactly (frontmatter, step numbering 1-7/8-13, fzf resolution, AskUserQuestion patterns). Semantic bullet comparison done by the LLM, not string matching. Per-pair commits in batch mode for clean git history.
- **Notes for sibling tasks:** This is the last child task of t163. The merge skill does NOT modify seed (same as classify). Vocabulary file paths are `aitasks/metadata/reviewmodes/*.txt`. Test files (`test_security_expanded.md`, `test_code_quality.md`) should be deleted after testing.
