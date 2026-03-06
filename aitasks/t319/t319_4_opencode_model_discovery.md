---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [opencode, codeagent]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-06 01:18
updated_at: 2026-03-06 11:06
---

Expand OpenCode model list using programmatic discovery via OpenCode batch mode.

## Context

The current `seed/models_opencode.json` has only 3 baseline models. OpenCode (v1.2.17) supports `opencode models` (lists all available models) and `opencode models --verbose` (full JSON metadata). Additionally, running OpenCode in batch mode can discover authenticated providers and their models. The discovered models are **installation-specific** and go to `aitasks/metadata/models_opencode.json`, NOT `seed/`.

## Two-Tier Model Config

- `seed/models_opencode.json` — stays as-is (baseline/common models for `ait setup` bootstrapping). NOT updated by this task.
- `aitasks/metadata/models_opencode.json` — installation-specific, updated by model discovery. This is what `aitask_codeagent.sh` reads at runtime.

## Discovery Approach

### Primary: OpenCode batch mode
Run OpenCode in batch mode with the following prompt:
```bash
opencode run "please list the available authenticated llm model providers IN THIS cli (opencode) and for each of them the list of available llm models. for all models found this way also show a short description of the model and its capabilities. run opencode to obtain this information. do not query any file in this project."
```

### Secondary: `opencode models` command
```bash
opencode models              # Lists all available models
opencode models --verbose    # Full JSON with costs, capabilities, limits
opencode models --refresh    # Refreshes cache from models.dev
```

## Steps

### 1. Create `aiscripts/aitask_opencode_models.sh`
New script that:
- Uses `command -v opencode` to find the binary (not hardcoded paths)
- Runs `opencode models --verbose` for structured model data
- Parses the JSON output to extract model info
- Generates/updates `aitasks/metadata/models_opencode.json` with discovered models
- Follows naming convention (lowercase, underscores: `gpt_5_4`, `claude_opus_4_6`)
- Preserves existing `verified` scores when updating existing entries

### 2. Update `aitask-refresh-code-models` skill
Modify `.claude/skills/aitask-refresh-code-models/SKILL.md`:
- Add OpenCode CLI discovery as primary method (call the script above)
- Keep web research as fallback for when OpenCode is not installed
- Note that OpenCode models go to `aitasks/metadata/` not `seed/`

## Currently Known Models (from `opencode models`): 31 models

big_pickle, claude_3_5_haiku, claude_haiku_4_5, claude_opus_4_1, claude_opus_4_5, claude_opus_4_6, claude_sonnet_4, claude_sonnet_4_5, claude_sonnet_4_6, gemini_3_flash, gemini_3_pro, gemini_3_1_pro, glm_4_6, glm_4_7, glm_5, gpt_5, gpt_5_codex, gpt_5_nano, gpt_5_1, gpt_5_1_codex, gpt_5_1_codex_max, gpt_5_1_codex_mini, gpt_5_2, gpt_5_2_codex, gpt_5_3_codex, gpt_5_3_codex_spark, gpt_5_4, kimi_k2_5, minimax_m2_1, minimax_m2_5, minimax_m2_5_free

## Files to Modify/Create

- `aiscripts/aitask_opencode_models.sh` — new script for programmatic model discovery
- `aitasks/metadata/models_opencode.json` — updated with discovered models (installation-specific)
- `.claude/skills/aitask-refresh-code-models/SKILL.md` — add OpenCode CLI discovery approach

## Reference

- Current `seed/models_opencode.json` (3 baseline models)
- `.claude/skills/aitask-refresh-code-models/SKILL.md` (refresh skill)
- `aidocs/extract_opencode_tools.sh` (batch mode pattern with permission handling)
- `aiscripts/aitask_codeagent.sh` (model resolution chain, reads `aitasks/metadata/models_*.json`)

## Verification

- `bash aiscripts/aitask_opencode_models.sh` successfully queries OpenCode and outputs model data
- `aitasks/metadata/models_opencode.json` has entries for all discovered models
- Model naming follows convention (lowercase, underscores)
- `seed/models_opencode.json` is NOT modified (stays as baseline)
- `ait codeagent list-models opencode` shows expanded model list
