---
Task: t258_4_update_peripheral_files.md
Parent Task: aitasks/t258_automatic_clean_up_of_aiexplains_for_code_browser.md
Sibling Tasks: aitasks/t258/t258_1_*.md, aitasks/t258/t258_2_*.md, aitasks/t258/t258_3_*.md, aitasks/t258/t258_5_*.md
Archived Sibling Plans: aiplans/archived/p258/p258_1_*.md, aiplans/archived/p258/p258_2_*.md, aiplans/archived/p258/p258_3_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

## Plan: Update peripheral files

### Step 1: Update `aitask_explain_runs.sh`

**File:** `aiscripts/aitask_explain_runs.sh`

**Add `--cleanup-stale` mode:**
- In `parse_args()` add case:
```bash
--cleanup-stale)
    MODE="cleanup-stale"
    shift
    ;;
```
- In `main()` add case:
```bash
cleanup-stale) exec "$SCRIPT_DIR/aitask_explain_cleanup.sh" --all ;;
```

**Update `list_runs()`:**
- After scanning `$AIEXPLAINS_DIR/*/files.txt`, also scan `$AIEXPLAINS_DIR/codebrowser/*/files.txt`
- Add section headers for clarity

**Update `interactive()` display:**
- Parse dir_key from keyed names for better display:
```bash
if [[ "$run_name" =~ ^(.+)__([0-9]{8}_[0-9]{6})$ ]]; then
    display_name="${BASH_REMATCH[1]} @ ${BASH_REMATCH[2]}"
fi
```

**Update help text:** Add `--cleanup-stale` to modes and examples.

### Step 2: Update SKILL.md

**File:** `.claude/skills/aitask-explain/SKILL.md`

- Line 193: Update naming from `aiexplains/<timestamp>/` to `aiexplains/<dir_key>__<timestamp>/`
- After Step 3 gather: Note auto-cleanup of stale runs
- Step 6 Cleanup: Note stale cleanup is automatic; manual cleanup removes latest run

### Step 3: Verify

1. `shellcheck aiscripts/aitask_explain_runs.sh`
2. `./aiscripts/aitask_explain_runs.sh --list` — shows both top-level and codebrowser runs
3. `./aiscripts/aitask_explain_runs.sh --cleanup-stale` — delegates to cleanup script
4. Review SKILL.md changes

### Step 9: Post-Implementation

Archive task following the standard workflow.
