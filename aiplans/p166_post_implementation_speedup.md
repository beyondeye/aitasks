---
Task: t166_post_implementation_speedup.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

The post-implementation step (Step 9) in the task-workflow Claude skill involves ~35 individual bash commands: sed metadata updates, mkdir, mv, git add/rm, git commit, lock releases, and folded task cleanup. Each command triggers a Claude Code permission prompt since many involve file moves and deletes. By consolidating these into a single whitelisted script, we eliminate repetitive permission prompts and speed up the post-implementation phase significantly.

## Implementation Plan

### 1. Create `aiscripts/aitask_archive.sh` [DONE]

A new script that handles all non-interactive post-implementation operations.

**Usage:**
```bash
./aiscripts/aitask_archive.sh <task_num>              # Archive parent task
./aiscripts/aitask_archive.sh <parent>_<child>         # Archive child task
./aiscripts/aitask_archive.sh --dry-run <task_num>     # Preview only
./aiscripts/aitask_archive.sh --no-commit <task_num>   # Stage but don't commit
```

**Structured output format** (parsed by the skill for interactive follow-ups):
```
ARCHIVED_TASK:<path>    ARCHIVED_PLAN:<path>    ISSUE:<task_num>:<issue_url>
PARENT_ARCHIVED:<path>  PARENT_ISSUE:<task_num>:<url>
FOLDED_DELETED:<task_num>:<path>  FOLDED_ISSUE:<task_num>:<url>
FOLDED_WARNING:<task_num>:<status>  COMMITTED:<hash>
```

### 2. Update `.claude/skills/task-workflow/SKILL.md` Step 9 [DONE]

Replaced inline bash commands with single `aitask_archive.sh` call + output parsing.

### 3. Update settings allowlists [DONE]

Added `"Bash(./aiscripts/aitask_archive.sh:*)"` to all 3 settings files.

## Final Implementation Notes

- **Actual work done:** Created `aiscripts/aitask_archive.sh` (~310 lines) that consolidates all post-implementation archival operations into a single script. Updated SKILL.md Step 9 to use the script, reducing ~100 lines of inline bash to a single script call + output parsing. Added allowlist entries to all 3 settings files.
- **Deviations from plan:** None significant. Script structure matched the plan.
- **Issues encountered:** (1) `set -euo pipefail` with `[[ ... ]] && die` pattern causes early exit when the condition is false — fixed by using `if/then/fi` instead. (2) `get_timestamp()` is defined in `aitask_update.sh` not `task_utils.sh` — inlined `date` command instead. (3) `handle_folded_tasks` was reading from archived path before the file was moved — reordered to read folded tasks before archival.
- **Key decisions:** Structured output format (e.g., `ISSUE:<num>:<url>`) enables the skill to handle interactive parts (issue updates) by parsing script output. The script handles everything non-interactive; the skill only handles user prompts.
