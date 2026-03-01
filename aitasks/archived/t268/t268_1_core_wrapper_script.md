---
priority: high
effort: high
depends: []
issue_type: feature
status: Done
labels: [modelwrapper]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-01 09:00
updated_at: 2026-03-01 12:10
completed_at: 2026-03-01 12:10
---

## Context

This is child task 1 of t268 (Code Agent Wrapper). It creates the core wrapper script `aitask_codeagent.sh` that encapsulates code agent and model knowledge, providing a unified interface for all TUIs and scripts to invoke different AI code agents (Claude Code, Gemini CLI, Codex CLI, OpenCode) with model selection support.

## Unified Agent String Format

`<code_agent>/<model>` — the first part selects which code agent CLI to run, the second part selects one of the models supported by that specific code agent.

Examples:
- `claude/sonnet4_6` — Claude Code with Sonnet 4.6
- `claude/opus4_6` — Claude Code with Opus 4.6
- `gemini/gemini3pro` — Gemini CLI with Gemini 3 Pro
- `codex/o3` — Codex CLI with o3
- `opencode/kimi2_5` — OpenCode with Kimi 2.5

**Naming convention:** underscores separate version components (e.g., `sonnet4_6` not `sonnet-4-6`). No dots in model names.

## Key Files

- **Create:** `aiscripts/aitask_codeagent.sh`
- **Modify:** `ait` (add `codeagent` dispatcher entry)
- **Create:** `aitasks/metadata/models_claude.json`, `models_gemini.json`, `models_codex.json`, `models_opencode.json`
- **Create:** `tests/test_codeagent.sh`

## Implementation Plan

### 1. Create per-agent model config files (JSON) in `aitasks/metadata/`

Each file lists models for a specific code agent with their CLI model ID and per-operation verification scores (0-100). Score 0 = untested, 100 = fully verified.

`models_claude.json`:
```json
{
  "models": [
    {
      "name": "sonnet4_6",
      "cli_id": "sonnet-4-6",
      "verified": { "task-pick": 80, "explain": 80, "batch-review": 0 }
    },
    {
      "name": "opus4_6",
      "cli_id": "claude-opus-4-6",
      "verified": { "task-pick": 80, "explain": 80, "batch-review": 0 }
    },
    {
      "name": "haiku4_5",
      "cli_id": "claude-haiku-4-5-20251001",
      "verified": { "task-pick": 0, "explain": 0, "batch-review": 0 }
    }
  ]
}
```

Similar files for `models_gemini.json`, `models_codex.json`, `models_opencode.json` (see plan for details).

### 2. Create `aiscripts/aitask_codeagent.sh`

**Code agent → CLI binary mapping (embedded in script via `case`):**
- `claude` → `claude`
- `gemini` → `gemini`
- `codex` → `codex`
- `opencode` → `opencode`

**CLI interface:**
- `list-agents` — list supported code agents
- `list-models [AGENT]` — list models for an agent (with verification scores)
- `resolve <operation>` — return configured agent string for an operation
- `check <agent-string>` — validate agent string and check CLI availability
- `invoke <operation> [args...]` — invoke the code agent for an operation
- `--agent-string STR` — override flag
- `--dry-run` — print command without executing

**Resolution chain (highest priority first):**
1. Explicit `--agent-string` flag
2. Per-user config: `aitasks/metadata/codeagent_config.local.json` (gitignored)
3. Per-project config: `aitasks/metadata/codeagent_config.json` (git-tracked)
4. Hardcoded default: `claude/sonnet4_6`

**Model file reading:** Use `jq` (with `python3 -c "import json"` fallback) to parse JSON model files.

**Operation-aware invocation:**
- `task-pick` — interactive skill invocation (e.g., `claude /aitask-pick 42`)
- `explain` — interactive skill invocation (e.g., `claude /aitask-explain dir`)
- `batch-review` — batch/non-interactive mode (future)
- `raw` — pass-through with model flag

### 3. Add `codeagent` to `ait` dispatcher

Add entry in the `case` statement: `codeagent) shift; exec "$SCRIPTS_DIR/aitask_codeagent.sh" "$@" ;;`

Update `show_usage()` with codeagent command.

### 4. Create tests

`tests/test_codeagent.sh` — test list-agents, list-models, resolve, check, dry-run invoke.

## Verification Steps

1. `./ait codeagent list-agents` — shows claude, gemini, codex, opencode
2. `./ait codeagent list-models claude` — shows sonnet4_6, opus4_6, haiku4_5 with scores
3. `./ait codeagent resolve task-pick` — returns configured agent string
4. `./ait codeagent check "claude/sonnet4_6"` — validates and checks CLI availability
5. `./ait codeagent --dry-run invoke task-pick 42` — prints command without executing
6. `bash tests/test_codeagent.sh` passes
7. `shellcheck aiscripts/aitask_codeagent.sh` passes
