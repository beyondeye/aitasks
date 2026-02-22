---
Task: t189_user_file_select_skill.md
Branch: main
Base branch: main
---

## Context

Task t189 creates a reusable file selection skill for other skills (aitask-explain, aitask-explore) to replace their current primitive free-text file selection. The skill supports three search modes: keyword content search, fuzzy name matching, and semantic functionality search. A bash helper script handles modes 1-2 for efficiency; mode 3 uses Claude's tools directly.

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `aiscripts/aitask_find_files.sh` | Create | Bash helper for keyword and name search |
| `.claude/skills/user-file-select/SKILL.md` | Create | Skill definition with step-based workflow |
| `.claude/settings.local.json` | Edit | Add whitelist entry for new script |
| `tests/test_find_files.sh` | Create | Automated tests for aitask_find_files.sh |

## Part 1: `aiscripts/aitask_find_files.sh`

**Structure** (follows `aitask_explain_extract_raw_data.sh` pattern):
- Header: `#!/usr/bin/env bash` + `set -euo pipefail`
- Source `lib/terminal_compat.sh` (not task_utils — no task resolution needed)
- Defaults: `MODE=""`, `SEARCH_TERMS=""`, `MAX_RESULTS=20`
- Argument parsing: while/case loop for `--keywords`, `--names`, `--max-results`, `--help`
- Output format: `<rank>|<match_count>|<file_path>` (pipe-delimited, one per line)

**Mode 1 — Keyword search (`search_keywords`)**:
1. Split terms string into array
2. For each term: `git ls-files -z | xargs -0 grep -ciI -- "$term" 2>/dev/null || true` — outputs `file:count` lines
3. Collect all output into temp file
4. Aggregate with awk: sum counts per file (handle filenames with colons by treating last field as count)
5. Sort descending, head -n max, add rank numbers
6. Clean up temp file

**Mode 2 — Name search (`search_names`)** — uses `fzf --filter` for fuzzy matching:
1. Split terms into array
2. For each term: `git ls-files | fzf --filter="$term" 2>/dev/null` — outputs matched files ranked by fzf's fuzzy score (best first)
3. Assign position-based scores: first result gets N points, second N-1, etc. (N = max_results)
4. Accumulate scores per file across all terms (files matching more terms rank higher)
5. Sort by accumulated score descending, head -n max, add rank numbers
6. Output as `<rank>|<score>|<file_path>`

**Why fzf**: Native fuzzy matching (e.g., "tsk_utl" matches "task_utils.sh"), smart path-aware ranking, much better UX than simple substring matching. Requires fzf installed (die if missing).

**Edge cases**: empty terms → die; no git repo → die; no matches → exit 0 with no output; binary files → skipped by `grep -I`

## Part 2: `.claude/skills/user-file-select/SKILL.md`

**Frontmatter**: name, description

**Steps**:

1. **Arguments** — Parse optional `--keywords`, `--names`, `--describe` to skip mode selection
2. **Mode Selection** — `AskUserQuestion` with 3 options: keywords / names / functionality
3. **Search Execution**:
   - 3a (keywords): prompt for terms if not in args → run `./aiscripts/aitask_find_files.sh --keywords "..."` → parse output
   - 3b (names): prompt for terms if not in args → run `./aiscripts/aitask_find_files.sh --names "..."` → parse output
   - 3c (functionality): prompt for description if not in args → Claude uses Glob/Grep/Read to find files → build ranked list with relevance descriptions
   - All modes: if no results → offer retry/switch mode/cancel
4. **Present Results** — Numbered list with score (modes 1-2) or relevance description (mode 3)
5. **User Selection** — Free-text `AskUserQuestion` for index-based input: `1,4,5` / `3-5` / `1,3-5,7` / `all`. Parse, validate bounds, re-prompt on error.
6. **Output & Refinement** — Display selected files, `AskUserQuestion`: confirm / search for more (merge with existing) / start over. Final output: newline-separated file paths.

## Part 3: Settings Update

Add `"Bash(./aiscripts/aitask_find_files.sh:*)"` to `.claude/settings.local.json` allow list.

## Part 4: `tests/test_find_files.sh`

15 test cases covering syntax, error handling, keyword search, name search (including fuzzy), output format, and edge cases.

## Implementation Sequence

- [x] Save plan
- [x] Create `aiscripts/aitask_find_files.sh`, `chmod +x`
- [x] Run `shellcheck aiscripts/aitask_find_files.sh` — clean (only SC1091 info)
- [x] Create `tests/test_find_files.sh`
- [x] Run `bash tests/test_find_files.sh` — 32/32 PASS
- [x] Create `.claude/skills/user-file-select/SKILL.md`
- [x] `.claude/settings.local.json` — whitelist entry already present

## Verification

1. `shellcheck aiscripts/aitask_find_files.sh` — clean pass
2. `bash tests/test_find_files.sh` — all tests pass
3. Manual smoke tests against the real repo

## Final Implementation Notes

- **Actual work done:** Created all 4 planned files: bash helper script with keyword search (grep-based) and name search (fzf --filter-based), SKILL.md with 5-step workflow (mode selection → search → present → select → confirm), test suite with 15 test cases (32 assertions), and implementation plan. The settings.local.json whitelist entry was already present.
- **Deviations from plan:** None significant. The original plan proposed awk-based substring matching for name search; user requested fzf integration which was adopted. Position-based scoring is used to combine fzf results across multiple search terms.
- **Issues encountered:** None. All tests pass on first run, shellcheck clean.
- **Key decisions:** (1) Source only terminal_compat.sh (not task_utils.sh) since no task resolution is needed. (2) Use temp files for score aggregation to avoid complex pipe chains. (3) fzf position-based scoring: first match gets N points, second N-1, etc., accumulated across terms so files matching more terms rank higher.
