---
Task: t204_gotchas_running_claude_not_project_root_directory.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

All aitasks skills run bash commands with relative paths like `./aiscripts/aitask_ls.sh`. The permissions in `.claude/settings.local.json` are defined using these same relative paths. If Claude Code is started from a subdirectory instead of the project root, none of these paths match, causing Claude to prompt for permission on every single command.

## Approaches Tried

### Approach 1: Bash check script (abandoned)
Created `aiscripts/lib/check_project_root.sh` + Step 0 in 12 skills. **Didn't work** because Claude Code auto-cd's to the project root before running bash commands, so the script always passes silently.

### Approach 2: CLAUDE.md instruction (abandoned)
Added an instruction to CLAUDE.md telling Claude to check the primary working directory. **User feedback:** also doesn't work — the issue is at the permission-matching level, not at the instruction level.

### Approach 3: Website documentation (implemented)
Document the requirement in the website docs so users know about it before encountering the issue.

## Final Implementation

### Main skills page
Added a prominent blockquote warning to `website/content/docs/skills/_index.md` explaining:
- Skills use relative paths that must match `.claude/settings.local.json` entries
- Running from a subdirectory causes permission prompts on every command
- Must `cd` to project root before launching Claude Code

### Individual skill pages (12 pages)
Added a brief note after the Usage section on each skill page:
> **Note:** Must be run from the project root directory. See Skills overview for details.

Files updated:
- `website/content/docs/skills/aitask-pick.md`
- `website/content/docs/skills/aitask-explore.md`
- `website/content/docs/skills/aitask-review.md`
- `website/content/docs/skills/aitask-fold.md`
- `website/content/docs/skills/aitask-create.md`
- `website/content/docs/skills/aitask-explain.md`
- `website/content/docs/skills/aitask-wrap.md`
- `website/content/docs/skills/aitask-stats.md`
- `website/content/docs/skills/aitask-changelog.md`
- `website/content/docs/skills/aitask-reviewguide-import.md`
- `website/content/docs/skills/aitask-reviewguide-classify.md`
- `website/content/docs/skills/aitask-reviewguide-merge.md`

## Final Implementation Notes
- **Actual work done:** Documentation-only change across 13 website files (1 index + 12 skill pages)
- **Deviations from plan:** Two prior approaches (bash script, CLAUDE.md instruction) were tried and abandoned based on user feedback before settling on documentation
- **Issues encountered:** Claude Code auto-cd's to project root, making bash-level detection impossible; CLAUDE.md instructions also ineffective for the same reason
- **Key decisions:** Documentation is the right approach since this is a setup/launch requirement, not something that can be detected or fixed at runtime
