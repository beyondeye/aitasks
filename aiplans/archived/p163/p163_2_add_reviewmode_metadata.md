---
Task: t163_2_add_reviewguide_metadata.md
Parent Task: aitasks/t163_review_modes_consolidate.md
Sibling Tasks: aitasks/t163/t163_3_*.md, aitasks/t163/t163_4_*.md, aitasks/t163/t163_5_*.md
Archived Sibling Plans: aiplans/archived/p163/p163_1_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Child task 2 of t163 (Review Guides Consolidation). After t163_1 created vocabulary files (`reviewtypes.txt` and `reviewlabels.txt`), this task adds `reviewtype` and `reviewlabels` frontmatter fields to all 9 existing reviewguide files, mirrors changes to seed, and updates the aitask-review skill documentation.

## Plan

### 1. Add frontmatter to 9 production reviewguide files

Add `reviewtype` and `reviewlabels` fields after existing frontmatter fields (after `description` for general files, after `environment` for environment-specific files). Do NOT modify the markdown body.

| File | reviewtype | reviewlabels |
|------|------------|--------------|
| `aireviewguides/general/code_conventions.md` | `style` | `[naming, formatting, organization, comments]` |
| `aireviewguides/general/code_duplication.md` | `code-smell` | `[dry, extraction, deduplication]` |
| `aireviewguides/general/error_handling.md` | `bugs` | `[errors, exceptions, edge-cases, resource-cleanup]` |
| `aireviewguides/general/performance.md` | `performance` | `[memory, caching, database, algorithmic-complexity]` |
| `aireviewguides/general/refactoring.md` | `code-smell` | `[complexity, coupling, code-smells]` |
| `aireviewguides/general/security.md` | `security` | `[injection, secrets, authentication, cryptography, input-validation]` |
| `aireviewguides/python/python_best_practices.md` | `conventions` | `[type-hints, idioms, context-managers, pythonic]` |
| `aireviewguides/android/android_best_practices.md` | `conventions` | `[lifecycle, coroutines, compose, memory]` |
| `aireviewguides/shell/shell_scripting.md` | `conventions` | `[quoting, portability, shellcheck, error-handling]` |

### 2. Mirror to seed directory

Copy each updated file from `aireviewguides/` to `seed/reviewguides/`.

### 3. Update aitask-review SKILL.md

Update line 297 frontmatter format documentation to include new fields.

### Critical Files

- 9 production files in `aireviewguides/{general,python,android,shell}/`
- 9 seed files in `seed/reviewguides/{general,python,android,shell}/`
- `.claude/skills/aitask-review/SKILL.md:297`

## Final Implementation Notes

- **Actual work done:** Added `reviewtype` and `reviewlabels` frontmatter fields to all 9 production reviewguide files, copied all 9 to seed directory, and updated SKILL.md line 297 to document the new fields. Exactly matches the original plan.
- **Deviations from plan:** None. All assignments matched the task specification exactly.
- **Issues encountered:** None. All verifications passed on first attempt.
- **Key decisions:** Placed new fields after `description` (for general modes) and after `environment` (for environment-specific modes) to maintain logical field ordering.
- **Notes for sibling tasks:** The 9 reviewguide files now have `reviewtype` and `reviewlabels` metadata. Sibling t163_3 (reviewguide scan script) can parse these fields to classify and compare modes. The `aitask_review_detect_env.sh` script safely ignores the new fields (verified). The SKILL.md documentation now also mentions `similar_to` (optional string) in the frontmatter format — this field is not yet used by any file but is ready for t163_4/t163_5 to populate.
