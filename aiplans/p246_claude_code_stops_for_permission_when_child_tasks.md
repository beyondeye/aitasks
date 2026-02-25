---
Task: t246_claude_code_stops_for_permission_when_child_tasks.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

When Claude Code executes `/aitask-pick` with a child task argument (e.g., `/aitask-pick 214_3`), it runs multiple raw `ls` commands to discover files (task files, children directories, archived siblings). These trigger permission prompts despite `Bash(ls:*)` being whitelisted — likely because Claude sometimes issues compound commands with `;` or `&&` that don't match the simple pattern. Additionally, the user observed these `ls` commands running BEFORE the execution profile selection prompt, which should always come first.

## Solution

Create `aiscripts/aitask_query_files.sh` — a consolidated helper script for all file/directory queries currently done via raw `ls` in skill files. One whitelisted script replaces scattered `ls` calls.

## Implementation Steps

- [x] Step 1: Create `aiscripts/aitask_query_files.sh` with 7 subcommands (task-file, has-children, child-file, sibling-context, plan-file, archived-children, resolve)
- [x] Step 2: Whitelist in `.claude/settings.local.json`
- [x] Step 3: Update `.claude/skills/aitask-pick/SKILL.md` — replaced 4 raw `ls` calls + added step ordering enforcement note
- [x] Step 4: Update `.claude/skills/task-workflow/SKILL.md` — replaced 3 raw `ls` calls
- [x] Step 5: Create `tests/test_query.sh` — 35 tests all passing
- [x] Step 6: Shellcheck + tests pass
- [ ] Step 7: Create follow-up task for remaining skills
- [ ] Step 9: Archive + commit

## Final Implementation Notes

- **Actual work done:** Created aitask_query_files.sh with 7 subcommands, updated aitask-pick and task-workflow skills, added whitelist entry, created 36 tests
- **Deviations from plan:** Found and fixed a bug during user testing: `ls ... | wc -l` pipeline with `set -o pipefail` would exit the script when `ls` found no matches (non-zero exit propagated through pipeline). Fixed by replacing with safe for-loop + counter pattern
- **Issues encountered:** "Sibling tool call errored" in Claude Code when running parallel tool calls — this is a Claude Code behavior, not script-related. Script itself works correctly when called individually
- **Key decisions:** Used for-loop glob iteration with `[[ -e "$f" ]] || continue` guard instead of `ls | wc -l` pipeline for robustness with `set -euo pipefail`

## Verification

- `shellcheck aiscripts/aitask_query_files.sh` — clean (info-level only: SC1091)
- `bash tests/test_query.sh` — 36/36 passed (including empty-dir edge case)
- Smoke tests: `resolve 246`, `plan-file 246`, `sibling-context 214` all return correct output
