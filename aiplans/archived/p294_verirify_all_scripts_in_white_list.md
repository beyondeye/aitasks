---
Task: t294_verirify_all_scripts_in_white_list.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Verify that all bash scripts in `aiscripts/` are whitelisted in `seed/claude_settings.local.json`. This seed file is used by `ait setup` to bootstrap new projects. Missing scripts cause permission prompts when Claude Code runs them.

## Analysis

**Currently whitelisted (22 top-level scripts + 1 lib):**
All scripts in the `allow` array at `seed/claude_settings.local.json`.

**Missing from whitelist (11 top-level scripts):**

| Script | Purpose |
|--------|---------|
| `aitask_board.sh` | TUI board launcher |
| `aitask_claim_id.sh` | Task ID claiming |
| `aitask_codeagent.sh` | Code agent wrapper |
| `aitask_codebrowser.sh` | Code browser |
| `aitask_install.sh` | Installation script |
| `aitask_issue_import.sh` | Import issues from tracker |
| `aitask_pr_close.sh` | Close/decline PRs |
| `aitask_pr_import.sh` | Import PRs as tasks |
| `aitask_settings.sh` | Settings management |
| `aitask_setup.sh` | Project setup/bootstrap |
| `aitask_sync.sh` | Remote sync |

## Implementation

Add 5 missing scripts to the whitelist (alphabetical order).

Excluded by design (not intended for direct Claude Code invocation): board, codeagent, codebrowser, install, settings, setup, task_utils, terminal_compat.

Added entries:
```
"Bash(./aiscripts/aitask_claim_id.sh:*)",
"Bash(./aiscripts/aitask_issue_import.sh:*)",
"Bash(./aiscripts/aitask_pr_close.sh:*)",
"Bash(./aiscripts/aitask_pr_import.sh:*)",
"Bash(./aiscripts/aitask_sync.sh:*)",
```

**File modified:** `seed/claude_settings.local.json`

## Final Implementation Notes
- **Actual work done:** Added 5 missing whitelist entries to seed/claude_settings.local.json. JSON validated successfully.
- **Deviations from plan:** None — straightforward addition.
- **Issues encountered:** None.
- **Key decisions:** 8 scripts intentionally excluded from whitelist (board, codeagent, codebrowser, install, settings, setup, task_utils, terminal_compat) — they are not intended for direct Claude Code invocation. Library scripts (task_utils.sh, terminal_compat.sh) are sourced internally by other scripts and don't need whitelisting.
