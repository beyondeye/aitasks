---
title: "Crew Orchestration"
linkTitle: "Crew"
weight: 50
description: "ait crew — initialize and run multi-agent crews (init, addwork, runner, dashboard, …)"
depth: [advanced]
maturity: [experimental]
---

`ait crew` manages **agentcrews** — teams of AI agents launched, ordered, and
monitored as a single coordinated unit. For the conceptual model (what a crew
is, how the dependency DAG and runner work, and why brainstorm is built on it),
see the [Agentcrews concept page]({{< relref "/docs/concepts/agentcrews" >}}).

> Agentcrews are an evolving feature — the `ait crew` CLI surface may still change.

A crew is created with `init`, populated with agents via `addwork`, and run by
the `runner`. The remaining subcommands inspect and control a running crew. Run
`ait crew <subcommand> --help` for the authoritative options of each.

## ait crew init

Create a new agentcrew with its own git branch and worktree. The crew's
identifier names an orphan branch `crew-<id>` checked out under
`.aitask-crews/crew-<id>/`.

```bash
ait crew init --id sprint1 \
  --add-type impl:claudecode/opus4_6 \
  --add-type review:claudecode/sonnet4_6:interactive \
  --batch
```

| Option | Description |
|--------|-------------|
| `--id <id>` | Crew identifier (required; lowercase alphanumeric, hyphens, underscores) |
| `--name <display_name>` | Human-readable name (defaults to the id) |
| `--add-type <id>:<agent>[:<launch_mode>]` | Register an agent type (repeatable). Optional third field sets the launch mode: `headless`, `interactive`, `openshell_headless`, or `openshell_interactive` |
| `--batch` | Non-interactive mode (no prompts) |

Batch output: `CREATED:<id>`.

## ait crew addwork

Register a new agent in an existing crew, creating all of its coordination
files (work-to-do, status, output, command queue, heartbeat). Use `--depends` to
wire the agent into the crew's dependency DAG.

```bash
ait crew addwork --crew sprint1 --name planner --work2do tasks/plan.md --type impl --batch
ait crew addwork --crew sprint1 --name coder   --work2do tasks/code.md --type impl --depends planner --batch
```

| Option | Description |
|--------|-------------|
| `--crew <id>` | Crew identifier (required) |
| `--name <agent_name>` | Agent name (required; lowercase alphanumeric, underscores) |
| `--work2do <file>` | Path to the work-to-do markdown file, or `-` for stdin (required). Supports `<!-- include: filename -->` directives resolved relative to the file's directory (one level only) |
| `--type <type_id>` | Agent type ID (required; must exist in the crew's agent types) |
| `--depends <a,b>` | Comma-separated list of agent names this agent depends on |
| `--group <name>` | Operation group name (e.g. `explore_001`) |
| `--launch-mode <mode>` | Launch mode (default: `headless`): `headless`, `interactive`, `openshell_headless`, `openshell_interactive` |
| `--batch` | Non-interactive mode (no prompts) |

Batch output: `ADDED:<name>`.

## ait crew setmode

Change the launch mode of a **Waiting** agent. Launch mode only applies to
pending launches, so this refuses to mutate agents that are already
Running / Completed / Error / Aborted / Paused.

```bash
ait crew setmode --crew sprint1 --name coder --mode interactive
```

| Option | Description |
|--------|-------------|
| `--crew <id>` | Crew identifier (required) |
| `--name <agent>` | Agent name (required) |
| `--mode <MODE>` | New launch mode (required): `headless`, `interactive`, `openshell_headless`, `openshell_interactive` |

Output: `UPDATED:<agent>:<mode>`.

## ait crew status

Get or set the status of the crew or an individual agent, list all agents, or
send a heartbeat.

```bash
ait crew status --crew sprint1 list
ait crew status --crew sprint1 --agent coder get
ait crew status --crew sprint1 --agent coder set --status Running --progress 40
ait crew status --crew sprint1 --agent coder heartbeat -m "loaded baseline"
```

| Argument / Option | Description |
|--------|-------------|
| `--crew <id>` | Crew identifier (required) |
| `--agent <name>` | Agent name (omit for crew-level status) |
| `get` | Show current crew or agent status |
| `list [--group <name>]` | List all agents and their statuses (optionally filtered to a group) |
| `set [--status <s>] [--progress <0-100>] [--no-push]` | Update an agent's status and/or progress |
| `heartbeat [-m, --message <text>]` | Update an agent's heartbeat with an optional progress message |

## ait crew command

Queue runtime control commands for agents. Commands persist in the agent's
queue until acknowledged.

```bash
ait crew command send     --crew sprint1 --agent coder --command kill
ait crew command send-all --crew sprint1 --command pause
ait crew command list     --crew sprint1 --agent coder
ait crew command ack      --crew sprint1 --agent coder
```

| Sub-command | Description |
|-------------|-------------|
| `send` | Send a command to a specific agent (needs `--agent`) |
| `send-all` | Send a command to all Running agents |
| `send-group` | Send a command to all agents in a group (needs `--group`) |
| `list` | List pending commands for an agent (needs `--agent`) |
| `ack` | Acknowledge (clear) pending commands for an agent (needs `--agent`) |

| Option | Description |
|--------|-------------|
| `--crew <id>` | Crew identifier (required) |
| `--agent <name>` | Agent name (required for `send`, `list`, `ack`) |
| `--group <name>` | Group name (required for `send-group`) |
| `--command <cmd>` | Command to send: `kill`, `pause`, `resume`, `update_instructions` |
| `--sent-by <who>` | Who sent the command: `runner` or `user` (default: `user`) |

Output: `COMMAND_SENT:<cmd>`, `COMMANDS_ACKED:<agent>`, or `NO_COMMANDS`.

## ait crew runner

Start (or check) the runner that orchestrates a crew — it computes the
dependency order, launches Ready agents up to the concurrency cap, and tracks
their heartbeats.

```bash
ait crew runner --crew sprint1                 # start the runner loop
ait crew runner --crew sprint1 --once --dry-run # preview one iteration
ait crew runner --crew sprint1 --check          # diagnose runner state
```

| Option | Description |
|--------|-------------|
| `--crew <id>` | Crew identifier (required) |
| `--interval <N>` | Seconds between iterations (default: config, or 30) |
| `--max-concurrent <N>` | Maximum agents running at once (default: config, or 3) |
| `--once` | Run a single iteration and exit |
| `--dry-run` | Show what would happen without launching agents |
| `--check` | Diagnostic mode — report runner state only |
| `--force` | Force restart if a runner is already active on the same host |
| `--reset-errors` | Reset `Error` agents back to `Waiting` before starting |
| `--batch` | Structured output |

## ait crew report

Report on crew state, agent details, and aggregated outputs.

```bash
ait crew report list                              # all crews
ait crew report summary --crew sprint1            # crew overview
ait crew report detail  --crew sprint1 --agent coder
ait crew report output  --crew sprint1            # aggregate agent outputs
```

| Sub-command | Description |
|-------------|-------------|
| `list` | List all agentcrews |
| `summary --crew <id> [--group <name>]` | Crew overview with agent statuses |
| `detail --crew <id> --agent <name>` | Detailed report for one agent |
| `output --crew <id> [--group <name>]` | Aggregate agent output files |

Pass `--batch` for structured output suitable for scripting.

## ait crew cleanup

Remove completed crew worktrees and, optionally, delete their branches. Only
crews in a terminal state (`Completed`, `Error`, `Aborted`) are cleaned.

```bash
ait crew cleanup --crew sprint1 --delete-branch --batch
ait crew cleanup --all-completed --delete-branch
```

| Option | Description |
|--------|-------------|
| `--crew <id>` | Clean a specific crew |
| `--all-completed` | Clean every crew in a terminal state |
| `--delete-branch` | Also delete the crew's git branch |
| `--batch` | Non-interactive, machine-parseable output |

Batch output: `CLEANED:<id>`, `NOT_TERMINAL:<id>:<status>`, or `NOT_FOUND:<id>`.

## ait crew dashboard

Open the Textual **TUI dashboard** for monitoring and managing crews — live
agent statuses and progress, dependency ordering, heartbeats, log previews, and
inline controls to pause, resume, or kill agents.

```bash
ait crew dashboard
```

Takes no required arguments; it discovers the crews under `.aitask-crews/`.

## ait crew logview

Open the **agent log viewer** TUI. It renders an agent's log file with full
ANSI escape support and tails it live by default.

```bash
ait crew logview --path .aitask-crews/crew-sprint1/coder_log.txt
ait crew logview sprint1 coder            # resolve the log for an agent
ait crew logview sprint1 coder --no-tail  # static snapshot instead of live tail
```

| Argument / Option | Description |
|--------|-------------|
| `--path <file>` | Path to the agent log file to render |
| `<crew_id> <agent_name>` | Resolve the log file for a named agent in a crew |
| `--no-tail` | Show a static snapshot instead of tailing the file live |

## On-disk layout

A crew's state lives in its worktree at `.aitask-crews/crew-<id>/`:

```text
.aitask-crews/crew-<id>/        # worktree of the orphan branch crew-<id>
├── _crew_meta.yaml             # static config: id, name, agent types, agents
├── _crew_status.yaml           # dynamic crew state: status, progress
├── _runner_alive.yaml          # runner heartbeat
├── <agent>_work2do.md          # the agent's task description
├── <agent>_status.yaml         # the agent's lifecycle state
├── <agent>_output.md           # the agent's results (read by downstream agents)
├── <agent>_commands.yaml       # the agent's pending command queue
└── <agent>_alive.yaml          # the agent's heartbeat
```

---

**Next:** [Development Guide]({{< relref "/docs/development" >}})
