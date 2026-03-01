---
priority: medium
effort: medium
depends: [268_5]
issue_type: feature
status: Ready
labels: [modelwrapper]
created_at: 2026-03-01 09:00
updated_at: 2026-03-01 09:00
---

## Context

This is child task 7 of t268 (Code Agent Wrapper). It adds `implemented_with` frontmatter tracking to task files, recording which code agent/model was used to implement each task. This metadata is useful for tracking which models produce better implementation quality.

## Key Files

- **Modify:** `aiscripts/aitask_codeagent.sh` (set env var before invoking code agent)
- **Modify:** `.claude/skills/task-workflow/SKILL.md` (read env var, write `implemented_with` to frontmatter)
- **Modify:** `aiscripts/aitask_update.sh` (support `--implemented-with` flag, parse new field)
- **Modify:** `aiscripts/lib/task_utils.sh` (add `implemented_with` to known frontmatter fields)
- **Modify:** `aiscripts/board/aitask_board.py` (display `implemented_with` in task detail view if present)
- **Modify:** `aiscripts/aitask_ls.sh` (handle new field gracefully)
- **Verify:** All scripts that parse task frontmatter tolerate the new field without errors

## Implementation Plan

### 1. Set environment variable in wrapper

When `aitask_codeagent.sh invoke` is called, set `AITASK_AGENT_STRING=<agent_string>` as an environment variable before `exec`-ing the code agent. This allows the skill running inside the code agent to know which agent/model launched it.

### 2. Update pick skill workflow

In `.claude/skills/task-workflow/SKILL.md`, at task claim time (Step 4):
- Read `AITASK_AGENT_STRING` env var
- If set, write `implemented_with: <value>` to the task frontmatter

### 3. Update `aitask_update.sh`

- Support `--implemented-with <agent_string>` flag
- Parse `implemented_with` field from frontmatter

### 4. Update `task_utils.sh`

- Add `implemented_with` to the list of known frontmatter fields for parsing/extraction

### 5. Update board TUI display

- In `aitask_board.py`, display `implemented_with` in the task detail view panel if the field is present in the task frontmatter

### 6. Verify compatibility

- Ensure `aitask_ls.sh` handles the new field gracefully (no display change unless `-v` verbose)
- Ensure all scripts that parse task frontmatter tolerate the new field without errors

## Design Decision: Environment Variable Approach

Chosen over alternatives:
- **Option A (chosen): Environment variable** — wrapper sets `AITASK_AGENT_STRING` before `exec`. Simple, works across all code agents.
- Option B: Temp file — more complex, cleanup needed
- Option C: CLI argument — not all code agents support passing custom args to skills

## Verification Steps

1. `aitask_codeagent.sh invoke task-pick 42` sets `AITASK_AGENT_STRING` env var
2. Task pick skill reads env var and writes `implemented_with` to frontmatter
3. `ait update --implemented-with claude/opus4_6 42` works
4. Board TUI shows `implemented_with` in task detail view
5. `ait ls` works correctly with tasks that have `implemented_with` field
6. Existing tasks without `implemented_with` field are unaffected
