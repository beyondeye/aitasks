---
priority: high
effort: medium
depends: [t172_1]
issue_type: refactor
status: Implementing
labels: [aitask_review]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-18 22:03
updated_at: 2026-02-18 23:00
---

## Context

Child task 3 of t172 (rename reviewmode to reviewguide). Updates the bash scripts that scan, analyze, and detect reviewmode files. Depends on t172_1 (directory moves) being complete.

## Key Files to Modify

### 1. `aiscripts/aitask_reviewguide_scan.sh` (renamed from aitask_reviewmode_scan.sh in t172_1)

This is the main scan/analysis script (~383 lines). All internal references need updating:

**Path references:**
- `aitasks/metadata/reviewmodes/` → `aireviewguides/`
- `.reviewmodesignore` → `.reviewguidesignore`

**Variable/function names containing "reviewmode":**
- `parse_reviewmode()` → `parse_reviewguide()`
- Any variables like `reviewmode_*` → `reviewguide_*`

**Comments and usage text:**
- Help text, comments, and usage strings mentioning "reviewmode" → "reviewguide"

**Header comments:**
- Script description mentioning "review mode" files → "review guide" files

### 2. `aiscripts/aitask_review_detect_env.sh`

This script detects the project environment and ranks review modes. Updates needed:

**Path references:**
- `aitasks/metadata/reviewmodes/` → `aireviewguides/`
- `.reviewmodesignore` → `.reviewguidesignore`

**Output format:**
- If the script outputs section headers like "REVIEW_MODES" → consider renaming to "REVIEW_GUIDES"
- Check if other scripts/skills parse this output and would break

**Comments and strings:**
- Any "reviewmode" mentions → "reviewguide"

### 3. Test files

- `tests/test_setup_git.sh` — update reviewmode references
- `tests/test_t167_integration.sh` — update reviewmode references

## Reference Files

- Read each script fully before modifying to understand all references
- Check the aitask-review SKILL.md to understand how scripts' output is parsed (avoid breaking the interface)

## Verification

1. `shellcheck aiscripts/aitask_reviewguide_scan.sh` — no new warnings
2. `shellcheck aiscripts/aitask_review_detect_env.sh` — no new warnings
3. `grep -ri "reviewmode" aiscripts/aitask_reviewguide_scan.sh` — should return 0 results
4. `grep -ri "reviewmode" aiscripts/aitask_review_detect_env.sh` — should return 0 results
5. `grep -ri "reviewmode" tests/` — should return 0 results
6. Run `./aiscripts/aitask_reviewguide_scan.sh` (default mode) — should list all reviewguide files from `aireviewguides/`
7. Run `./aiscripts/aitask_reviewguide_scan.sh --find-similar` — should work correctly
8. Run `./aiscripts/aitask_review_detect_env.sh` — should detect environment and list guides from `aireviewguides/`
