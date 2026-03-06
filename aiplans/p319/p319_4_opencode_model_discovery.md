---
Task: t319_4_opencode_model_discovery.md
Parent Task: aitasks/t319_opencode_support.md
Sibling Tasks: aitasks/t319/t319_1_opencode_skill_wrappers.md, aitasks/t319/t319_2_opencode_setup_install.md, aitasks/t319/t319_3_opencode_docs_update.md
Archived Sibling Plans: (check aiplans/archived/p319/ at implementation time)
Worktree: (none - working on current branch)
Branch: (current branch)
Base branch: main
---

# Plan: OpenCode Model Discovery and Refresh

## Overview

Create a script to programmatically discover OpenCode models using `opencode models` and `opencode run` batch mode. Update the refresh skill to use CLI-based discovery for OpenCode.

**Key principle:** Discovered models go to `aitasks/metadata/models_opencode.json` (installation-specific), NOT `seed/models_opencode.json` (baseline for bootstrapping).

## Step 1: Create model discovery script

**File:** `aiscripts/aitask_opencode_models.sh`

Script that:
1. Uses `command -v opencode` to find the binary (no hardcoded paths)
2. Runs `opencode models --verbose` to get structured JSON output
3. Parses the verbose output to extract model metadata (id, name, provider, capabilities, costs)
4. Converts to aitasks model format with naming convention (lowercase, underscores)
5. Generates/updates `aitasks/metadata/models_opencode.json`
6. Preserves existing `verified` scores for models that already have entries

**Model name conversion rules:**
- `opencode/claude-opus-4-6` → `claude_opus_4_6`
- `opencode/gpt-5.3-codex` → `gpt_5_3_codex`
- `opencode/big-pickle` → `big_pickle`
- Strip the `opencode/` prefix, replace `-` and `.` with `_`

**Output format (matching existing JSON schema):**
```json
{
  "models": [
    {
      "name": "claude_opus_4_6",
      "cli_id": "opencode/claude-opus-4-6",
      "notes": "Claude Opus 4.6 via OpenCode Zen provider",
      "verified": { "task-pick": 0, "explain": 0, "batch-review": 0 }
    }
  ]
}
```

**Note:** The `cli_id` includes the `opencode/` provider prefix since that's what `-m` flag expects.

### Alternative: Batch mode discovery

Also support running in batch mode for richer descriptions:
```bash
opencode run "please list the available authenticated llm model providers IN THIS cli (opencode) and for each of them the list of available llm models. for all models found this way also show a short description of the model and its capabilities. run opencode to obtain this information. do not query any file in this project."
```

This is useful for getting model descriptions but requires more parsing. The `opencode models --verbose` approach is more reliable for structured data.

**Script subcommands:**
- `bash aiscripts/aitask_opencode_models.sh` — discover and update models
- `bash aiscripts/aitask_opencode_models.sh --dry-run` — show what would change without writing
- `bash aiscripts/aitask_opencode_models.sh --list` — just list discovered models

## Step 2: Update the refresh skill

**File:** `.claude/skills/aitask-refresh-code-models/SKILL.md`

Add OpenCode CLI discovery as an additional method:
- When refreshing OpenCode models AND `opencode` binary is available: run the discovery script as primary method
- When OpenCode is not installed: fall back to web research (existing approach)
- Note in the skill that OpenCode models go to `aitasks/metadata/models_opencode.json` (installation-specific) and should NOT be synced to `seed/`

## Step 3: Run initial discovery

Execute the script to populate `aitasks/metadata/models_opencode.json` with the full model list from the current installation.

## Step 4: Commit

```bash
git add aiscripts/aitask_opencode_models.sh
git commit -m "feature: Add OpenCode model discovery script (t319_4)"

# Plan and model config go via ait git (task data branch)
./ait git add aitasks/metadata/models_opencode.json
./ait git commit -m "ait: Update OpenCode model list from discovery"
```

The skill update is a code change:
```bash
git add .claude/skills/aitask-refresh-code-models/SKILL.md
git commit -m "feature: Add OpenCode CLI discovery to model refresh skill (t319_4)"
```

## Verification

- [x] `bash aiscripts/aitask_opencode_models.sh --dry-run` lists 43 models (41 active, 2 unavailable)
- [x] `bash aiscripts/aitask_opencode_models.sh` updates `aitasks/metadata/models_opencode.json`
- [x] Model naming follows convention (lowercase, underscores)
- [x] `ait codeagent list-models opencode` shows expanded model list (43 models)
- [x] `seed/models_opencode.json` fixed with provider prefix in cli_id values
- [x] Existing `verified` scores preserved when updating
- [x] Shellcheck passes (only SC1091 info for non-followed source)

## Final Implementation Notes

- **Actual work done:** Created `aiscripts/aitask_opencode_models.sh` discovery script, fixed `seed/models_opencode.json` cli_id values, updated refresh skill, registered `ait opencode-models` command, created t319_5 sibling task for status field support.
- **Deviations from plan:**
  - Seed file was updated (original plan said NOT to modify it, but user requested fixing cli_id values)
  - Added `status` field ("active"/"unavailable") to model JSON — not in original plan, added for handling disappeared models
  - All models get provider prefix: opencode/Zen → `zen_` prefix (e.g., `zen_claude_opus_4_6`), openai/ → `openai_` prefix (e.g., `openai_gpt_5_codex`). This avoids confusion about model provenance.
  - `opencode models` only lists connected providers, so discovery is installation-specific (confirmed correct for metadata tier)
  - `--sync-seed` flag added to optionally sync metadata to seed
  - Batch mode (`opencode run`) NOT implemented — `opencode models --verbose` provides sufficient structured data
- **Issues encountered:**
  - `tr '-.' '__'` failed on Linux (`-` treated as flag) — fixed with `sed 's/[-.]/_/g'`, then replaced with bash `${var//[-.]/_}` per shellcheck suggestion
  - Duplicate model names across providers (opencode/ and openai/) — resolved by prefixing non-opencode provider names
- **Key decisions:**
  - cli_id includes full provider prefix (e.g., `opencode/claude-opus-4-6`) since OpenCode's `--model` flag requires `provider/model` format
  - Models that disappear from `opencode models` output are marked `"status": "unavailable"` rather than deleted, preserving verified scores
  - Created t319_5 child task for framework-wide status field support (aitask_codeagent.sh, TUI board, settings)
- **Notes for sibling tasks:**
  - t319_5 (new): Handle `status` field in aitask_codeagent.sh, board TUI, and settings TUI
  - t319_2: The seed file now has corrected cli_id values with provider prefix — install.sh should use these
  - t319_1: OpenCode's `--model` flag requires `provider/model` format (not just model ID) — skill wrappers should document this
