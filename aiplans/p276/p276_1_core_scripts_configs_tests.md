---
Task: t276_1_core_scripts_configs_tests.md
Parent Task: aitasks/t276_ambiguous_codeagent_names.md
Sibling Tasks: aitasks/t276/t276_2_skills_docs_peripheral.md
Worktree: (none — working on current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t276_1 — Core scripts, configs, and tests rename

## Goal
Rename the internal agent identifiers `claude` → `claudecode` and `gemini` → `geminicli` across all core scripts, config files, and tests. The CLI binary names (the actual commands you type) remain unchanged.

## Steps

### 1. Rename model config files (git mv)
```bash
git mv seed/models_claude.json seed/models_claudecode.json
git mv seed/models_gemini.json seed/models_geminicli.json
# .aitask-data files use ait git:
cd .aitask-data && git mv aitasks/metadata/models_claude.json aitasks/metadata/models_claudecode.json
cd .aitask-data && git mv aitasks/metadata/models_gemini.json aitasks/metadata/models_geminicli.json
```
The file content stays unchanged (model entries are LLM identifiers).

### 2. Update `aiscripts/aitask_codeagent.sh`
- Line 5: comment example `claude/opus4_6` → `claudecode/opus4_6`
- Line 21: `DEFAULT_AGENT_STRING="claude/opus4_6"` → `"claudecode/opus4_6"`
- Line 22: `SUPPORTED_AGENTS=(claude gemini codex opencode)` → `(claudecode geminicli codex opencode)`
- Line 46: error example `claude/opus4_6` → `claudecode/opus4_6`
- Lines 62-64: `get_cli_binary()` — `claude)` → `claudecode)` (still echoes `"claude"`), `gemini)` → `geminicli)` (still echoes `"gemini"`)
- Lines 74-76: `get_model_flag()` — same case label renames
- Line 99: error message example
- Lines 254-293: `build_invoke_command()` — case labels `claude)` → `claudecode)`, `gemini)` → `geminicli)`
- Lines 345-364: Help text — all `claude/opus4_6` → `claudecode/opus4_6`, `gemini/gemini2_5pro` → `geminicli/gemini2_5pro`

### 3. Update `aiscripts/settings/settings_app.py`
- Lines 56-59: MODEL_FILES dict keys and paths:
  ```python
  "claudecode": METADATA_DIR / "models_claudecode.json",
  "geminicli": METADATA_DIR / "models_geminicli.json",
  ```

### 4. Update `aiscripts/lib/config_utils.py`
- Line 36: docstring `models_claude.json` → `models_claudecode.json`

### 5. Update `aiscripts/aitask_update.sh`
- Line 124: help text `"claude/opus4_6"` → `"claudecode/opus4_6"`

### 6. Update codeagent_config.json files
Both `seed/codeagent_config.json` and `.aitask-data/aitasks/metadata/codeagent_config.json`:
```json
{
  "defaults": {
    "task-pick": "claudecode/opus4_6",
    "explain": "claudecode/sonnet4_6",
    "batch-review": "claudecode/sonnet4_6",
    "raw": "claudecode/sonnet4_6"
  }
}
```

### 7. Update tests
- `tests/test_codeagent.sh` — file copy paths, assert strings, test agent names
- `tests/test_config_utils.py` — `models_claude.json` filename references

### 8. Verify
- `bash tests/test_codeagent.sh`
- `python -m pytest tests/test_config_utils.py`
- `shellcheck aiscripts/aitask_codeagent.sh`
- Grep for stale references

## Step 9 (Post-Implementation)
After implementation: review, commit, archive, push per task-workflow.
