---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: []
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-02 19:52
updated_at: 2026-03-02 20:07
completed_at: 2026-03-02 20:07
---

Rename agent identifiers from claude/gemini to claudecode/geminicli in all core scripts, config files, and tests.

## Context
The internal agent identifier is changing: claude → claudecode, gemini → geminicli. The CLI binary names stay the same (claude, gemini). codex and opencode are unchanged.

## Key Files to Modify

### Shell Scripts
- `aiscripts/aitask_codeagent.sh` — The main codeagent wrapper (~25 references):
  - Line 21: `DEFAULT_AGENT_STRING="claude/opus4_6"` → `"claudecode/opus4_6"`
  - Line 22: `SUPPORTED_AGENTS=(claude gemini codex opencode)` → `(claudecode geminicli codex opencode)`
  - Line 45: regex pattern for agent string validation needs to allow longer names
  - Line 46: error message example
  - Lines 63-64: `get_cli_binary()` case — `claude)` → `claudecode)` echoing `"claude"`, `gemini)` → `geminicli)` echoing `"gemini"`
  - Lines 75-76: `get_model_flag()` case — same pattern
  - Lines 254-284: `build_invoke_command()` case statements
  - Lines 345-364: Help text examples (`claude/opus4_6` → `claudecode/opus4_6`, `gemini/gemini2_5pro` → `geminicli/gemini2_5pro`)
- `aiscripts/aitask_update.sh` — Line 124: help text example `"claude/opus4_6"` → `"claudecode/opus4_6"`
- `aiscripts/lib/config_utils.py` — Line 36: docstring example `models_claude.json` → `models_claudecode.json`

### Python Settings TUI
- `aiscripts/settings/settings_app.py` — Lines 56-60: MODEL_FILES dict:
  - Key `"claude"` → `"claudecode"`, path `models_claude.json` → `models_claudecode.json`
  - Key `"gemini"` → `"geminicli"`, path `models_gemini.json` → `models_geminicli.json`

### Config Files (content updates)
- `seed/codeagent_config.json` — Change all `"claude/..."` to `"claudecode/..."`
- `.aitask-data/aitasks/metadata/codeagent_config.json` — Same changes

### File Renames (git mv)
- `seed/models_claude.json` → `seed/models_claudecode.json`
- `seed/models_gemini.json` → `seed/models_geminicli.json`
- `.aitask-data/aitasks/metadata/models_claude.json` → `.aitask-data/aitasks/metadata/models_claudecode.json`
- `.aitask-data/aitasks/metadata/models_gemini.json` → `.aitask-data/aitasks/metadata/models_geminicli.json`
NOTE: The content INSIDE these JSON files stays unchanged — the model entries (opus4_6, cli_id etc.) are LLM identifiers, not agent identifiers.

### Tests
- `tests/test_codeagent.sh` — Lines 79-81: file copy paths, Lines 118-120: assert strings (`AGENT:claude` → `AGENT:claudecode`), Lines 125-172: test case agent strings
- `tests/test_config_utils.py` — Lines 115-116, 329, 336: `models_claude.json` → `models_claudecode.json`

## Reference Files for Patterns
- `aiscripts/aitask_codeagent.sh` — The main file to understand how agent names are used throughout (identifiers vs binary names vs model IDs)
- `seed/codeagent_config.json` — Shows the agent string format: `<agent>/<model>`

## Implementation Plan
1. Rename model config files with `git mv` (seed/ and .aitask-data/)
2. Update `aitask_codeagent.sh` — all SUPPORTED_AGENTS, case statements, help text
3. Update `settings_app.py` MODEL_FILES dict
4. Update `config_utils.py` docstring
5. Update `aitask_update.sh` help text
6. Update codeagent_config.json files (seed/ and .aitask-data/)
7. Update test files to match new names
8. Run tests and shellcheck

## Verification
- `bash tests/test_codeagent.sh`
- `python -m pytest tests/test_config_utils.py` (or `bash tests/test_config_utils.py` if bash-based)
- `shellcheck aiscripts/aitask_codeagent.sh`
- `grep -r 'models_claude\|models_gemini' aiscripts/ seed/ tests/` — should only find models_claudecode/models_geminicli
