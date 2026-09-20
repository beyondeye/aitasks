---
title: "Framework Session"
linkTitle: "Framework session"
weight: 95
description: "The machine-wide record of every running and frozen code agent that makes freeze and restore possible."
depth: [advanced]
---

## What it is

A **framework session** is the framework's own record of a code agent: which
project and tmux window it belongs to, which task it is working, which agent and
model it is, the CLI session id it could be resumed from, and where it sits in
the freeze/restore lifecycle. One record per agent, for every agent on the
machine, across every project.

The records live in a single file, `~/.config/aitasks/agent_sessions.json`, with
mode `0600`. `aitask_agent_sessions.sh` is the only writer: it holds a lock
around each read-modify-write and replaces the file atomically. Readers — the
viewer, `ait monitor`, `ait minimonitor` — take no lock at all, because every
write lands whole, so a reader always sees one complete generation.

A frozen agent's captured output does not live in that file. It goes to
`~/.config/aitasks/frozen/<id>/` (mode `0700`) as `capture.ansi`, the raw
terminal capture with its colour intact, and `capture.txt`, the same output
stripped to plain text.

### Identity versus location

A record is identified by **project root, window name and slot** — the slot
distinguishing a second agent that was split into the same window. That triple
is what survives the things that happen to a running agent.

Its pane id and process id are **location**, not identity. A tmux server
restart, a reattach or a respawn replaces them on the same record, which is why
a restarted tmux does not produce a second record for an agent it already knows.

The join between a pane and its record is the tmux pane option
`@aitask_record`, stamped on the pane after the record is written. Pane options
die with the pane, so a recycled pane id can never carry a stale one. Two more
options mark a frozen pane and a stand-in viewer that has finished booting;
together they are what lets the framework tell "the agent is still here" from
"the viewer has taken over" without trusting a process name.

### States

A record moves through five states. Every transition is a single guarded
operation — an illegal one is refused and writes nothing:

```text
                 freeze-begin              freeze-commit
      live ──────────────────▶ freezing ──────────────────▶ frozen
        ▲                          │                          │
        │      freeze-abort        │                          │ restore-begin
        └──────────────────────────┘                          ▼
        ▲                                                  restoring
        │  hook acknowledgement, or liveness confirmation      │
        └──────────────────────────────────────────────────────┤
                                                               │ restore-abort
                            stand-in back                      ▼
                 frozen ◀───────────────────────────────── aborting

      drop, from any state: the record and its capture files are removed
```

`freezing`, `restoring` and `aborting` are transitional: an operation is in
flight. `aborting` in particular is owned by the restore attempt that failed,
which stops a second restore from starting in the gap before the stand-in viewer
is back.

### Operation leases

Freezing and restoring are multi-step transactions run by a coordinator that
must outlive the pane it is respawning. Each takes a **lease** on the record — a
one-time nonce plus the coordinator's own process id — and every verb that
changes a leased record must present the matching nonce. A coordinator that lost
the race writes nothing rather than acting twice.

The lease is what makes repair safe. `reconcile` settles transitional records
from what tmux can be seen to hold, but it leaves a record alone while the
lease's owner is alive or the lease is younger than 60 seconds. Only a lease
whose owner is gone can be taken over.

### The session hook

`ait setup` installs a
[SessionStart hook]({{< relref "/docs/commands/setup-install" >}}#session-hooks)
that runs when a code agent starts. It records the agent's session id into the
record, which is what makes a later restore possible at all. It writes nothing
into the agent's session and always exits successfully.

The hook is also the acknowledgement channel for a restore. The replacement
agent is launched with the record id and the attempt's nonce in its environment;
the hook hands them back, and the store checks that the session that came up is
the session that was asked for. That is the **verified** outcome — and the only
one that deletes the capture files.

When no acknowledgement arrives within `frozen.restore_ack_grace`, the restore
is confirmed on the evidence the coordinator does have: the process it launched
is running in the pane. That is the **unverified** outcome, and it deliberately
**keeps** the capture. It is the normal outcome for an interactive Codex agent,
whose TUI fires no hook, and for any agent whose CLI reports no session.

### Cleanup rules

Records are retired only on positive evidence, and never on a partial view: an
observation that could not enumerate everything suppresses every removal, and
transitional records are exempt entirely — they belong to `reconcile`.

| Reason | What it means |
|---|---|
| `dead_window` | a live agent's window is gone from a project that was fully enumerated |
| `dead_pane` | its pane is gone or dead **and** its process is provably gone |
| `capture_missing` | a frozen record's capture file no longer exists, so there is nothing left to read or restore from |

Two things run this cleanup, so it does not depend on a TUI being open: the
maintenance tick of `ait monitor` and `ait minimonitor`, and the freeze/restore
coordinator, which reconciles after every operation.

### Overrides

Two environment variables relocate the state, which is what the test suite uses
and what an unusual home directory layout needs:

| Variable | Replaces |
|---|---|
| `AITASKS_AGENT_SESSIONS_FILE` | `~/.config/aitasks/agent_sessions.json` |
| `AITASKS_FROZEN_DIR` | `~/.config/aitasks/frozen` |

## Why it exists

An agent's pane is not a durable thing. It dies with a tmux restart, it is
recycled, it is renamed, it is split. Tying "which agent is this" to a pane
therefore loses agents exactly when it matters — after the crash or the reboot
you most want to recover from.

The store answers that question from outside tmux, machine-wide rather than
per-project, which is what makes it possible to end an agent's process and still
have something that knows how to bring it back.

## How to use

You rarely address the store directly. It is what the
[freeze and restore workflow]({{< relref "/docs/workflows/freeze-and-restore-agents" >}})
is built on, what `ait frozenagent` lists and acts on, and what the frozen rows
in `ait monitor` and `ait minimonitor` are reading.

## See also

- [Freeze and Restore Agents]({{< relref "/docs/workflows/freeze-and-restore-agents" >}}) — the workflow the store exists for.
- [Frozen Agent]({{< relref "/docs/tuis/frozenagent" >}}) — the viewer that stands in for a frozen agent's pane.
- [The IDE model]({{< relref "/docs/concepts/ide-model" >}}) — the tmux layout these records describe.
- [Locks]({{< relref "/docs/concepts/locks" >}}) — the other claim an agent holds, on its task rather than its pane.
