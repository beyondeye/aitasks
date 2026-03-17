---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [bash_scripts, task_workflow, reviewguides]
folded_tasks: [263]
created_at: 2026-03-17 12:58
updated_at: 2026-03-17 12:59
---

Encapsulate inline bash commands found in SKILL.md files into dedicated whitelistable scripts.

## Problem

Multiple SKILL.md files contain inline bash commands that are difficult to whitelist in Claude Code's `settings.local.json`. These commands trigger permission prompts every time they run, slowing down workflows.

## Proposed Scripts

### 1. `aitask_review_summary.sh` (internal, not user-facing)
Encapsulate `git status` + `git diff --stat` into a single script.
- Used in: task-workflow/SKILL.md (Step 8), aitask-pickrem/SKILL.md (Step 9), aitask-pickweb/SKILL.md (Step 7)
- Add to whitelist template in `seed/claude_settings.local.json`

### 2. `aitask_find_task_from_commit.sh` (internal)
Encapsulate `git log -1 --name-only --pretty=format:'' | grep '^aitasks/t'` pattern.
- Used in: aitask-revert/SKILL.md (Step 4, L609), aitask-pr-import/SKILL.md (Step 5, L251)

### 3. `aitask_find_reviewguide.sh` (internal)
Encapsulate `find aireviewguides/ -name '*.md' ... | sed ... | fzf --filter "<arg>" | head -4`.
- Used in: aitask-reviewguide-classify/SKILL.md (Step 2), aitask-reviewguide-merge/SKILL.md (Step 2)

### 4. `aitask_reviewguide_vocabulary.sh` (internal)
Encapsulate reviewguide vocabulary operations:
- `read` mode: outputs contents of `reviewtypes.txt`, `reviewlabels.txt`, `reviewenvironments.txt`
- `update` mode: appends a value to a vocabulary file and sorts it
- Used in: aitask-reviewguide-classify/SKILL.md (Steps 4, 7), aitask-reviewguide-merge/SKILL.md (Step 6), aitask-reviewguide-import/SKILL.md (Steps 4, 6)

## Implementation Steps

1. Create each script in `.aitask-scripts/` following shell conventions (`set -euo pipefail`, `#!/usr/bin/env bash`)
2. Update all referenced SKILL.md files to call the new scripts instead of inline commands
3. Add new scripts to the whitelist template in `seed/claude_settings.local.json`
4. Run `shellcheck` on new scripts

## Merged from t263: custom script for final git status

currently at the end of the task_workflow (and possibly other similar workflow) we have a bash command (git status && echo "---" && git diff --stat)  fpr a summary of all changes made. the problem that this command is difficult to speciically whitelist for claude code, so perhaps encapsulate it in a custom small aitask_gitstatus.sh (internal command not exposed to users) and it to whitelisted command template in seed/claude_settings.local.json

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t263** (`t263_custom_script_for_final_git_status.md`)
