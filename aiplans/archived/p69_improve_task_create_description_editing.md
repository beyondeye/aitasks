---
Task: t69_improve_task_create_description_editing.md
Branch: main
Base branch: main
---

# Plan: t69 — Improve task create description editing

## Context

When using `aitask_create.sh` interactively, the description input (`read -rp`) doesn't support arrow key navigation. Pressing left/right arrows inserts escape characters (`[D`, `[C`) instead of moving the cursor. Long lines that wrap past terminal width are also impossible to navigate back through. The fix is to add bash's `-e` flag to enable readline support on the relevant `read` calls.

## Approach

Add the `-e` flag to three `read -rp` calls that accept free-text input. This enables bash's built-in readline library, which handles arrow keys, cursor movement, Ctrl+A/E (home/end), Ctrl+W (delete word), and proper wrapped-line navigation — all with zero new dependencies.

## File to modify

**`aitask_create.sh`** — 3 single-character insertions:

| Line | Current | New | Purpose |
|------|---------|-----|---------|
| 474 | `read -rp "Enter new label: "` | `read -erp "Enter new label: "` | Label input |
| 608 | `read -rp "Task name (short, will be sanitized): "` | `read -erp "Task name (short, will be sanitized): "` | Task name input |
| 627 | `read -rp "Enter description (or press Enter to skip): "` | `read -erp "Enter description (or press Enter to skip): "` | Description input (primary fix) |

Lines 757 and 1067 (`read -rp "Commit to git? [Y/n] "`) are left unchanged — they're simple yes/no prompts that don't benefit from readline.

## Why `-e` works here

- The function `get_task_definition()` is called inside a command substitution (`task_desc=$(get_task_definition)`), but this only captures stdout. Readline's prompt goes to stderr, and stdin remains the terminal — so readline works correctly.
- This is the same pattern used by fzf calls already in the function (line 652 uses `< /dev/tty`).

## Verification

1. Run `./aitask_create.sh` and reach the description prompt
2. Type text, use left/right arrow keys — cursor should move (no `[D`/`[C` inserted)
3. Type a long line that wraps, arrow-left past the wrap — should work
4. Ctrl+A (home), Ctrl+E (end), Ctrl+W (delete word) — should all work
5. Press Enter with empty input — should still be treated as "skip"
6. Complete a full task creation — verify no readline artifacts in the output file
