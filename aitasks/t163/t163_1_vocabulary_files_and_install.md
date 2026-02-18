---
priority: medium
effort: low
depends: []
issue_type: feature
status: Ready
labels: [aitask_review, claudeskills]
created_at: 2026-02-18 15:10
updated_at: 2026-02-18 15:10
---

## Context

This is child task 1 of the review modes consolidation (t163). Review mode files in `aitasks/metadata/reviewmodes/` need richer metadata. Before adding metadata to files, we need controlled vocabulary files that define the allowed values for new frontmatter fields `reviewtype` and `reviewlabels`.

This follows the existing pattern of `seed/task_types.txt` → `aitasks/metadata/task_types.txt`.

## Key Files to Modify

- `seed/reviewtypes.txt` — **new file**, controlled vocabulary for review types
- `seed/reviewlabels.txt` — **new file**, controlled vocabulary for review labels
- `aitasks/metadata/reviewtypes.txt` — **new file**, copy from seed
- `aitasks/metadata/reviewlabels.txt` — **new file**, copy from seed
- `install.sh` — add `install_seed_reviewtypes()` and `install_seed_reviewlabels()` functions

## Reference Files for Patterns

- `seed/task_types.txt` — existing vocabulary file pattern to follow
- `install.sh` lines 212-227 — `install_seed_task_types()` function to replicate
- `install.sh` line 453 — where `install_seed_task_types` is called in the main flow

## Implementation Plan

### 1. Create `seed/reviewtypes.txt`

```
bugs
code-smell
conventions
performance
security
style
```

One value per line, sorted alphabetically. These categorize what kind of checks a review mode performs.

### 2. Create `seed/reviewlabels.txt`

```
algorithmic-complexity
authentication
caching
code-smells
comments
compose
complexity
context-managers
coroutines
coupling
cryptography
database
deduplication
dry
edge-cases
error-handling
errors
exceptions
extraction
formatting
idioms
injection
input-validation
lifecycle
memory
naming
organization
portability
pythonic
quoting
resource-cleanup
secrets
shellcheck
type-hints
```

One value per line, sorted alphabetically. These are sub-categorization tags for reviewmode files.

### 3. Copy seed files to metadata

```bash
cp seed/reviewtypes.txt aitasks/metadata/reviewtypes.txt
cp seed/reviewlabels.txt aitasks/metadata/reviewlabels.txt
```

### 4. Update `install.sh`

Add two new functions after `install_seed_task_types()` (line 227), following the exact same pattern:

```bash
# --- Install seed review types ---
install_seed_reviewtypes() {
    local src="$INSTALL_DIR/seed/reviewtypes.txt"
    local dest="$INSTALL_DIR/aitasks/metadata/reviewtypes.txt"

    if [[ ! -f "$src" ]]; then
        warn "No seed/reviewtypes.txt in tarball — skipping review types installation"
        return
    fi

    if [[ -f "$dest" && "$FORCE" != true ]]; then
        info "  Review types file exists (kept): reviewtypes.txt"
    else
        cp "$src" "$dest"
        info "  Installed review types: reviewtypes.txt"
    fi
}

# --- Install seed review labels ---
install_seed_reviewlabels() {
    local src="$INSTALL_DIR/seed/reviewlabels.txt"
    local dest="$INSTALL_DIR/aitasks/metadata/reviewlabels.txt"

    if [[ ! -f "$src" ]]; then
        warn "No seed/reviewlabels.txt in tarball — skipping review labels installation"
        return
    fi

    if [[ -f "$dest" && "$FORCE" != true ]]; then
        info "  Review labels file exists (kept): reviewlabels.txt"
    else
        cp "$src" "$dest"
        info "  Installed review labels: reviewlabels.txt"
    fi
}
```

Call them in the main install flow after `install_seed_task_types` (around line 453):

```bash
info "Installing review types..."
install_seed_reviewtypes

info "Installing review labels..."
install_seed_reviewlabels
```

## Verification Steps

1. Verify files exist and match:
   ```bash
   diff seed/reviewtypes.txt aitasks/metadata/reviewtypes.txt
   diff seed/reviewlabels.txt aitasks/metadata/reviewlabels.txt
   ```
2. Run shellcheck on install.sh: `shellcheck install.sh`
3. Verify install.sh can be sourced without errors (dry-run check)
