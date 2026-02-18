---
priority: medium
effort: low
depends: [t163_1]
issue_type: feature
status: Done
labels: [aitask_review, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-18 15:10
updated_at: 2026-02-18 15:49
completed_at: 2026-02-18 15:49
---

## Context

This is child task 2 of the review guides consolidation (t163). After vocabulary files are created (t163_1), we need to add `reviewtype` and `reviewlabels` frontmatter fields to all 9 existing reviewguide files, and update the aitask-review skill documentation.

## Dependencies

- Depends on t163_1 (vocabulary files must exist first)

## Key Files to Modify

**Reviewguide files (18 total — 9 production + 9 seed mirrors):**
- `aireviewguides/general/code_conventions.md`
- `aireviewguides/general/code_duplication.md`
- `aireviewguides/general/error_handling.md`
- `aireviewguides/general/performance.md`
- `aireviewguides/general/refactoring.md`
- `aireviewguides/general/security.md`
- `aireviewguides/python/python_best_practices.md`
- `aireviewguides/android/android_best_practices.md`
- `aireviewguides/shell/shell_scripting.md`
- Same 9 files in `seed/reviewguides/` (must mirror exactly)

**Documentation:**
- `.claude/skills/aitask-review/SKILL.md` — update Notes section line 297

## Reference Files for Patterns

- `aitasks/metadata/reviewtypes.txt` — allowed values for `reviewtype`
- `aitasks/metadata/reviewlabels.txt` — allowed values for `reviewlabels`
- Current reviewguide files already have frontmatter with `name`, `description`, optional `environment`

## Implementation Plan

### 1. Add frontmatter to all 9 reviewguide files

For each file, add `reviewtype` and `reviewlabels` fields to the existing YAML frontmatter. Do NOT modify the markdown body.

**Exact assignments:**

| File | reviewtype | reviewlabels |
|------|------------|--------------|
| `general/code_conventions.md` | `style` | `[naming, formatting, organization, comments]` |
| `general/code_duplication.md` | `code-smell` | `[dry, extraction, deduplication]` |
| `general/error_handling.md` | `bugs` | `[errors, exceptions, edge-cases, resource-cleanup]` |
| `general/performance.md` | `performance` | `[memory, caching, database, algorithmic-complexity]` |
| `general/refactoring.md` | `code-smell` | `[complexity, coupling, code-smells]` |
| `general/security.md` | `security` | `[injection, secrets, authentication, cryptography, input-validation]` |
| `python/python_best_practices.md` | `conventions` | `[type-hints, idioms, context-managers, pythonic]` |
| `android/android_best_practices.md` | `conventions` | `[lifecycle, coroutines, compose, memory]` |
| `shell/shell_scripting.md` | `conventions` | `[quoting, portability, shellcheck, error-handling]` |

**Example frontmatter (code_conventions.md):**
```yaml
---
name: Code Conventions
description: Check naming, formatting, and pattern consistency
reviewtype: style
reviewlabels: [naming, formatting, organization, comments]
---
```

**Example frontmatter with environment (python_best_practices.md):**
```yaml
---
name: Python Best Practices
description: Check type hints, modern idioms, context managers, and pythonic patterns
environment: [python]
reviewtype: conventions
reviewlabels: [type-hints, idioms, context-managers, pythonic]
---
```

### 2. Mirror changes to seed directory

Copy each updated file from `aireviewguides/` to `seed/reviewguides/` at the matching path.

### 3. Update aitask-review documentation

In `.claude/skills/aitask-review/SKILL.md`, update the Notes section (line 297) from:
```
- The frontmatter format is: `name` (string), `description` (string), `environment` (optional list)
```
to:
```
- The frontmatter format is: `name` (string), `description` (string), `environment` (optional list), `reviewtype` (optional string), `reviewlabels` (optional list), `similar_to` (optional string)
```

## Verification Steps

1. Confirm `aitask_review_detect_env.sh` still works (new fields are safely ignored by its parser):
   ```bash
   echo "aiscripts/aitask_ls.sh" | ./aiscripts/aitask_review_detect_env.sh --files-stdin --reviewguides-dir aitasks/metadata/reviewguides
   ```
2. Verify seed mirrors production:
   ```bash
   diff -r aireviewguides/ seed/reviewguides/
   ```
3. Verify all reviewtype values exist in `aitasks/metadata/reviewtypes.txt`
4. Verify all reviewlabel values exist in `aitasks/metadata/reviewlabels.txt`
