---
priority: medium
effort: low
depends: [t195_4, t195_6]
issue_type: feature
status: Done
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-25 12:19
updated_at: 2026-02-25 23:48
completed_at: 2026-02-25 23:48
---

## Context

This is child task 7 of t195 (Python Code Browser TUI). It adds the Claude Code integration — a keyboard shortcut that launches Claude Code with the `aitask-explain` skill, passing the currently viewed file, optional line range selection, and the existing explain run directory.

This connects the codebrowser to the AI explanation workflow: users browse code, see task annotations, select a range of interest, and press `e` to get a detailed AI explanation of that code section.

## Key Files to Modify

- **`aiscripts/codebrowser/codebrowser_app.py`** (MODIFY):
  - Add `e` keybinding: `Binding("e", "launch_claude", "Explain in Claude")`
  - `action_launch_claude()`:
    - Get current file path and optional selection range from code viewer
    - Get explain run directory from ExplainManager
    - Detect terminal emulator (reuse pattern from board TUI)
    - Construct Claude Code invocation command
    - Launch in terminal or use `app.suspend()` for inline execution
  - Add `_find_terminal() -> str | None`: detect available terminal emulator (alacritty, kitty, ghostty, foot, xterm, etc.)
  - Add `_build_claude_command(file_path, range, run_dir) -> list[str]`: construct the command
  - Show notification on launch attempt

## Reference Files for Patterns

- `aiscripts/board/aitask_board.py` — search for `_find_terminal` or terminal detection pattern: the board TUI has a method that checks for available terminal emulators to launch external commands
- `aiscripts/board/aitask_board.py` — search for `app.suspend()` pattern: used when no separate terminal is available, suspends the TUI, runs command in the same terminal, then resumes
- `.claude/skills/aitask-explain/SKILL.md`: The explain skill accepts file paths and can auto-detect existing explain run directories. The codebrowser should construct an invocation like `claude "/aitask-explain <filepath>"` or pass additional context
- `aiscripts/codebrowser/explain_manager.py` (from t195_4): `get_run_info()` returns the run directory path

## Implementation Plan

1. Add `_find_terminal()` method to `CodeBrowserApp`:
   - Check for terminal emulators in order: `$TERMINAL` env var, `alacritty`, `kitty`, `ghostty`, `foot`, `xterm`
   - Use `shutil.which()` to check availability
   - Return the first found, or None

2. Add `_build_claude_command(file_path: Path, line_range: tuple[int,int] | None, run_dir: str | None) -> list[str]`:
   - Base: `["claude", "/aitask-explain"]`
   - Append file path as argument
   - If line_range: the explain skill will be invoked with range info
   - If run_dir: the explain skill can detect it automatically from the aiexplains directory
   - Return the full command list

3. Add `action_launch_claude()`:
   - Get current file: `self._current_file`; if None → notify "No file selected" and return
   - Get range: `self.query_one(CodeViewer).get_selected_range()`
   - Get run info: `self.explain_manager.get_run_info(self._current_file)`
   - Build command via `_build_claude_command()`
   - Terminal detection:
     a. If terminal found: `subprocess.Popen([terminal, "-e"] + command)`
     b. If no terminal: use `self.app.suspend()` context manager — suspends TUI, runs command in foreground, resumes TUI on exit
   - Show notification: "Launching Claude Code for <filename>..."

4. Add binding: `Binding("e", "launch_claude", "Explain in Claude")`

5. Handle edge cases:
   - Claude CLI not installed: check `shutil.which("claude")`, show error notification
   - Large selection (>500 lines): warn user that explanations work best for focused ranges

## Verification Steps

1. Select a file, press `e` — Claude Code should launch with the explain skill
2. Select a range (shift+arrows), press `e` — Claude should receive the range context
3. If no file selected, press `e` — should show "No file selected" notification
4. If `claude` CLI not in PATH — should show helpful error message
5. Verify the explain skill receives the correct file path
6. After Claude exits (if using suspend mode), the codebrowser should resume normally
