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
