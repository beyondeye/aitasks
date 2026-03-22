---
Task: t428_1_core_aitask_qa_skill.md
Parent Task: aitasks/t428_new_skill_aitask_qa.md
Sibling Tasks: aitasks/t428/t428_2_*.md, aitasks/t428/t428_3_*.md, aitasks/t428/t428_4_*.md, aitasks/t428/t428_5_*.md, aitasks/t428/t428_6_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Core aitask-qa Skill

## Overview

Create the standalone `/aitask-qa` skill for test/QA analysis. The skill analyzes changes from any task (active or archived), discovers and runs tests, identifies gaps, proposes a test plan, and optionally creates follow-up tasks.

## Steps

### 1. Add `recent-archived` subcommand to `aitask_query_files.sh`

**File:** `.aitask-scripts/aitask_query_files.sh`

Add a new subcommand case in the main `case "$subcommand" in` block:

```bash
recent-archived)
    local limit="${2:-15}"
    local entries=()
    # Scan parent archived tasks
    for f in "$ARCHIVED_DIR"/t*_*.md; do
        [[ -e "$f" ]] || continue
        local completed_at
        completed_at=$(read_yaml_field "$f" "completed_at")
        if [[ -z "$completed_at" ]]; then
            # Fallback to file mtime
            completed_at=$(stat -c '%Y' "$f" 2>/dev/null || stat -f '%m' "$f" 2>/dev/null)
        fi
        local issue_type
        issue_type=$(read_yaml_field "$f" "issue_type")
        local basename_f
        basename_f=$(basename "$f" .md)
        entries+=("${completed_at}|${f}|${issue_type}|${basename_f}")
    done
    # Also scan child archived tasks
    for d in "$ARCHIVED_DIR"/t*/; do
        [[ -d "$d" ]] || continue
        for f in "$d"t*_*.md; do
            [[ -e "$f" ]] || continue
            local completed_at
            completed_at=$(read_yaml_field "$f" "completed_at")
            if [[ -z "$completed_at" ]]; then
                completed_at=$(stat -c '%Y' "$f" 2>/dev/null || stat -f '%m' "$f" 2>/dev/null)
            fi
            local issue_type
            issue_type=$(read_yaml_field "$f" "issue_type")
            local basename_f
            basename_f=$(basename "$f" .md)
            entries+=("${completed_at}|${f}|${issue_type}|${basename_f}")
        done
    done
    if [[ ${#entries[@]} -eq 0 ]]; then
        echo "NO_RECENT_ARCHIVED"
        exit 0
    fi
    # Sort by completed_at descending, output top N
    printf '%s\n' "${entries[@]}" | sort -t'|' -k1 -rn | head -n "$limit" | while IFS='|' read -r ca path itype tname; do
        echo "RECENT_ARCHIVED:${path}|${ca}|${itype}|${tname}"
    done
    ;;
```

Also update the help text and subcommand docs at the top of the file.

### 2. Create `.claude/skills/aitask-qa/SKILL.md`

Create the full skill definition with these sections:
- Frontmatter: `name: aitask-qa`, `description: Run QA analysis on any task...`
- Step 0: Profile Selection (reference execution-profile-selection.md)
- Step 1: Task Selection (argument handling + recent-archived listing)
- Step 2: Change Analysis (commits, diff, plan file)
- Step 3: Test Discovery (scan test files, map source→test)
- Step 4: Test Execution (project_config.yaml keys, auto-detect fallback)
- Step 5: Test Plan Proposal (categorized, profile-aware)
- Step 6: Follow-up Task Creation (aitask_create.sh)
- Step 7: Satisfaction Feedback

Key patterns to follow:
- Use `aitask_query_files.sh` for all file resolution
- Use `AskUserQuestion` with paginated options for task selection
- Use `git log --oneline --all --grep="(t<task_id>)"` for commit detection
- Support both active and archived tasks
- Profile keys: `qa_mode`, `qa_run_tests`

### 3. Register skill trigger in `.claude/settings.local.json`

Add aitask-qa to the skill list. The trigger description should mention: QA, testing, test analysis, test coverage.

### 4. Document profile keys in `profiles.md`

Add `qa_mode` and `qa_run_tests` rows to the profile schema table.

## Verification

1. `./aitask-scripts/aitask_query_files.sh recent-archived 5` — verify output format
2. Check skill loads in Claude Code
3. Test with an archived task ID
4. Test interactive mode (no argument)

## Post-Implementation

Step 9 of task-workflow for archival.
