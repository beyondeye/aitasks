---
Task: t159_reviewmodes_directory_tree.md
Worktree: (working on main)
Branch: main
Base branch: main
---

# Plan: Reviewmodes Directory Tree Structure + Filter File (t159)

## Context

The 9 reviewmode files are stored flat in `aitasks/metadata/reviewmodes/*.md`. As the number of modes grows, a flat structure becomes harder to navigate. This refactor reorganizes them into a categorized directory tree and adds a `.reviewmodesignore` filter file using gitignore syntax (powered by `git check-ignore --no-index`).

## Directory Structure

**Seed and installed layouts (identical):**
```
reviewmodes/
├── .reviewmodesignore          # Optional filter file (gitignore syntax)
├── general/                    # Universal modes (no environment field)
│   ├── code_conventions.md
│   ├── code_duplication.md
│   ├── error_handling.md
│   ├── performance.md
│   ├── refactoring.md
│   └── security.md
├── python/
│   └── python_best_practices.md
├── android/
│   └── android_best_practices.md
└── shell/
    └── shell_scripting.md
```

## Implementation Steps

### Step 1: Reorganize seed files (`seed/reviewmodes/`) ✅
### Step 2: Reorganize installed files (`aitasks/metadata/reviewmodes/`) ✅
### Step 3: Update `aiscripts/aitask_review_detect_env.sh` ✅
### Step 4: Update `install.sh` — `install_seed_reviewmodes()` ✅
### Step 5: Update `aiscripts/aitask_setup.sh` — `setup_review_modes()` ✅
### Step 6: Update `.claude/skills/aitask-review/SKILL.md` ✅

## Final Implementation Notes

- **Actual work done:** All 6 steps implemented as planned. Reorganized 9 reviewmode files from flat to tree structure (general/, python/, android/, shell/), added .reviewmodesignore filter file, updated all 4 scripts and SKILL.md documentation.
- **Deviations from plan:** Fixed a pre-existing bug where `printf '%s\n'` on empty arrays produced ghost entries in output. Added `[[ ${#array[@]} -gt 0 ]]` guards before printf in the output section.
- **Issues encountered:** `git check-ignore --no-index` works correctly with `core.excludesFile` for filtering. Directory-level patterns (e.g., `general/`) correctly match all files in that subdirectory.
- **Key decisions:** Output field name changed from `<filename>` to `<relative_path>` throughout all documentation and variable names. The filter uses an associative array for O(1) lookup of ignored paths.
