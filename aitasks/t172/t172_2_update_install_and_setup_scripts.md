---
priority: high
effort: medium
depends: [t172_1]
issue_type: refactor
status: Ready
labels: [aitask_review]
created_at: 2026-02-18 22:02
updated_at: 2026-02-18 22:02
---

## Context

Child task 2 of t172 (rename reviewmode to reviewguide). Updates the installation infrastructure to use the new directory names and paths. Depends on t172_1 (directory moves) being complete.

## Key Files to Modify

### 1. `install.sh` (~22 references)

**Function renames:**
- `install_seed_reviewmodes()` → `install_seed_reviewguides()`
- Function calls updated to match

**Path changes (critical — destination changes):**
- `seed/reviewmodes/` → `seed/reviewguides/`
- `aitasks/metadata/reviewmodes/` → `aireviewguides/` (this is the big structural change — installed reviewguides now go to project root)
- `.reviewmodesignore` → `.reviewguidesignore`

**Info messages:**
- "Installing review modes..." → "Installing review guides..."
- Any other user-facing strings with "reviewmode"

**Note:** The vocabulary file install functions (`install_seed_reviewtypes`, `install_seed_reviewlabels`, `install_seed_reviewenvironments`) also reference the destination path `aitasks/metadata/reviewmodes/` — these must change to `aireviewguides/`.

### 2. `aiscripts/aitask_setup.sh`

- Update any references to `aitasks/metadata/reviewmodes/` → `aireviewguides/`
- Update any references to `seed/reviewmodes/` → `seed/reviewguides/`
- Update function calls if it invokes install.sh functions

## Reference Files

- `install.sh` — main file to modify (read current content first)
- `aiscripts/aitask_setup.sh` — may have references

## Verification

1. `shellcheck install.sh` — no new warnings
2. `shellcheck aiscripts/aitask_setup.sh` — no new warnings
3. `grep -r "reviewmode" install.sh` — should return 0 results
4. `grep -r "reviewmode" aiscripts/aitask_setup.sh` — should return 0 results
5. `grep -r "aitasks/metadata/reviewmodes" install.sh` — should return 0 results (old path gone)
6. `grep "aireviewguides" install.sh` — should show the new destination paths
