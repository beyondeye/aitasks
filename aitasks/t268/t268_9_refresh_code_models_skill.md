---
priority: medium
effort: medium
depends: [t268_1]
issue_type: feature
status: Implementing
labels: [modelwrapper]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-01 11:52
updated_at: 2026-03-01 12:39
---

## Context

This is a child task of t268 (Code Agent Wrapper). It creates a Claude Code skill/command `aitask-refresh-code-models` that automates the update of `models_*.json` files in `aitasks/metadata/`. The procedure mirrors what was done manually in t268_1 (web search for latest models, update JSON files).

## Key Files

- **Create:** `.claude/skills/aitask-refresh-code-models/SKILL.md`
- **Modify:** `aitasks/metadata/models_claude.json`, `models_gemini.json`, `models_codex.json`, `models_opencode.json`
- **Modify:** `seed/models_claude.json`, `seed/models_gemini.json`, `seed/models_codex.json`, `seed/models_opencode.json`

## Model Research Sources (per agent)

The skill should search these sources for the latest available models. These URLs may change over time — the skill should include a self-update step to verify these references are still valid.

### Claude Code
- **Documentation:** https://code.claude.com/docs/en/model-config (model aliases and full names)
- **Models overview:** https://platform.claude.com/docs/en/about-claude/models/overview
- **Key info:** Uses `--model` flag. Prefer explicit versioned IDs (e.g., `claude-opus-4-6`) over aliases (`opus`) to avoid unexpected behavior on new releases.

### Gemini CLI
- **Documentation:** https://geminicli.com/docs/get-started/gemini-3/
- **Models page:** https://ai.google.dev/gemini-api/docs/models
- **GitHub discussions:** https://github.com/google-gemini/gemini-cli/discussions (announcements of new model availability)
- **Key info:** Uses `-m` flag. Model IDs may include `-preview` suffix for preview models.

### Codex CLI (OpenAI)
- **Documentation:** https://developers.openai.com/codex/models/
- **Changelog:** https://developers.openai.com/codex/changelog/
- **Key info:** Uses `-m` flag. Models are GPT-5.x-codex variants.

### OpenCode
- **Providers page:** https://opencode.ai/docs/providers/
- **GitHub:** https://github.com/anomalyco/opencode (issues/discussions for new model support)
- **Key info:** Uses `--model` flag. Provider-based model IDs (e.g., `kimi-k2.5`, `deepseek-reasoner`).

## Implementation Plan

### 1. Create skill SKILL.md

The skill should:

1. **Fetch current model info** by reading the existing `models_*.json` files from `aitasks/metadata/`
2. **Search for latest models** using `WebSearch` and `WebFetch` tools on the sources listed above for each agent
3. **Compare** current models vs. discovered models:
   - Identify new models not in the config
   - Identify deprecated/removed models
   - Identify changed CLI IDs (renamed models)
4. **Present changes** to the user via `AskUserQuestion`:
   - For each agent: show proposed additions, removals, and updates
   - Let the user confirm or modify before applying
5. **Update JSON files** in both `aitasks/metadata/` and `seed/`:
   - Add new models with `verified` scores all set to 0
   - Remove deprecated models (or mark with a `deprecated: true` field)
   - Update CLI IDs for renamed models
   - Preserve existing `verified` scores for unchanged models
6. **Self-update step**: Verify the research source URLs are still valid:
   - Fetch each URL and check for 200 response
   - If any URL fails, warn the user and suggest updating the SKILL.md with new URLs
   - If the model page structure has changed significantly (e.g., model naming conventions changed), suggest updating the skill's parsing logic

### 2. JSON schema

Each model entry:
```json
{
  "name": "opus4_6",
  "cli_id": "claude-opus-4-6",
  "notes": "Latest Opus, best for complex reasoning",
  "verified": { "task-pick": 80, "explain": 80, "batch-review": 0 }
}
```

### 3. Naming convention rules

- Model names use underscores, no dots (e.g., `opus4_6` not `opus4.6`)
- CLI IDs use the exact string expected by the CLI tool's `--model`/`-m` flag

## Verification Steps

1. Running `/aitask-refresh-code-models` opens the skill and performs web searches
2. Changes are presented for user approval before being applied
3. Both `aitasks/metadata/models_*.json` and `seed/models_*.json` are updated
4. `./ait codeagent list-models` shows the updated model list
5. Self-update check warns if any research source URL is no longer valid
