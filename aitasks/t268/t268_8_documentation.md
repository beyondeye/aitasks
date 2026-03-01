---
priority: medium
effort: low
depends: [268_5, 268_6, 268_7]
issue_type: documentation
status: Ready
labels: [modelwrapper]
created_at: 2026-03-01 09:00
updated_at: 2026-03-01 09:00
---

## Context

This is child task 8 of t268 (Code Agent Wrapper). It documents all the new infrastructure created in the previous child tasks: the agent string format, configuration hierarchy, CLI commands, per-project vs per-user config, adding new agents/models, and the Settings TUI.

## Key Files

- **Create:** `aidocs/codeagent.md`
- **Possibly modify:** `website/` content pages (if applicable)

## Implementation Plan

### 1. Create `aidocs/codeagent.md`

Document:
- **Agent string format:** `<code_agent>/<model>` convention, naming rules (underscores, no dots)
- **Supported code agents:** claude, gemini, codex, opencode — with CLI binary mapping
- **Model naming convention:** How model names map to CLI model IDs
- **`ait codeagent` CLI commands:** list-agents, list-models, resolve, check, invoke (with examples)
- **Configuration hierarchy:** project config → user config → default (resolution chain)
- **Per-project vs per-user config:** Explain the `_config.json` / `_config.local.json` split pattern
- **How to add new code agents/models:** Edit model config files in `aitasks/metadata/`
- **Settings TUI:** How to use `ait settings` to manage all configuration
- **`implemented_with` metadata:** What it tracks, how it's populated
- **Verification scores:** What they mean, how they're used

### 2. Update website docs (if applicable)

- Add codeagent configuration page under relevant section
- Cross-reference from board and codebrowser documentation

## Verification Steps

1. `aidocs/codeagent.md` exists and covers all topics listed above
2. Documentation is accurate against actual implementation
3. Examples in documentation work when executed
4. Website builds without errors if website pages were modified
