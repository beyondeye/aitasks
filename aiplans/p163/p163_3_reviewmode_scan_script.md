---
Task: t163_3_reviewmode_scan_script.md
Parent Task: aitasks/t163_review_modes_consolidate.md
Sibling Tasks: aitasks/t163/t163_4_classify_skill.md, aitasks/t163/t163_5_merge_skill.md
Archived Sibling Plans: aiplans/archived/p163/p163_1_vocabulary_files_and_install.md, aiplans/archived/p163/p163_2_add_reviewmode_metadata.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

The review modes consolidation (t163) needs a bash helper script to scan reviewmode files for metadata completeness and find similar files. This script is a prerequisite for the classify skill (t163_4) and merge skill (t163_5). Siblings t163_1 (vocabulary files) and t163_2 (metadata on all files) are complete — all 9 reviewmode files now have `reviewtype` and `reviewlabels` fields.

## Plan: Create `aiscripts/aitask_reviewmode_scan.sh`

### File Created

- `aiscripts/aitask_reviewmode_scan.sh` — new bash script (383 lines)

### Script Structure

```
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR + source lib/terminal_compat.sh
--- Defaults ---
--- Argument parsing (while/case) ---
--- File discovery + .reviewmodesignore filter ---
--- parse_reviewmode() function ---
--- Parse all files into array ---
--- Environment filter ---
--- Label set helpers (split_csv, compute_label_overlap, check_env_overlap) ---
--- Mode-specific output (case: default | missing-meta | find-similar | compare) ---
```

### Implementation Details

1. **Argument parsing** — Follows `aitask_review_detect_env.sh` while/case pattern
2. **File discovery** — Reuses exact `.reviewmodesignore` filter pattern from `aitask_review_detect_env.sh` lines 297-325
3. **parse_reviewmode()** — Extended version parsing `name`, `environment`, `reviewtype`, `reviewlabels`
4. **Environment filter** — `--environment general` shows universal only; `--environment bash` shows only bash-matching files
5. **Label helpers** — `compute_label_overlap()` uses associative arrays for O(1) intersection; `check_env_overlap()` checks environment overlap
6. **Scoring** — `score = (shared_labels * 2) + (type_match ? 3 : 0) + (env_overlap ? 2 : 0)`

### Verification Results

All 6 tests passed:
- [x] Default: lists all 9 files with metadata
- [x] `--missing-meta`: empty (all files have metadata from t163_2)
- [x] `--environment bash`: only `shell/shell_scripting.md`
- [x] `--find-similar`: shows similarity pairs (performance↔android share "memory" label)
- [x] `--compare general/security.md`: shows matches scored by overlap
- [x] `shellcheck`: only SC1091 info (can't follow source — same as reference script)

## Final Implementation Notes

- **Actual work done:** Created `aiscripts/aitask_reviewmode_scan.sh` (383 lines) exactly as specified in the task description. All 4 modes implemented: default listing, `--missing-meta`, `--find-similar`, and `--compare FILE`.
- **Deviations from plan:** Initial implementation showed universal modes when using `--environment bash`; fixed to strict filtering per task spec (only files with matching environment field, not universal). Also fixed bash ternary expression `(x == "y" ? 3 : 0)` which doesn't work in `$((...))` — replaced with `[[ ]] && $(( ))`.
- **Issues encountered:** shellcheck SC2295 (unquoted expansions in `${..}`) and SC2034 (unused variables in IFS read) — both fixed by quoting and prefixing unused vars with `_`.
- **Key decisions:** Environment filter is strict: `--environment bash` only shows bash-matching files (not universal). `--environment general` shows only universal modes. `check_env_overlap` considers both-universal as overlap, but one-universal-one-specific as no overlap (different scope).
- **Notes for sibling tasks:** The script's `--compare FILE` mode is designed to be called by the classify skill (t163_4) in Step 4 to find the most similar existing file. The `--find-similar` mode is designed for the merge skill (t163_5) batch mode to find merge candidates. The `--missing-meta` mode is for classify skill batch mode. Output is pipe-delimited for easy parsing in skill workflows.
