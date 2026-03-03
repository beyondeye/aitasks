---
title: "/aitask-refresh-code-models"
linkTitle: "/aitask-refresh-code-models"
weight: 55
description: "Research latest AI code agent models and update model configuration files"
---

Research the latest AI code agent models via web search and update the `models_*.json` configuration files used by [`ait codeagent`](../../commands/codeagent/).

**Usage:**
```
/aitask-refresh-code-models
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Step-by-Step

The skill follows an 8-step workflow:

1. **Read current configs** — Loads all `aitasks/metadata/models_*.json` files and `codeagent_config.json` to identify current models and which are in use
2. **Select agents** — Choose which agents to refresh (Claude, Gemini, Codex, OpenCode, or all)
3. **Research latest models** — Uses `WebSearch` and `WebFetch` against canonical documentation URLs to discover current model offerings
4. **Compare** — Categorizes each model as NEW, UPDATED, DEPRECATED?, or UNCHANGED by comparing web research against current config
5. **Present changes** — Displays a structured change report marking models that are in use
6. **Update JSON files** — Applies approved changes to `models_*.json` files. Syncs to `seed/` if present
7. **Verify research URLs** — Checks that the documentation URLs used for research are still reachable (informational only)
8. **Commit** — Commits updated model files via `./ait git`

## Key Behaviors

- **Never auto-removes models** — Deprecated models are flagged but only removed with explicit user approval
- **Preserves verification scores** — Existing `verified` scores are never overwritten; new models start at zero
- **Seed sync** — If the `seed/` directory exists, updated model files are copied there automatically
- **Graceful degradation** — If web research fails for a specific agent, the skill continues with remaining agents

## Model Naming Convention

Model `name` fields follow strict rules: lowercase only, underscores replace dots/hyphens, version numbers concatenated (e.g., Opus 4.6 → `opus4_6`, Gemini 2.5 Pro → `gemini2_5pro`).

## Related

- [`ait codeagent`](../../commands/codeagent/) — Uses the model files managed by this skill
- [Settings TUI](../../tuis/settings/) Models tab — Visual editor for model configurations
