---
Task: t258_1_create_aitask_explain_cleanup_script.md
Parent Task: aitasks/t258_automatic_clean_up_of_aiexplains_for_code_browser.md
Sibling Tasks: aitasks/t258/t258_2_*.md, aitasks/t258/t258_3_*.md, aitasks/t258/t258_4_*.md, aitasks/t258/t258_5_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

## Plan: Create `aitask_explain_cleanup.sh`

### Step 1: Create the cleanup script

Create `aiscripts/aitask_explain_cleanup.sh` following conventions from `aiscripts/aitask_explain_runs.sh`.

**Structure:**
```
#!/usr/bin/env bash
set -euo pipefail
source terminal_compat.sh

Variables: TARGET_DIR, MODE (target|all), DRY_RUN, QUIET

Functions:
- extract_key_and_timestamp(name) → "key|timestamp" or return 1
- cleanup_directory(target_dir) → groups by key, deletes stale, returns count
- Main modes: --target, --all, --dry-run, --quiet
```

**Key algorithm — `cleanup_directory()`:**
1. Iterate subdirs in target_dir
2. For each, call `extract_key_and_timestamp`:
   - Regex `^(.+)__([0-9]{8}_[0-9]{6})$` → key=group1, ts=group2
   - Bare timestamp (15 chars, digit_digit) → key=`_bare_timestamp_`, ts=name
3. Use `declare -A` associative arrays to track newest per key
4. Safety: validate with `realpath` under `aiexplains/`, check `files.txt` or `raw_data.txt` exists
5. Delete stale dirs with `rm -rf`
6. Output `CLEANED: N`

**When `--all`:** Run cleanup on both `aiexplains/` (only non-`codebrowser` dirs) and `aiexplains/codebrowser/`.

### Step 2: Add to `ait` dispatcher

In `ait` file, add near the `explain-runs` line (~129):
```bash
explain-cleanup) shift; exec "$SCRIPTS_DIR/aitask_explain_cleanup.sh" "$@" ;;
```
And add to `show_usage()` under Tools.

### Step 3: Add to settings whitelists

Add `"Bash(./aiscripts/aitask_explain_cleanup.sh:*)"` to:
- `seed/claude_settings.local.json` (line ~32, near other explain entries)
- `.claude/settings.local.json` (near other explain entries)

### Step 4: Run shellcheck and test

1. `shellcheck aiscripts/aitask_explain_cleanup.sh`
2. `./aiscripts/aitask_explain_cleanup.sh --dry-run --all`
3. `./aiscripts/aitask_explain_cleanup.sh --all`

### Step 9: Post-Implementation

Archive task following the standard workflow.

## Final Implementation Notes

- **Actual work done:** Created `aiscripts/aitask_explain_cleanup.sh` with all planned features (--target, --all, --dry-run, --quiet modes). Added `explain-cleanup` command to `ait` dispatcher and usage help. Added whitelist entries to both `seed/claude_settings.local.json` and `.claude/settings.local.json`.
- **Deviations from plan:** The `cleanup_directory()` function uses a global `_cleanup_result` variable instead of echoing the count to stdout. This was necessary because `info()` from `terminal_compat.sh` writes to stdout, which would pollute the return value when captured via `$(...)`. Also added `./ait explain-cleanup:*` to the local settings whitelist for dispatcher-based invocation.
- **Issues encountered:** Initial version had `info()` stdout output being captured by command substitution, causing "unbound variable" errors. Fixed by switching to a `_cleanup_result` global variable pattern.
- **Key decisions:** Used associative arrays (`declare -A`) for grouping by key — requires bash 4+, but the project already requires this (env bash shebang picks up brew bash 5.x on macOS). The `--all` mode processes top-level aiexplains/ separately (skipping the codebrowser subdir) to avoid cross-contamination of keys.
- **Notes for sibling tasks:** The `extract_key_and_timestamp()` function defines the canonical naming pattern: `<key>__<YYYYMMDD_HHMMSS>`. Sibling t258_2 (auto-naming for aitask-explain) should use this same pattern. The `_dir_to_key()` convention from `explain_manager.py` (replace `/` with `__`) is already compatible. The cleanup script is at `aiscripts/aitask_explain_cleanup.sh` and can be invoked as `./ait explain-cleanup --all --quiet` for integration into other scripts/TUI startup.
