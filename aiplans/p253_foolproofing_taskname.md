---
Task: t253_foolproofing_taskname.md
Worktree: N/A (current branch)
Branch: main
Base branch: main
---

# Plan: Foolproofing Task Name Input (t253)

## Context

Users frequently enter a full task description into the task name prompt by mistake, resulting in a long, meaningless sanitized filename. This change detects when the raw input exceeds 50 characters and offers to treat it as the description instead, then re-asks for the actual task name.

This only applies to **interactive mode** — batch mode users provide `--name` explicitly.

## Key Files

- `aiscripts/aitask_create.sh` — sole file to modify
  - `get_task_name()` (lines 907-918): where the name is read
  - `get_task_definition()` (lines 922-999): description input loop
  - `main()` (lines 1374-1384): where name + description are collected sequentially

## Implementation

### 1. Add a global variable `PREDESC_TEXT=""` near top of script

Declare `PREDESC_TEXT=""` alongside other global variables so it can be set inside `get_task_name()` and read by `main()`.

### 2. Modify `get_task_name()` to detect long input

After reading the raw input, check if its length exceeds 50 characters (before sanitization). If so, ask the user via fzf menu whether it's actually a description. If yes, store it in `PREDESC_TEXT` and re-ask for the actual task name.

### 3. Modify `get_task_definition()` to accept optional initial description

Accept an optional parameter. If provided, initialize `task_desc` with it and inform the user.

### 4. Wire it up in `main()`

Pass `PREDESC_TEXT` to `get_task_definition()`.

## Verification

1. Interactive: enter long string > 50 chars at name prompt → should trigger detection
2. Select "Yes, it's a description" → re-ask name, pre-populate description
3. Select "No, it's the task name" → normal flow (truncated)
4. Short name (<= 50 chars) → no prompt
5. `shellcheck aiscripts/aitask_create.sh`

## Final Implementation Notes
- **Actual work done:** Modified `get_task_name()` to detect >50 char input, offer fzf menu to treat as description, and output both name+predesc via stdout (line 1 = name, line 2 = predesc). Modified `get_task_definition()` to accept optional initial description parameter. Updated `main()` to parse combined output and pass predesc through.
- **Deviations from plan:** Used stdout line-based protocol instead of a global variable (`PREDESC_TEXT`), because `get_task_name()` runs in a subshell via `$(...)` so globals can't propagate back. User-visible messages use `>&2` to avoid being captured.
- **Issues encountered:** None. Shellcheck passed with only pre-existing info/style warnings.
- **Key decisions:** Used `head -1` / `sed '1d'` to split the two-line output. Used `warn()` for the detection message (goes to stderr automatically) and raw `echo >&2` for the info message inside the subshell.
