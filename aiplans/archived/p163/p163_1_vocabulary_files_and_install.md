---
Task: t163_1_vocabulary_files_and_install.md
Parent Task: aitasks/t163_review_modes_consolidate.md
Sibling Tasks: aitasks/t163/t163_2_*.md, aitasks/t163/t163_3_*.md, aitasks/t163/t163_4_*.md, aitasks/t163/t163_5_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Child task 1 of review guides consolidation (t163). Creates controlled vocabulary files for `reviewtype` and `reviewlabels` metadata fields that will be added to reviewguide files in subsequent sibling tasks. Follows the existing pattern of `seed/task_types.txt` → `aitasks/metadata/task_types.txt`.

## Plan

### 1. Create `seed/reviewtypes.txt`

New file with one value per line, sorted alphabetically:
```
bugs
code-smell
conventions
deprecations
performance
security
style
```

### 2. Create `seed/reviewlabels.txt`

New file with one value per line, sorted alphabetically (33 labels as specified in task).

### 3. Copy seed files to metadata

```bash
cp seed/reviewtypes.txt aitasks/metadata/reviewtypes.txt
cp seed/reviewlabels.txt aitasks/metadata/reviewlabels.txt
```

### 4. Update `install.sh`

Add two new functions after `install_seed_task_types()` (after line 227), following the exact same pattern:
- `install_seed_reviewtypes()` — copies `seed/reviewtypes.txt` → `aitasks/metadata/reviewtypes.txt`
- `install_seed_reviewlabels()` — copies `seed/reviewlabels.txt` → `aitasks/metadata/reviewlabels.txt`

Call them in the main install flow after `install_seed_task_types` (line 453), before `install_seed_reviewguides` (line 456):

```bash
info "Installing review types..."
install_seed_reviewtypes

info "Installing review labels..."
install_seed_reviewlabels
```

### Critical Files

- `seed/reviewtypes.txt` — **new**
- `seed/reviewlabels.txt` — **new**
- `aitasks/metadata/reviewtypes.txt` — **new** (copy from seed)
- `aitasks/metadata/reviewlabels.txt` — **new** (copy from seed)
- `install.sh:212-227` — pattern to replicate (`install_seed_task_types`)
- `install.sh:452-453` — where to add new install calls

## Verification

1. `diff seed/reviewtypes.txt aitasks/metadata/reviewtypes.txt` — should be identical
2. `diff seed/reviewlabels.txt aitasks/metadata/reviewlabels.txt` — should be identical
3. `shellcheck install.sh` — no new warnings

## Final Implementation Notes

- **Actual work done:** Created 4 vocabulary files (seed + metadata copies for reviewtypes and reviewlabels) and added 2 install functions + 2 calls in install.sh. Added `deprecations` to reviewtypes per user request (not in original task spec).
- **Deviations from plan:** Added `deprecations` review type (user requested during planning). Original task had 6 types, now 7.
- **Issues encountered:** None. All shellcheck warnings are pre-existing (lines 276, 444).
- **Key decisions:** Placed install functions between `install_seed_task_types` and `install_seed_reviewguides` for logical ordering. Install calls follow same order.
- **Notes for sibling tasks:** The vocabulary files are now at `aitasks/metadata/reviewtypes.txt` (7 values) and `aitasks/metadata/reviewlabels.txt` (34 values). Sibling t163_2 should use these to validate `reviewtype` and `reviewlabels` frontmatter fields when adding metadata to reviewguide files.
