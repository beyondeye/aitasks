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
