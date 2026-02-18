---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Done
labels: [aitask_review, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-17 18:03
updated_at: 2026-02-17 19:00
completed_at: 2026-02-17 19:00
---

Reorganize the reviewguides storage from a flat directory to a directory tree structure, and add a gitignore-like filter file for enabling/disabling review guides.

## Current State
- Review guides stored flat in `aireviewguides/*.md`
- 9 review guide files, all in one directory
- No way to disable/enable modes without deleting files

## Changes Required

### 1. Directory Tree Structure
Move from flat `aireviewguides/*.md` to a tree structure that allows organizing modes by category/environment (e.g., `aireviewguides/security/`, `aireviewguides/python/`, etc.). The exact structure should be determined during planning.

### 2. Filter File (`.reviewguidesignore` or similar)
Add a filter file in the top-level reviewguides directory that uses gitignore-like syntax to disable specific review guides or entire directories of modes. Example:
```
# Disable all Android-specific modes
android/

# Disable a specific mode
security/owasp_advanced.md
```

### 3. Implementation Note: gitignore Pattern Matching in Bash
Use `git check-ignore --no-index --stdin` with the filter file to get full gitignore pattern matching for free, since git is always available. This avoids reimplementing glob/pattern logic in bash.

### 4. Update Affected Files
- `aitask_review_detect_env.sh` (from t158) — needs to scan subdirectories and apply filter
- `.claude/skills/aitask-review/SKILL.md` — update reviewguides listing to handle tree structure
- `aiscripts/aitask_install.sh` / seed files — update how reviewguides are installed
- Any other scripts that reference `aireviewguides/*.md`

### 5. Seed Reviewguides
Update how seed review guides are organized and installed to match the new tree structure.
