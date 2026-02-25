---
Task: t195_8_code_viewer_rendering_hardening.md
Parent Task: aitasks/t195_python_codebrowser.md
Sibling Tasks: aitasks/t195/t195_5_*.md
Archived Sibling Plans: aiplans/archived/p195/p195_*_*.md
Branch: main
Base branch: main
---

# Plan: t195_8 — Code Viewer Rendering Hardening

## Steps

### 1. Binary file detection
- In `load_file()`: try `read_text()`, catch `UnicodeDecodeError`
- Or use `file -b --mime-encoding` subprocess
- Show "Binary file — cannot display" message

### 2. Tab normalization
- `expandtabs(4)` on each line before rendering

### 3. Long line handling
- `no_wrap=True` on code column
- Truncate lines exceeding max_width with `...` via `Rich.Text.truncate()`

### 4. Empty file handling
- 0 lines → show "(empty file)" static message

### 5. Unicode/emoji handling
- Test with wide characters
- Ensure Rich Table column alignment accounts for character width

### 6. CSS overflow
- Add `overflow: hidden` on code display widget

## Verification
- Binary files → "Binary file" message
- Long lines → truncated, no layout break
- Tabs → consistent spaces
- Empty files → "(empty file)"
- Unicode/emoji → no crash
