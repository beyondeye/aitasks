---
title: "Framework Session"
linkTitle: "Framework session"
weight: 95
description: "The machine-wide record of every running and frozen code agent that makes freeze and restore possible."
depth: [intermediate]
---

## What it is

A **framework session** is the record aitasks keeps of a coding agent: which
project and tmux window it belongs to, which task it is working on, which agent
and model it is, and the id its CLI can resume the conversation from. There is
one record per agent, for every agent on the machine, in every project. The
record is kept apart from the agent's terminal pane, so it outlasts the pane.

## Why it exists

A tmux pane does not last. It dies when the tmux server restarts or the machine
shuts down, and it can be recycled, renamed or split. An agent known only by its
pane is lost with the pane.

The framework session is what lets you **freeze** an agent: end its process and
keep its terminal output readable in its pane. It is also what lets you
**restore** a frozen agent: start its coding agent again on the same
conversation. Freezing frees the memory and the share of the
machine a finished agent still holds, and the record keeps what is needed to
bring the agent back later, even after a reboot.

## How to use

You never edit the record; aitasks writes it. You meet it when you freeze an
agent, with **f** in `ait monitor` or `ait minimonitor` (**Z** freezes every
agent), and when you restore one with **R** in the
[frozen-agent viewer]({{< relref "/docs/tuis/frozenagent" >}}) that takes its
pane. [Freeze and Restore Agents]({{< relref "/docs/workflows/freeze-and-restore-agents" >}})
walks through both, including re-picking a frozen agent's task instead and
bringing agents back after a reboot.

A restore needs the agent's session id. The session hook, which `ait setup`
offers to install, records it when the agent starts. Without it, re-pick the
task instead.

## See also

- [Freeze and Restore Agents]({{< relref "/docs/workflows/freeze-and-restore-agents" >}}) — when to freeze, the ways back, and what to do when a restore fails.
- [Frozen Agent]({{< relref "/docs/tuis/frozenagent" >}}) — the viewer that takes a frozen agent's pane, its keys and its messages.
- [Session hooks]({{< relref "/docs/commands/setup-install" >}}#session-hooks) — what `ait setup` installs so an agent can be restored.
- [Framework Session Store]({{< relref "/docs/development/framework-session" >}}) — where the records live, how a record is identified, its states, how a restore is verified and when a record is retired.
- [The IDE model]({{< relref "/docs/concepts/ide-model" >}}) — the tmux layout these records describe.
- [Locks]({{< relref "/docs/concepts/locks" >}}) — the task lock an agent holds on its task.

---

**Next:** [Agent memory]({{< relref "/docs/concepts/agent-memory" >}})
