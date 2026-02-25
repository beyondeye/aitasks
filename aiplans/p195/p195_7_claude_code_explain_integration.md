---
Task: t195_7_claude_code_explain_integration.md
Parent Task: aitasks/t195_python_codebrowser.md
Sibling Tasks: aitasks/t195/t195_4_*.md, aitasks/t195/t195_6_*.md
Archived Sibling Plans: aiplans/archived/p195/p195_*_*.md
Branch: main
Base branch: main
---

# Plan: t195_7 — Claude Code Explain Skill Integration

## Steps

### 1. Add `_find_terminal()` to app
- Check: `$TERMINAL` env, then alacritty, kitty, ghostty, foot, xterm
- Use `shutil.which()` for detection
- Return first found or None

### 2. Add `_build_claude_command()`
- Base: `["claude", "/aitask-explain <filepath>"]`
- Include range context if selected
- ExplainManager provides run directory info (skill auto-detects)

### 3. Add `action_launch_claude()`
- Validate: current file selected, claude CLI available
- Get selection range and run info
- If terminal found: `subprocess.Popen([terminal, "-e"] + cmd)`
- If no terminal: `app.suspend()` → run foreground → resume
- Show notification

### 4. Add binding
- `Binding("e", "launch_claude", "Explain in Claude")`

### 5. Edge cases
- No file selected → notify
- Claude not installed → error message
- Large selection → warn about focused ranges

## Verification
- `e` launches Claude Code with explain skill
- Range selection passed as context
- No file → notification
- Claude missing → error
- Suspend/resume works

## Final Implementation Notes
- **Actual work done:** All plan steps implemented with corrections from verification. Added `_find_terminal()`, `action_launch_claude()` (as `@work(exclusive=True)` async method), and `e` binding to `codebrowser_app.py`. Extended the `aitask-explain` skill SKILL.md to accept `path:start-end` range syntax (e.g., `src/app.py:10-50`) as argument and focus analysis on specified ranges. Dropped the separate `_build_claude_command()` method — command is built inline following the board TUI's simpler pattern.
- **Deviations from plan:** (1) Eliminated `_build_claude_command()` — the board TUI builds commands inline (e.g., `["claude", f"/aitask-pick {num}"]`), so we follow the same pattern. (2) Changed subprocess separator from `-e` to `--` to match the board TUI pattern (`aitask_board.py:2574`). (3) Extended terminal emulator list beyond the original plan — combined modern terminals (alacritty, kitty, ghostty, foot) with the board TUI's Linux desktop list (x-terminal-emulator, xdg-terminal-exec, gnome-terminal, etc.). (4) Added `@work(exclusive=True)` async decorator to `action_launch_claude()` following the board TUI's consistent pattern for all external command methods. (5) Added `path:start-end` range syntax to the explain skill (per user request) instead of just passing plain paths — the original task description mentioned range context but the initial plan didn't address how to convey it. (6) Dropped "large selection warning" edge case — unnecessary complexity for initial implementation.
- **Issues encountered:** None. The explain skill doesn't have a CLI parameter for accepting pre-generated run directories, so the codebrowser's explain data (in `aiexplains/codebrowser/`) stays independent from what the explain skill generates on its own (in `aiexplains/`). This is a reasonable separation — the codebrowser data is for annotations, the skill generates its own data for explanations.
- **Key decisions:** Used relative path from project root (not absolute) when invoking Claude, since Claude runs at the project root. The `get_selected_range()` returns 1-indexed values which map directly to the `path:start-end` format. The suspend pattern doesn't need post-suspend refresh since the explain skill operates independently from codebrowser state.
- **Notes for sibling tasks:** `_find_terminal()` is a standalone method that can be reused by future features needing external command launching. The `@work(exclusive=True)` pattern means only one external command launches at a time. The explain skill now supports `path:start-end` argument syntax — any other integration point can use this format. The `work` decorator must be imported as `from textual import work` (not from `textual.worker`).
