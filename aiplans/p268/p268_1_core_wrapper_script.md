---
Task: t268_1_core_wrapper_script.md
Parent Task: aitasks/t268_wrapper_for_claude_code.md
Sibling Tasks: aitasks/t268/t268_2_config_infrastructure.md, aitasks/t268/t268_3_common_config_library.md, aitasks/t268/t268_4_board_config_split.md, aitasks/t268/t268_5_tui_integration.md
Archived Sibling Plans: (none yet)
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

The aitasks TUIs (board, codebrowser) currently hardcode `claude` as the AI agent CLI. This prevents switching to alternative agents (Gemini CLI, Codex CLI, OpenCode) and doesn't support model selection. This task creates the foundational wrapper script `aitask_codeagent.sh` that provides a unified interface for invoking any supported code agent with any supported model, using the `<agent>/<model>` string format.

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `aiscripts/aitask_codeagent.sh` |
| Create | `aitasks/metadata/models_claude.json` |
| Create | `aitasks/metadata/models_gemini.json` |
| Create | `aitasks/metadata/models_codex.json` |
| Create | `aitasks/metadata/models_opencode.json` |
| Create | `aitasks/metadata/codeagent_config.json` |
| Modify | `ait` (dispatcher + help + update-check skip) |
| Create | `tests/test_codeagent.sh` |

## Implementation Steps

### Step 1: Create model config JSON files in `aitasks/metadata/`

Each file defines models for one agent with `name` (internal, underscored, no dots), `cli_id` (exact string passed to CLI `--model` flag), `notes` (human-readable description), and `verified` scores per operation (0-100).

JSON schema per model entry:
```json
{
  "name": "opus4_6",
  "cli_id": "claude-opus-4-6",
  "notes": "Latest Opus, best for complex reasoning",
  "verified": { "task-pick": 80, "explain": 80, "batch-review": 0 }
}
```

**`models_claude.json`** — Based on [Claude Code model docs](https://code.claude.com/docs/en/model-config). Uses `--model` flag with explicit versioned IDs (not aliases, to avoid unexpected behavior on new releases).
| name | cli_id | notes |
|------|--------|-------|
| opus4_6 | claude-opus-4-6 | Latest Opus |
| sonnet4_6 | claude-sonnet-4-6 | Latest Sonnet |
| haiku4_5 | claude-haiku-4-5-20251001 | Fast, efficient |
| opus4_5 | claude-opus-4-5 | Previous gen |
| sonnet4_5 | claude-sonnet-4-5 | Previous gen |

**`models_gemini.json`** — Based on [Gemini CLI docs](https://geminicli.com/docs/get-started/gemini-3/). Uses `-m` flag.
| name | cli_id | notes |
|------|--------|-------|
| gemini3_1pro | gemini-3.1-pro-preview | Latest, advanced reasoning |
| gemini3pro | gemini-3-pro | Strong reasoning |
| gemini3flash | gemini-3-flash-preview | Latest flash, fast |
| gemini2_5pro | gemini-2.5-pro | Stable, complex tasks |
| gemini2_5flash | gemini-2.5-flash | Stable, budget-friendly |

**`models_codex.json`** — Based on [Codex CLI docs](https://developers.openai.com/codex/models/). Uses `-m` flag.
| name | cli_id | notes |
|------|--------|-------|
| gpt5_3codex | gpt-5.3-codex | Most capable agentic model |
| gpt5_3codex_spark | gpt-5.3-codex-spark | Ultra-fast, research preview |
| gpt5_2codex | gpt-5.2-codex | Advanced coding |
| gpt5_1codex_max | gpt-5.1-codex-max | Long-horizon tasks |

**`models_opencode.json`** — Based on [OpenCode provider docs](https://opencode.ai/docs/providers/). Uses `--model` flag with provider-specific IDs.
| name | cli_id | notes |
|------|--------|-------|
| kimi_k2_5 | kimi-k2.5 | Moonshot AI, strong coding |
| sonnet4_6 | sonnet-4-6 | Via Anthropic provider |
| deepseek_reasoner | deepseek-reasoner | Via DeepSeek provider |

### Step 2: Create `aitasks/metadata/codeagent_config.json`

Per-project defaults mapping operations to agent strings:
```json
{
  "defaults": {
    "task-pick": "claude/opus4_6",
    "explain": "claude/sonnet4_6",
    "batch-review": "claude/sonnet4_6",
    "raw": "claude/sonnet4_6"
  }
}
```

Note: `task-pick` defaults to `opus4_6` per user preference (complex reasoning task). Other operations default to `sonnet4_6` (efficient for execution).

### Step 3: Create `aiscripts/aitask_codeagent.sh`

Core wrapper script (~350 LOC). Structure:

1. **Header**: shebang, `set -euo pipefail`, source `terminal_compat.sh` + `task_utils.sh`
2. **Constants**: `METADATA_DIR`, `DEFAULT_AGENT_STRING="claude/opus4_6"`, `SUPPORTED_AGENTS`, `SUPPORTED_OPERATIONS`
3. **Utility functions**:
   - `require_jq()` — die if jq not available (pattern from `aitask_issue_import.sh:77`)
   - `parse_agent_string(str)` — validate `^[a-z]+/[a-z0-9_]+$`, set `PARSED_AGENT`/`PARSED_MODEL`
   - `get_cli_binary(agent)` — case mapping (claude→claude, gemini→gemini, etc.)
   - `get_cli_model_id(agent, model)` — jq query on `models_<agent>.json`
   - `resolve_agent_string(operation)` — 4-level resolution chain: flag → local config → project config → hardcoded default
4. **Subcommands**:
   - `cmd_list_agents` — list all agents with CLI availability status
   - `cmd_list_models [agent]` — list models with verification scores
   - `cmd_resolve <operation>` — output resolved agent string + components
   - `cmd_check <agent-string>` — validate and check CLI binary in PATH
   - `cmd_invoke <operation> [args...]` — build and execute agent-specific command
5. **Invocation building** (`build_invoke_command`): Agent-specific command construction. Each CLI has slightly different flag syntax:
   - **claude**: `claude --model <cli_id> "/aitask-pick <args>"` — uses `--model`, skill as single argument (matching existing board pattern at `aitask_board.py:2750`)
   - **gemini**: `gemini -m <cli_id> "/aitask-pick <args>"` — uses `-m` short flag
   - **codex**: `codex -m <cli_id> <args>` — uses `-m` short flag
   - **opencode**: `opencode --model <cli_id> <args>` — uses `--model`
   - For `raw` operation: pass-through with model flag only
   - Each agent maps `get_model_flag()` to return the right flag (`--model` vs `-m`)
6. **Main**: parse global flags (`--agent-string`, `--dry-run`, `--help`), dispatch subcommand

**Key design decisions**:
- `jq` required (no python fallback) — consistent with existing codebase
- Purely non-interactive — utility/plumbing script, no fzf needed
- `exec` on invoke (replaces shell process, like `ait` dispatcher pattern)
- Structured `FIELD:value` output for machine-parseable commands (list-agents, list-models, resolve)
- `DRY_RUN:` prefix output for `--dry-run invoke`

### Step 4: Modify `ait` dispatcher

Three changes to `/home/ddt/Work/aitasks/ait`:
1. Add dispatch entry (line ~134, before `help`): `codeagent) shift; exec "$SCRIPTS_DIR/aitask_codeagent.sh" "$@" ;;`
2. Add to `show_usage()` under "Tools:": `  codeagent      Manage code agent and model configuration`
3. Add to update-check skip list (line 113): append `|codeagent`

### Step 5: Create `tests/test_codeagent.sh`

Follow pattern from `tests/test_claim_id.sh`: assert helpers, temp dir with copied scripts + configs, PASS/FAIL counters.

Test cases:
1. Syntax check (`bash -n`)
2. `list-agents` outputs all 4 agents
3. `list-models claude` shows sonnet4_6, opus4_6, haiku4_5
4. `list-models` with invalid agent → exit nonzero
5. `resolve task-pick` returns `claude/opus4_6` (from project config)
6. `resolve` with `--agent-string` override takes priority
7. `resolve` with local config overrides project config
8. `check claude/sonnet4_6` — valid (exit zero if claude in PATH, structured error if not)
9. `check` with invalid format → exit nonzero
10. `check` with unknown model → exit nonzero
11. `--dry-run invoke task-pick 42` → output contains `DRY_RUN:` and `claude`
12. `--help` shows usage text

### Step 6: Run verification

1. `shellcheck aiscripts/aitask_codeagent.sh`
2. `./ait codeagent list-agents`
3. `./ait codeagent list-models claude`
4. `./ait codeagent resolve task-pick`
5. `./ait codeagent check "claude/sonnet4_6"`
6. `./ait codeagent --dry-run invoke task-pick 42`
7. `bash tests/test_codeagent.sh`

### Step 7: Post-Implementation (Step 9 from task-workflow)

Archive task, commit, push per shared workflow.

## Final Implementation Notes

- **Actual work done:** Created `aitask_codeagent.sh` (290 LOC) with all 5 subcommands (list-agents, list-models, resolve, check, invoke). Created 4 model config JSONs with real 2026 model IDs researched via web search. Created per-project defaults config. Updated `ait` dispatcher. Created comprehensive test suite (36 tests). Additionally added seed files and install/setup functions (originally t268_2 scope but done here for completeness).
- **Deviations from plan:** Added seed files + `install.sh` functions + `aitask_setup.sh` data branch init updates, which were originally scoped for t268_2. Created new sibling task t268_9 for automated model refresh skill.
- **Issues encountered:** None significant. SC1091 shellcheck info-level warnings for sourced files (expected, same as all other scripts).
- **Key decisions:**
  - Used explicit versioned CLI model IDs (e.g., `claude-opus-4-6`) instead of aliases (`opus`) to avoid unexpected behavior when new versions release
  - Default for `task-pick` is `opus4_6` (per user preference for complex reasoning), other operations default to `sonnet4_6`
  - Each agent has its own model flag mapping (`--model` for claude/opencode, `-m` for gemini/codex)
  - jq is a hard requirement (no python fallback), consistent with existing codebase pattern
- **Notes for sibling tasks:**
  - t268_2 should still handle: adding `*.local.json` to data branch gitignore, any remaining seed infrastructure
  - t268_5 (TUI integration) should use `./ait codeagent --dry-run invoke <op> <args>` to get the command, or `./ait codeagent resolve <op>` to get the agent/model/binary info
  - The `build_invoke_command` function constructs skill invocation as a single argument string (e.g., `"/aitask-pick 42"`) matching the existing board/codebrowser pattern
  - New sibling t268_9 created for automated model config refresh skill
