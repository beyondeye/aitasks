---
priority: high
effort: medium
depends: [t268_1]
issue_type: feature
status: Done
labels: [modelwrapper]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-01 09:00
updated_at: 2026-03-01 12:35
completed_at: 2026-03-01 12:35
---

## Context

This is child task 2 of t268 (Code Agent Wrapper). It creates the configuration infrastructure: seed files for model configs, the codeagent_config.json defaults file, and updates `aitask_setup.sh` to deploy these during project setup. Also updates gitignore for `.local.json` per-user config files.

## Config Split Pattern

- `<tool>_config.json` → per-project (git-tracked)
- `<tool>_config.local.json` → per-user (gitignored)
- Applied to: `codeagent_config`, `board_config`, `codebrowser_config`

## Key Files

- **Create:** `seed/models_claude.json`, `seed/models_gemini.json`, `seed/models_codex.json`, `seed/models_opencode.json`
- **Create:** `seed/codeagent_config.json`
- **Modify:** `aiscripts/aitask_setup.sh` (copy seed configs during `setup_data_branch()`, update gitignore for `*.local.json`)

## Implementation Plan

### 1. Create seed model config files

Copy the model JSON files created in t268_1 into `seed/` as templates for new project setup. Before creating, research latest available models for each code agent to ensure seed files are up-to-date.

### 2. Create `seed/codeagent_config.json`

Operation defaults config:
```json
{
  "default_agent": "claude/sonnet4_6",
  "operations": {
    "task-pick": "claude/opus4_6",
    "explain": "claude/sonnet4_6",
    "batch-review": "claude/sonnet4_6"
  }
}
```

Per-user `.local.json` uses same schema, sparse (only overrides).

### 3. Update `aitask_setup.sh`

- In `setup_data_branch()`: copy all seed model config files and `codeagent_config.json` to `aitasks/metadata/`
- Update the data branch `.gitignore` to include `*.local.json` pattern in metadata directory

### 4. Verify model config files are independent from operation defaults

Model config files list what's available (with verification scores). `codeagent_config.json` configures which agent/model to use for each operation. These are independent concerns.

## Verification Steps

1. `seed/` contains all model config JSON files and `codeagent_config.json`
2. Running `ait setup` on a fresh project copies all seed configs to `aitasks/metadata/`
3. `aitasks/metadata/*.local.json` files are gitignored on the data branch
4. `codeagent_config.json` schema is valid and parseable by `aitask_codeagent.sh`
