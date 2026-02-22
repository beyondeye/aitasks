---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: []
created_at: 2026-02-22 14:27
updated_at: 2026-02-22 14:27
---

# Fix extract_geminicli_tools.sh launching interactive mode instead of batch

## Problem

The script `aidocs/extract_geminicli_tools.sh` launches Gemini CLI in interactive mode instead of batch/headless mode. The prompt instructions are lost because they are never passed to the `gemini` command.

### Root Cause

Lines 22-24 of the script are missing backslash (`\`) line continuations:

```bash
gemini
  --yolo
  --prompt "${PROMPT}"
```

Without trailing `\` on lines 22 and 23, bash interprets this as three separate commands:
1. `gemini` — runs with no arguments, launching the interactive TUI
2. `--yolo` — treated as a separate command (fails or is ignored)
3. `--prompt "${PROMPT}"` — treated as a separate command (never executed)

### Additional Issue

The `--prompt` long flag should be verified against the actual Gemini CLI interface. According to the Gemini CLI docs, the correct flag for headless/non-interactive execution is `-p` (short form). The long form `--prompt` may or may not be supported — needs verification.

## Fix

1. Add backslash line continuations so all flags are passed to the `gemini` command:

```bash
gemini \
  --yolo \
  -p "${PROMPT}"
```

2. Verify whether `--prompt` (long form) is supported by the installed Gemini CLI version. If not, use `-p` instead.

3. Optionally, consider adding `--output-format json` or `--output-format text` for more predictable scripted output.

## References

- Script location: `aidocs/extract_geminicli_tools.sh`
- Gemini CLI headless mode docs: https://google-gemini.github.io/gemini-cli/docs/cli/headless.html
- Key Gemini CLI flags for batch mode: `-p` (prompt), `--yolo` (auto-approve), `--output-format` (text/json/stream-json)
