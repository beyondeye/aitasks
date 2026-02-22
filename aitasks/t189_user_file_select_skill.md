---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [aitasks, claudeskills]
created_at: 2026-02-22 09:27
updated_at: 2026-02-22 09:27
---

Create a new Claude Code skill `.claude/skills/user-file-select/SKILL.md` that provides a reusable, interactive file selection mechanism for other skills.

## Context
Currently both `aitask-explain` (Step 1) and `aitask-explore` (Step 1) use simple free-text `AskUserQuestion` prompts for file/area selection. This gives a poor UX because the user must know exact file paths. This skill extracts file selection into a shared, sophisticated mechanism that can be invoked by other skills.

## Three Search Modes

### Mode 1: Search by keywords
- User provides one or more keywords (e.g., "task resolve archive")
- Call a new bash helper script `aiscripts/aitask_find_files.sh` which:
  - Searches keywords inside all git-tracked project files using `grep -c` or similar
  - Ranks files by total number of keyword matches across all keywords
  - Returns a numbered list of top results (e.g., top 20) with match counts
- Output format from script: `<rank>|<match_count>|<file_path>` (pipe-delimited, one per line)

### Mode 2: Search by names (fuzzy)
- User provides one or more partial filenames (e.g., "task_utils terminal_compat")
- The bash helper script performs fuzzy name matching:
  - Use `git ls-files` as the file list
  - Match each partial name against the filename (basename) and full path
  - Rank by match quality (exact basename match > substring in basename > substring in full path)
  - Support matching multiple names simultaneously — a file matching more names ranks higher
- Return a numbered ranked list

### Mode 3: Search by functionality
- User provides a natural language description of what the code does (e.g., "files that handle git commit message parsing")
- The LLM (Claude) is fully responsible for finding relevant files using whatever tools it deems effective (Glob, Grep, Read, etc.)
- Claude produces a ranked list of files with brief relevance descriptions
- Present in the same numbered format as the other modes

## User Selection from Ranked List

After any mode produces a ranked list, present it to the user as a numbered list:
```
1. aiscripts/lib/task_utils.sh (12 matches)
2. aiscripts/aitask_changelog.sh (8 matches)
3. aiscripts/aitask_archive.sh (6 matches)
...
```

Then ask the user to select files using index-based selection supporting:
- Individual indices: `1,4,5`
- Ranges: `3-5`
- Mixed: `1, 3-5, 7, 9-12`
- `all` to select everything in the list

Parse the selection string and output the final list of full file paths from project root.

## Skill Interface

### Input (arguments)
The skill can be invoked with optional arguments:
- No arguments: show mode selection menu
- `--keywords "term1 term2"`: jump directly to keyword search
- `--names "partial1 partial2"`: jump directly to name search
- `--describe "what the files do"`: jump directly to functionality search

### Output
The skill's final output is a newline-separated list of selected file paths (full paths from project root). This output is what calling skills (aitask-explain, aitask-explore) will consume.

## Files to Create

### `aiscripts/aitask_find_files.sh`
Bash helper script for modes 1 and 2:
```
aitask_find_files.sh --keywords "term1 term2" [--max-results N]
aitask_find_files.sh --names "partial1 partial2" [--max-results N]
```
- Uses `set -euo pipefail`, sources `terminal_compat.sh`
- Max results default: 20
- Output: `<rank>|<match_count>|<file_path>` per line
- For `--keywords`: search file contents with grep, count matches, sort descending
- For `--names`: fuzzy match against `git ls-files`, score by match quality, sort descending

### `.claude/skills/user-file-select/SKILL.md`
Skill workflow:
1. Mode selection (keywords / names / functionality) via `AskUserQuestion`
2. Prompt for search input (keywords, partial names, or description)
3. Execute search (call bash script for modes 1-2, use LLM tools for mode 3)
4. Present ranked results
5. Ask user for index-based selection (via `AskUserQuestion` free text)
6. Parse selection string (handle `1,3-5,7` format)
7. Output final file list

### `.claude/settings.local.json`
Add: `"Bash(./aiscripts/aitask_find_files.sh:*)"` to allowed commands

## Reference Files
- `.claude/skills/aitask-explain/SKILL.md` — current simple file selection in Step 1 (to be replaced by follow-up task)
- `.claude/skills/aitask-explore/SKILL.md` — current free-text area selection in Step 1 (to be replaced by follow-up task)
- `aiscripts/aitask_explain_extract_raw_data.sh` — example of how bash helpers integrate with skills
- `aiscripts/lib/terminal_compat.sh` — shell library conventions (die, warn, info helpers)

## Verification
1. Test `aitask_find_files.sh --keywords "resolve task"` — should return ranked files containing those keywords
2. Test `aitask_find_files.sh --names "task_utils terminal"` — should find task_utils.sh and terminal_compat.sh
3. Test the skill manually: `/user-file-select` and try each mode
4. `shellcheck aiscripts/aitask_find_files.sh`
5. Verify index parsing handles: `1`, `1,3`, `1-5`, `1,3-5,7,9-12`, `all`
