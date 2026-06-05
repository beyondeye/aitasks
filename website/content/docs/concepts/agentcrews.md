---
title: "Agentcrews"
linkTitle: "Agentcrews"
weight: 75
description: "The multi-agent orchestration engine that runs a team of AI agents as a dependency-ordered crew."
depth: [advanced]
maturity: [experimental]
---

> Agentcrews are an evolving feature — the `ait crew` CLI surface may still change.

## What it is

An **agentcrew** is a team of AI agents (workers) defined, launched, and
monitored as a single coordinated unit. You create a crew, register one or more
agents in it — each with its own work description — declare the dependencies
between them, and let a background **runner** launch them in the right order.

Each crew is **isolated**: it lives on its own orphan git branch (`crew-<id>`)
checked out as a worktree under `.aitask-crews/crew-<id>/`, with no source code —
just the crew's coordination state. Every agent in the crew has:

- a **work-to-do** file describing its task,
- a **status** that moves through a fixed lifecycle —
  `Waiting → Ready → Running → Completed` (or `Error` / `Aborted` / `Paused`),
- **heartbeats** so the runner can tell it is still alive,
- an **output** file that downstream agents and reports can read, and
- a **command queue** for runtime control (pause, resume, kill).

Agents declare **dependencies** on one another, forming a directed acyclic graph
(DAG). The runner computes a topological order and launches agents as their
upstream dependencies complete, up to a configurable **concurrency cap**.

## Why it exists

Agentcrew is the **orchestration engine underneath the framework's multi-agent
flows**. Rather than each higher-level feature reinventing process spawning,
dependency ordering, liveness tracking, and isolation, those features compose on
top of one shared crew primitive. The framework's **brainstorm** sessions, for
example, are built directly on agentcrew — they create a crew, register their
specialized roles as agents through the same `ait crew` plumbing, and drive them
with the crew runner.

Running agents as a crew buys three things that are awkward to get otherwise:

- **Parallelism with ordering** — independent agents run concurrently, while
  dependent ones wait for their inputs, all from a single DAG you declare once.
- **Inter-agent hand-off** — a downstream agent reads the output files of the
  upstream agents it depends on, so work flows through the team.
- **Live observability and intervention** — heartbeats, status, and logs are
  visible in real time, and you can pause, resume, or kill agents mid-run from
  the dashboard or the command line.

## How to use

Most users meet agentcrew indirectly, through a higher-level flow like
brainstorm. To drive one directly, the minimal loop is:

1. `ait crew init` — create the crew.
2. `ait crew addwork` — register each agent (repeat, using `--depends` to wire
   the DAG).
3. `ait crew runner` — start the orchestrator that launches agents in order.
4. `ait crew dashboard` / `ait crew report` / `ait crew logview` — watch progress
   and inspect outputs.
5. `ait crew cleanup` — remove the crew's worktree and branch when it is done.

The full subcommand surface — including status, runtime commands, and the
monitoring TUIs — is documented in the
[`ait crew` command reference]({{< relref "/docs/commands/crew" >}}).

## See also

- [`ait crew` command reference]({{< relref "/docs/commands/crew" >}}) — every subcommand and its options
- [Locks]({{< relref "/docs/concepts/locks" >}}) — how concurrent agents avoid stepping on each other
- [Git branching model]({{< relref "/docs/concepts/git-branching-model" >}}) — the dedicated branches that hold framework state, akin to the per-crew orphan branch

---

**Next:** [Agent attribution]({{< relref "/docs/concepts/agent-attribution" >}})
