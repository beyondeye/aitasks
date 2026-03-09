---
title: "Code Agent"
linkTitle: "Code Agent"
weight: 45
description: "ait codeagent command for multi-agent model selection and invocation"
---

## ait codeagent

Unified wrapper for invoking AI code agents (Claude Code, Gemini CLI, Codex CLI, OpenCode) with configurable per-operation model selection.

```bash
ait codeagent list-agents                              # Show available agents
ait codeagent list-models claudecode                   # List Claude models
ait codeagent resolve task-pick                        # Show configured agent/model
ait codeagent check "claudecode/opus4_6"               # Validate an agent string
ait codeagent coauthor "codex/gpt5_4"                  # Resolve commit coauthor metadata
ait codeagent invoke task-pick 42                      # Pick task 42 with configured agent
ait codeagent --agent-string geminicli/gemini2_5pro invoke explain src/  # Override agent
ait codeagent --dry-run invoke task-pick 42            # Preview command without running
```

### Agent String Format

An agent string identifies both the code agent and the model to use, in the format `<agent>/<model>`:

```
claudecode/opus4_6
geminicli/gemini2_5pro
codex/gpt5_3codex
opencode/kimi_k2_5
```

**Naming rules:**
- Agent names use lowercase letters only: `claudecode`, `geminicli`, `codex`, `opencode`
- Model names use lowercase letters, digits, and underscores: `opus4_6`, `gemini3pro`, `gpt5_3codex_spark`
- No dots, hyphens, or uppercase characters in agent strings

### Supported Agents

| Agent | CLI Binary | Model Flag | Notes |
|-------|-----------|------------|-------|
| `claudecode` | `claude` | `--model` | Claude Code CLI |
| `geminicli` | `gemini` | `-m` | Gemini CLI |
| `codex` | `codex` | `-m` | Codex CLI |
| `opencode` | `opencode` | `--model` | OpenCode CLI |

### Operations

Each operation maps to a different use case with its own default model:

| Operation | Description | Default |
|-----------|-------------|---------|
| `task-pick` | Picking and implementing tasks | `claudecode/opus4_6` |
| `explain` | Explaining or documenting code | `claudecode/sonnet4_6` |
| `batch-review` | Batch code review | `claudecode/sonnet4_6` |
| `raw` | Direct/ad-hoc invocations (passthrough) | `claudecode/sonnet4_6` |

### Subcommands

#### list-agents

Lists all supported agents and whether their CLI binary is available in PATH.

```bash
ait codeagent list-agents
```

Output format:
```
AGENT:claudecode BINARY:claude STATUS:available
AGENT:geminicli BINARY:gemini STATUS:not-found
AGENT:codex BINARY:codex STATUS:not-found
AGENT:opencode BINARY:opencode STATUS:not-found
```

#### list-models

Lists available models for one or all agents, with verification scores.

```bash
ait codeagent list-models              # All agents
ait codeagent list-models claudecode   # Claude models only
```

Output format:
```
=== claudecode ===
MODEL:opus4_6 CLI_ID:claude-opus-4-6 NOTES:Most intelligent model VERIFIED:task-pick=80,explain=80,batch-review=0

=== geminicli ===
MODEL:gemini2_5pro CLI_ID:gemini-2.5-pro NOTES:Stable, best for complex tasks VERIFIED:task-pick=0,explain=0,batch-review=0
```

#### resolve

Returns the configured agent string for an operation after applying the full resolution chain.

```bash
ait codeagent resolve task-pick
```

Output:
```
AGENT_STRING:claudecode/opus4_6
AGENT:claudecode
MODEL:opus4_6
CLI_ID:claude-opus-4-6
BINARY:claude
MODEL_FLAG:--model
```

#### check

Validates an agent string and verifies the CLI binary is available.

```bash
ait codeagent check "claudecode/opus4_6"
# OK: claudecode/opus4_6 -> claude --model claude-opus-4-6 (binary found)
```

#### coauthor

Returns the commit coauthor metadata for an agent string.

```bash
ait codeagent coauthor "codex/gpt5_4"
```

Output:
```text
AGENT_STRING:codex/gpt5_4
AGENT_COAUTHOR_NAME:Codex/GPT5.4
AGENT_COAUTHOR_EMAIL:codex@aitasks.io
AGENT_COAUTHOR_TRAILER:Co-Authored-By: Codex/GPT5.4 <codex@aitasks.io>
```

The task workflow uses this subcommand during commit creation. It combines:

- the task's `implemented_with` value
- the model metadata in `aitasks/metadata/models_<agent>.json`
- the project-level `codeagent_coauthor_domain` setting from `aitasks/metadata/project_config.yaml`

If the resolver fails, the workflow skips only the code-agent trailer and keeps any normal or imported-contributor attribution.

#### invoke

Invokes the code agent for an operation. The wrapper resolves the agent/model, builds the command, exports `AITASK_AGENT_STRING` for tracking, and `exec`s the agent CLI.

```bash
ait codeagent invoke task-pick 42          # Pick task 42
ait codeagent invoke explain src/main.py   # Explain a file
```

| Option | Description |
|--------|-------------|
| `--agent-string STR` | Override agent string for this invocation |
| `--dry-run` | Print the command that would be executed without running it |

### Configuration

The agent/model for each operation is resolved through a 4-level chain (highest priority first):

1. **`--agent-string` flag** -- CLI override for a single invocation
2. **Per-user config** -- `aitasks/metadata/codeagent_config.local.json` (gitignored)
3. **Per-project config** -- `aitasks/metadata/codeagent_config.json` (git-tracked)
4. **Hardcoded default** -- `claudecode/opus4_6`

#### Project config (`codeagent_config.json`)

Shared across the team, checked into git. Sets the default agent/model for each operation:

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

#### User config (`codeagent_config.local.json`)

Per-user overrides, gitignored. Same schema as the project config. Only include operations you want to override:

```json
{
  "defaults": {
    "task-pick": "geminicli/gemini2_5pro"
  }
}
```

This user would use Gemini for task-pick but inherit the project defaults for all other operations.

Both config files can be edited directly or through the [Settings TUI](../../tuis/settings/).

### Model Configuration

Models are defined in JSON files at `aitasks/metadata/models_<agent>.json`. Each file contains an array of model entries:

```json
{
  "models": [
    {
      "name": "opus4_6",
      "cli_id": "claude-opus-4-6",
      "notes": "Most intelligent model for agents and coding",
      "verified": {
        "task-pick": 80,
        "explain": 80,
        "batch-review": 0
      }
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `name` | Internal identifier used in agent strings (underscored, no dots) |
| `cli_id` | Exact model ID passed to the CLI binary's model flag |
| `notes` | Human-readable description |
| `verified` | Per-operation verification scores (0-100) |

#### Verification Scores

Scores indicate how well a model has been tested for each operation:

- **0** -- Not verified (untested or unknown quality)
- **1-49** -- Partially verified (works but with known issues)
- **50-79** -- Verified (works well for most cases)
- **80-100** -- Highly verified (extensively tested, recommended)

Scores are displayed in the [Settings TUI](../../tuis/settings/) Models tab and help when choosing which model to assign to an operation.

#### Updating Models

To add new models, update notes, or check for deprecated entries, use the [`/aitask-refresh-code-models`](../../skills/aitask-refresh-code-models/) skill. It researches the latest models from each provider's documentation and updates the JSON files with user approval. Verification scores can also be edited through the [Settings TUI](../../tuis/settings/) Models tab or by editing the JSON files directly.

### `implemented_with` Metadata

When a task is implemented, the agent string is recorded in the task's YAML frontmatter:

```yaml
implemented_with: claudecode/opus4_6
```

This enables tracking which agent/model performed each task's implementation for quality analysis.

It also feeds `ait codeagent coauthor`, which the task workflow uses to build resolver-based `Co-Authored-By` trailers for commits.

**How it's populated:**

1. When `ait codeagent invoke` runs, it exports the `AITASK_AGENT_STRING` environment variable before launching the agent
2. The `/aitask-pick` skill reads this env var during task claim and writes it to the frontmatter
3. If the env var is not set (agent was launched directly, not through the wrapper), the skill self-detects: it identifies its own agent CLI and model, looks up the model in the config file, and constructs the agent string

### TUI Integration

The code agent wrapper is integrated into both TUI applications:

- **Board TUI** (`ait board`) -- When you pick a task from the board (press **Enter** on a task card, then select "Pick"), the board invokes `ait codeagent invoke task-pick <task_num>` instead of hardcoding a specific agent. This means the board respects your configured agent/model for the `task-pick` operation.

- **Code Browser** (`ait codebrowser`) -- When you launch the explain action on a file, the code browser resolves the `explain` operation through the wrapper to determine which agent binary to use. It performs a pre-flight check to verify the binary is in PATH and shows a user-friendly error if not found.

- **Settings TUI** (`ait settings`) -- The Code Agent tab provides a visual editor for operation-to-agent bindings. You can change which agent and model is assigned to each operation (`task-pick`, `explain`, `batch-review`, `raw`) without editing JSON files directly.

Both TUIs delegate all agent resolution to the centralized configuration -- there is no TUI-specific agent config.

## Related

- [`/aitask-refresh-code-models`]({{< relref "/docs/skills/aitask-refresh-code-models" >}}) — Research and update model configuration files
- [Settings TUI]({{< relref "/docs/tuis/settings" >}}) — Visual editor for code agent defaults (Agent Defaults tab) and model definitions (Models tab)
- [Board TUI — How to Pick a Task]({{< relref "/docs/tuis/board/how-to#how-to-pick-a-task-for-implementation" >}}) — Uses the `task-pick` operation to launch the configured agent
- [Code Browser]({{< relref "/docs/tuis/codebrowser" >}}) — Uses the `explain` operation for launching explain sessions
