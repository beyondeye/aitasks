---
Task: t172_3_update_bash_scripts.md
Parent Task: aitasks/t172_rename_reviewmode_to_reviewguide.md
Sibling Tasks: aitasks/t172/t172_4_*.md, aitasks/t172/t172_5_*.md
Archived Sibling Plans: aiplans/archived/p172/p172_1_*.md, aiplans/archived/p172/p172_2_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Child task 3 of t172 (rename reviewmode to reviewguide). t172_1 physically moved/renamed all directories and files. t172_2 updated install.sh and aitask_setup.sh. This task updates the two bash scripts that scan/analyze reviewguide files, plus test files.

## Plan

### 1. Update `aiscripts/aitask_reviewguide_scan.sh`

All changes are text replacements — no logic changes.

**Header comments (lines 2-6):**
- `aitask_reviewmode_scan.sh` → `aitask_reviewguide_scan.sh`
- `reviewmode files` → `reviewguide files`
- `aitask_reviewmode_scan.sh [OPTIONS]` → `aitask_reviewguide_scan.sh [OPTIONS]`

**Flag/option renames:**
- `--reviewmodes-dir` → `--reviewguides-dir` (lines 12, 50-52, 64, 71)

**Variable renames (replace_all):**
- `REVIEWMODES_DIR` → `REVIEWGUIDES_DIR` (lines 34, 83, 97, 100, 104, 110, 165, and more)

**Function rename:**
- `parse_reviewmode()` → `parse_reviewguide()` (line 139 definition, line 175 call)

**Default path:**
- `aitasks/metadata/reviewmodes` → `aireviewguides` (line 34)

**Ignore file:**
- `.reviewmodesignore` → `.reviewguidesignore` (line 100)

**Help text (lines 64-74):**
- Update script name, description, flag names

**Warning/error messages:**
- `Reviewmodes directory not found` → `Reviewguides directory not found` (line 83)
- `No reviewmode files found` → `No reviewguide files found` (line 129)

**Comments:**
- `reviewmode` → `reviewguide` everywhere in comments

### 2. Update `aiscripts/aitask_review_detect_env.sh`

**Header comments (lines 2-7):**
- `review modes` → `review guides`
- `--reviewmodes-dir` → `--reviewguides-dir`

**Output section headers:**
- `REVIEW_MODES` → `REVIEW_GUIDES` (lines 18, 289)
- Note for t172_4: The aitask-review SKILL.md parses `REVIEW_MODES` and must be updated to parse `REVIEW_GUIDES`

**Flag/option renames:**
- `--reviewmodes-dir` → `--reviewguides-dir` (lines 7, 11, 49-51, 57, 61)

**Variable renames (replace_all):**
- `REVIEWMODES_DIR` → `REVIEWGUIDES_DIR` (lines 31, 50, 261, 295, 299, 303, 309, 320)

**Default path:**
- `aitasks/metadata/reviewmodes` → `aireviewguides` (line 31)

**Function rename:**
- `parse_reviewmode()` → `parse_reviewguide()` (line 237 definition, line 332 call)

**Ignore file:**
- `.reviewmodesignore` → `.reviewguidesignore` (lines 297, 299)

**Comments:**
- `review mode` → `review guide` everywhere in comments (lines 232-234, 291, 327, etc.)

### 3. Update `tests/test_setup_git.sh`

**Test 10 (lines 294-310) — "late-stage files" test:**
- Line 294 comment: `review modes` → `review guides`
- Line 295: `mkdir -p "$TMPDIR_10/aitasks/metadata/reviewmodes"` → `mkdir -p "$TMPDIR_10/aireviewguides"`
- Line 296: path → `"$TMPDIR_10/aireviewguides/test_mode.md"`
- Line 296: `"# review mode"` → `"# review guide"`
- Line 303 comment: `Review modes` → `Review guides`
- Line 304: `"reviewmodes/test_mode.md"` → `"aireviewguides/test_mode.md"`

### 4. Update `tests/test_t167_integration.sh`

**Scenario B (lines 122-148) — "late-stage files" test:**
- Line 133: `mkdir -p "$TEST_DIR/aitasks/metadata/reviewmodes"` → `mkdir -p "$TEST_DIR/aireviewguides"`
- Line 134: path → `"$TEST_DIR/aireviewguides/test_mode.md"`
- Line 134: `"# test review mode"` → `"# test review guide"`
- Line 133 comment: `review modes installation` → `review guides installation`
- Line 146: `"reviewmodes/test_mode.md"` → `"aireviewguides/test_mode.md"`
- Line 146 description: `Review mode file` → `Review guide file`

## Verification

1. `shellcheck aiscripts/aitask_reviewguide_scan.sh` — no new warnings
2. `shellcheck aiscripts/aitask_review_detect_env.sh` — no new warnings
3. `grep -ri "reviewmode" aiscripts/aitask_reviewguide_scan.sh` — 0 results
4. `grep -ri "reviewmode" aiscripts/aitask_review_detect_env.sh` — 0 results
5. `grep -ri "reviewmode" tests/` — 0 results
6. `./aiscripts/aitask_reviewguide_scan.sh` — should list all reviewguide files from `aireviewguides/`
7. `./aiscripts/aitask_reviewguide_scan.sh --find-similar` — should work correctly
8. `./aiscripts/aitask_review_detect_env.sh` — should output `REVIEW_GUIDES` section header and list guides from `aireviewguides/`
9. `bash tests/test_setup_git.sh` — all tests pass
10. `bash tests/test_t167_integration.sh` — all tests pass

## Final Implementation Notes

- **Actual work done:** All planned changes executed across 4 files (aitask_reviewguide_scan.sh, aitask_review_detect_env.sh, test_setup_git.sh, test_t167_integration.sh). Additionally fixed a bug missed by t172_2: added `aireviewguides/` to `check_paths` in both `aitask_setup.sh` and `install.sh` `commit_framework_files` functions — previously review modes were caught by the `aitasks/metadata/` path, but the new `aireviewguides/` location at project root requires its own entry.
- **Deviations from plan:** Two extra files modified (aitask_setup.sh, install.sh) to fix the `check_paths` bug discovered during test execution.
- **Issues encountered:** Test 10 in test_setup_git.sh initially failed because `commit_framework_files()` didn't include `aireviewguides/` in its `check_paths` list — the old `aitasks/metadata/reviewmodes/` was implicitly covered by the `aitasks/metadata/` entry but the new root-level `aireviewguides/` is not.
- **Key decisions:** Renamed `REVIEW_MODES` output section header to `REVIEW_GUIDES` in detect_env.sh.
- **Notes for sibling tasks:**
  - t172_4 MUST update the aitask-review SKILL.md to parse `REVIEW_GUIDES` instead of `REVIEW_MODES` from detect_env.sh output
  - t172_4 MUST update the `--reviewmodes-dir` flag references to `--reviewguides-dir` in SKILL.md
  - t172_4 should update the default path from `aitasks/metadata/reviewmodes` to `aireviewguides` in SKILL.md
  - The `check_paths` fix in aitask_setup.sh and install.sh ensures `aireviewguides/` files are included in framework commits

## Post-Implementation

Step 9 from task-workflow: archive task and plan via `aitask_archive.sh 172_3`.
