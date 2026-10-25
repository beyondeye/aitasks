---
title: "Code Agent"
linkTitle: "Code Agent"
weight: 45
description: "ait codeagent command for multi-agent model selection and invocation"
depth: [intermediate]
---

## ait codeagent

Unified wrapper for invoking AI code agents (Claude Code and other supported coding agents) with configurable per-operation model selection.

```bash
ait codeagent list-agents                              # Show available agents
ait codeagent list-models claudecode                   # List Claude models
ait codeagent resolve task-pick                        # Show configured agent/model
ait codeagent check "claudecode/opus4_6"               # Validate an agent string
ait codeagent coauthor "codex/gpt5_4"                  # Resolve commit coauthor metadata
ait codeagent invoke task-pick 42                      # Pick task 42 with configured agent
ait codeagent --agent-string codex/gpt5_4 invoke explain src/  # Override agent
ait codeagent --dry-run invoke task-pick 42            # Preview command without running
```

### Agent String Format

An agent string identifies both the code agent and the model to use, in the format `<agent>/<model>`:

```
claudecode/opus4_6
codex/gpt5_3codex
opencode/kimi_k2_5
```

**Naming rules:**
- Agent names use lowercase letters only: `claudecode`, `codex`, `opencode`
- Model names use lowercase letters, digits, and underscores: `opus4_6`, `gpt5_3codex_spark`, `kimi_k2_5`
- No dots, hyphens, or uppercase characters in agent strings

### Supported Agents

| Agent | CLI Binary | Model Flag | Notes |
|-------|-----------|------------|-------|
| `claudecode` | `claude` | `--model` | Claude Code CLI |
| `codex` | `codex` | `-m` | Codex CLI |
| `opencode` | `opencode` | `--model` | OpenCode CLI |

### Operations

Each operation maps to a different use case with its own default model:

| Operation | Description | Default |
|-----------|-------------|---------|
| `pick` | Picking and implementing tasks | `claudecode/opus5_5` |
| `explain` | Explaining or documenting code | `claudecode/sonnet5_5` |
| `explore` | Exploring the codebase | `claudecode/opus5_5` |
| `explore-relay` | Chat-relayed exploration for bug-report intake (Claude Code only) | `claudecode/opus5_5` |
| `work-report` | Drafting a manager-facing work report from board columns | `claudecode/sonnet5_5` |
| `trail` | Creating, refreshing, and showing implementation trails | `claudecode/opus5_5` |
| `batch-review` | Batch code review | `claudecode/sonnet5_5` |
| `qa` | Test coverage analysis | `claudecode/sonnet5_5` |
| `shadow` | Advisory companion agent for a followed session | `codex/gpt6_1_sol` |
| `discuss` | Advisory discussion of brainstorm proposals (compare, explain, question, risk-check) | `codex/gpt6_1_sol` |
| `learn` | Learning a new skill from source material | `claudecode/opus5_5` |
| `raw` | Direct/ad-hoc invocations (passthrough) | `claudecode/sonnet5_5` |

### Subcommands

#### list-agents

Lists all supported agents and whether their CLI binary is available in PATH.

```bash
ait codeagent list-agents
```

Output format:
```
AGENT:claudecode BINARY:claude STATUS:available
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

=== codex ===
MODEL:gpt5_4 CLI_ID:gpt-5.4 NOTES:Best Codex model for complex tasks VERIFIED:task-pick=0,explain=0,batch-review=0
```

#### resolve

Returns the configured agent string for an operation after applying the full resolution chain.

```bash
ait codeagent resolve pick
```

Output:
```
AGENT_STRING:claudecode/opus5_5
AGENT:claudecode
MODEL:opus5_5
CLI_ID:claude-opus-5-5
BINARY:claude
MODEL_FLAG:--model
```

#### check

Validates an agent string and verifies the CLI binary is available.

```bash
ait codeagent check "claudecode/opus4_6"
# OK: claudecode/opus4_6 -> claude --model claude-opus-4-6 (binary found)
```

#### check-superseded

Lists the operations whose configured model the framework has superseded and, on a terminal, offers to switch them — one question per superseded model per config layer. `--report` only lists them. See [Superseded model defaults](#superseded-model-defaults).

```bash
ait codeagent check-superseded            # asks on a terminal, lists otherwise
ait codeagent check-superseded --report   # list only
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

When the resolved agent is Codex CLI, every skill is launched directly in Codex's default mode, with the skill prompt passed as the initial CLI prompt. Interactive workflow checkpoints work there because `request_user_input` is available via the `default_mode_request_user_input` feature that `ait setup` enables. Direct `raw` and `batch-review` invocations remain passthrough.

| Option | Description |
|--------|-------------|
| `--agent-string STR` | Override agent string for this invocation |
| `--dry-run` | Print the command that would be executed without running it |
| `--headless` | Run `claudecode batch-review` non-interactively (adds `--print`). No-op for other agents/operations. Defaults to interactive mode, since Claude Code bills headless print mode at a higher per-token rate. |

### Configuration

The agent/model for each operation is resolved through a 4-level chain (highest priority first):

1. **`--agent-string` flag** -- CLI override for a single invocation
2. **Per-user config** -- `aitasks/metadata/codeagent_config.local.json` (gitignored)
3. **Per-project config** -- `aitasks/metadata/codeagent_config.json` (git-tracked)
4. **Hardcoded default** -- `claudecode/opus5_5`

#### Project config (`codeagent_config.json`)

Shared across the team, checked into git. Sets the default agent/model for each operation:

```json
{
  "defaults": {
    "pick": "claudecode/opus5_5",
    "explain": "claudecode/sonnet5_5",
    "batch-review": "claudecode/sonnet5_5",
    "raw": "claudecode/sonnet5_5"
  }
}
```

#### User config (`codeagent_config.local.json`)

Per-user overrides, gitignored. Same schema as the project config. Only include operations you want to override:

```json
{
  "defaults": {
    "pick": "codex/gpt5_4"
  }
}
```

This user would use Codex for pick but inherit the project defaults for all other operations.

Both config files can be edited directly or through the [Settings TUI](../../tuis/settings/).

#### Superseded model defaults

`ait upgrade` adds new operation keys to `codeagent_config.json` but never changes a value you already have, so a project keeps the model it was installed with. The framework records which model a newer one supersedes in `.aitask-scripts/lib/model_supersessions.json` (framework-owned, replaced on every upgrade): when it promotes a new default, and when it registers the successor of a model that was never a default (for example `claudecode/haiku4_5` → `claudecode/haiku5_5`). Supersessions chain: a project still on `claudecode/opus4_8` is offered the newest model in the chain that is registered in its `models_claudecode.json`. Supersessions are recorded for `claudecode`, `codex` and `opencode` models. An OpenCode lineage stays within one provider and model line (for example `opencode/opencode_claude_opus_4_8` → `opencode/opencode_claude_opus_5_5`), and a model a provider no longer serves is still offered its successor.

At the end of an upgrade, `ait upgrade` checks every key under `defaults` in both config layers:

- An operation whose model is superseded is grouped with the other operations of the same layer that use that model, and you get one question per group: `Your project defaults for pick, explore use claudecode/opus5, which is superseded by claudecode/opus5_5. Switch? [Y/n]`.
- Operations set to a model nothing supersedes are never offered a switch. This holds for framework defaults and custom choices alike; a custom choice whose model has a recorded successor is offered it like any other.
- The project layer and the per-user layer are asked separately. An accepted project-layer switch is committed (`ait: Update codeagent_config.json`) when the file had no other uncommitted changes; otherwise it is written and left for you to review and commit. The per-user layer is never committed.
- Answering `n` is remembered for this clone, in the repository's git directory, and that model is not offered again until a different successor is available.
- Without a terminal (for example a `curl | bash` upgrade), nothing is changed: the offers are listed together with the command to review them.

Only the person running the upgrade sees these questions, so other users' `codeagent_config.local.json` overrides are checked when each of them runs `ait codeagent check-superseded`.

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

- **Board TUI — work reports** -- Pressing **W** on the board resolves the `work-report` operation through the wrapper and launches `/aitask-work-report` with the columns and tasks you reviewed. See [Board TUI — How to Generate a Work Report]({{< relref "/docs/tuis/board/how-to#how-to-generate-a-work-report" >}}).

- **Code Browser** (`ait codebrowser`) -- When you launch the explain action on a file, the code browser resolves the `explain` operation through the wrapper to determine which agent binary to use. It performs a pre-flight check to verify the binary is in PATH and shows a user-friendly error if not found.

- **Settings TUI** (`ait settings`) -- The Code Agent tab provides a visual editor for operation-to-agent bindings. You can change which agent and model is assigned to each operation (`task-pick`, `explain`, `batch-review`, `raw`) without editing JSON files directly.

Both TUIs delegate all agent resolution to the centralized configuration -- there is no TUI-specific agent config.

### Troubleshooting

**An agent pane opens but stays blank.** On a host that manages the agent CLI with [mise](https://mise.jdx.dev/), check for a wrapper script in `~/.local/bin` named after the agent that runs `mise x <agent> -- <agent>`. Without mise's shell activation, that command looks the agent up through PATH again. When `~/.local/bin` comes before mise's shims directory, the lookup finds the wrapper itself, which re-executes forever and draws nothing.

Panes the framework opens, and `ait codeagent invoke`, reorder PATH so mise's shims and install directories come before everything except the framework's own `bin` directories. A pane you open yourself keeps whatever PATH its tmux client had. If you hit the loop when launching by hand, put `~/.local/share/mise/shims` ahead of `~/.local/bin` in your PATH, or change the wrapper to run `exec "$(mise which <agent>)" "$@"`, which does not look the agent up again.

## Related

- [`/aitask-refresh-code-models`]({{< relref "/docs/skills/aitask-refresh-code-models" >}}) — Research and update model configuration files
- [Settings TUI]({{< relref "/docs/tuis/settings" >}}) — Visual editor for code agent defaults (Agent Defaults tab) and model definitions (Models tab)
- [Board TUI — How to Pick a Task]({{< relref "/docs/tuis/board/how-to#how-to-pick-a-task-for-implementation" >}}) — Uses the `task-pick` operation to launch the configured agent
- [Code Browser]({{< relref "/docs/tuis/codebrowser" >}}) — Uses the `explain` operation for launching explain sessions
