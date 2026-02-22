---
Task: t203_fix_extract_geminicli_tools_batch_mode.md
Branch: main
Base branch: main
---

# Plan: Fix extract_geminicli_tools.sh batch mode (t203)

## Context

The script `aidocs/extract_geminicli_tools.sh` launches Gemini CLI in interactive mode instead of batch mode because lines 22-24 are missing backslash (`\`) line continuations. Without them, `gemini` runs with no arguments (interactive TUI), and `--yolo` and `--prompt` are treated as separate (failing) commands.

## Changes

**File: `aidocs/extract_geminicli_tools.sh`** (lines 22-24)

Replace:
```bash
gemini
  --yolo
  --prompt "${PROMPT}"
```

With:
```bash
gemini \
  --yolo \
  -p "${PROMPT}"
```

Changes:
1. Add `\` line continuations on lines 22 and 23
2. Use `-p` instead of `--prompt` (the short form is the documented flag for Gemini CLI headless mode)

## Verification

```bash
# Syntax check
bash -n aidocs/extract_geminicli_tools.sh

# Shellcheck
shellcheck aidocs/extract_geminicli_tools.sh
```

## Final Implementation Notes
- **Actual work done:** Added backslash line continuations on lines 22-23 and changed `--prompt` to `-p` (documented short form for Gemini CLI headless mode)
- **Deviations from plan:** None
- **Issues encountered:** None — straightforward fix
- **Key decisions:** Used `-p` (short form) instead of `--prompt` per Gemini CLI documentation
