---
title: "Framework Session Store"
linkTitle: "Framework Session"
weight: 62
description: "Where framework session records and frozen captures live, how a record is identified, its states and leases, what the session hook records, how a restore is verified, when a record is retired, and the freeze engine's commands"
depth: [advanced]
---

The framework session store holds one record per coding agent on the machine and the captured output of every frozen agent; what a framework session is for is on the [Framework session]({{< relref "/docs/concepts/framework-session" >}}) concept page.

## Where the state lives

The records live in a single file, `~/.config/aitasks/agent_sessions.json`, with mode `0600`. It covers every project on the machine.

A frozen agent's captured output is not in that file. It goes to `~/.config/aitasks/frozen/<id>/` (mode `0700`) as two files:

| File | Contents |
|---|---|
| `capture.ansi` | the raw terminal capture, with its colour intact |
| `capture.txt` | the same output stripped to plain text |

Both locations can be moved with environment variables; see [Overrides](#overrides).

## Who writes it

`aitask_agent_sessions.sh` is the only writer. Every write replaces the file whole, so a reader always sees one complete generation of the records and needs no lock. The readers are the [frozen-agent viewer]({{< relref "/docs/tuis/frozenagent" >}}), `ait monitor` and `ait minimonitor`.

## Identity and location

A record is identified by its project root, its tmux window name and its slot. The slot is a number that tells apart a second agent split into the same window. These three values survive a tmux server restart, a reattach or a respawn, which change the pane id and process id. Each record also has a generated id, which names its capture directory and is what `@aitask_record` stores; when its window is renamed, the record keeps its id and takes the new name.

The pane id and the process id are the record's location, so when they change they are replaced on the same record. An agent that starts in a window where exactly one `live` record has lost its process takes over that record, so a restarted tmux does not produce a second record for an agent the store already knows. When two or more such records share the window, nothing tells them apart: the agent gets a new record and the old ones are left to the [cleanup rules](#cleanup-rules). How long a `live` record waits to be taken over is set by the [cleanup rules](#cleanup-rules).

The tmux pane option `@aitask_record` joins a pane to its record. Pane options die with the pane, so a recycled pane id can never carry a stale one.

## States

A record moves through five states. Every transition is a single guarded operation: an illegal one is refused and writes nothing.

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

A drop is refused while the record holds captured text that [sitrep]({{< relref "/docs/workflows/sitrep" >}}) has not harvested; `aitask_frozen.sh drop` runs that harvest first.

`freezing`, `restoring` and `aborting` are transitional: an operation is in flight. `aborting` is owned by the restore attempt that failed, which stops a second restore from starting before the viewer is back in the pane.

## Operation leases

A freeze or a restore is a run of several steps. A background process, the coordinator, runs them, and it has to outlive the pane it respawns. Each operation takes a lease on the record, owned by its coordinator. While the lease is held only that coordinator can change the record, so a coordinator that lost a race writes nothing instead of acting twice.

`aitask_frozen.sh reconcile` settles transitional records from what tmux can be seen to hold (when it runs is in [The freeze engine](#the-freeze-engine)). It leaves a record alone while the lease's owner is alive or the lease is younger than 60 seconds. Only a lease whose owner is gone can be taken over.

## The session hook

The [SessionStart hook]({{< relref "/docs/commands/setup-install" >}}#session-hooks) that `ait setup` installs records the agent's session id into its record, which is what lets a later restore resume that session. The rules below decide when it records and what it records.

### When it records

The hook records only when it runs inside the agent's own pane, never on another agent's behalf. This matters for a Codex agent started by hand, without the framework's launch overrides. Codex can run such an agent through its shared app-server daemon. The daemon then runs the hook on that agent's behalf and reports the pane that started the daemon, which is not necessarily this agent's pane. Those reports are ignored, so a hand-started Codex agent like this can only be brought back by re-picking its task.

### Which CLI owns the session

The hook also records which CLI owns the session. An agent launched by the framework names itself. For an agent you start by hand, the hook works out the CLI from the transcript path the agent reports, and only from a path that belongs to the session being reported. An agent started inside another agent inherits that agent's identity. When the inherited identity and the transcript disagree, the hook records nothing.

A restore resumes the session only with that same CLI. For an agent started by hand, the restore uses the agent and model the record names when freezing could recover them (the agent was started with a model the framework knows). Without them it would launch the project's default agent for the `raw` operation (see [Operations]({{< relref "/docs/commands/codeagent" >}}#operations)), and it resumes only when that default is the same CLI. When nothing could tell which CLI it was, or the restore would launch a different one, the restore is refused and the agent stays frozen; you can still re-pick its task.

An OpenCode agent cannot resume a session, so it can only be re-picked.

A Codex agent's session is also captured when it is frozen, on Linux and macOS, from the transcript its own process holds open. That works only while Codex runs its TUI in its own process. The framework's Codex launches pass `-c tui.alternate_screen=never`, which keeps it there; a Codex you start by hand without that override can be routed through the shared app-server daemon, which holds the transcript instead, so no session is captured for it (see [When it records](#when-it-records)). For a Codex you type at a shell prompt, the freeze reads only the shell's foreground job: a suspended or background Codex is never taken for the pane's agent. Codex opens its transcript at its first turn, so an agent frozen before then has no session to resume.

A captured Codex session is kept only when the framework can name the model a restore would launch. When the launch named a model with `-m` (or `--model`), that model decides: one listed in `aitasks/metadata/models_codex.json` is recorded with the session, and any other leaves no session. When the launch named no model, a Codex model already on the agent's record is used. Without either, no session is kept, and the agent can only be re-picked.

## Restore verification

The hook is also how a restore is acknowledged. The replacement agent is launched with the record id and the attempt's nonce in its environment. The hook hands them back, and the store checks that the session that came up is the session that was asked for. That is the verified outcome, and only a verified restore deletes the capture files. What the two outcomes look like to the user is in [What "unverified" means]({{< relref "/docs/workflows/freeze-and-restore-agents" >}}#what-unverified-means).

A resumed Codex agent is verified by the session transcript it holds open. Its TUI fires the hook only at a session's first turn, so the coordinator does not wait for a hook. It reads which session's transcript the resumed process holds open, and the store compares that session with the one it asked for. A match is verified and deletes the capture. A different session aborts the restore.

When nothing verifies the restore within `frozen.restore_ack_grace` (see the [viewer's configuration]({{< relref "/docs/tuis/frozenagent/reference" >}}#configuration)), it is confirmed on the evidence the coordinator does have: the process it launched is running in the pane. That is the unverified outcome, and it keeps the capture. It is the outcome for any agent whose CLI reports no session within the grace, and for a Codex resume whose session cannot be read from the process, for example a TUI routed through the shared Codex app-server daemon, which holds the transcript instead.

A hook that reports in after the restore has settled is never refused. Codex does this at its first turn. If the restore was confirmed on liveness and the hook comes from the launched process with the session that was asked for, the restore is upgraded to verified and the capture is deleted. Any other late report updates the record, so the pane keeps following the agent's current session.

## Cleanup rules

Records are retired only on positive evidence and never on a partial view. An observation that could not enumerate everything suppresses every removal. Transitional records are exempt from these rules: `reconcile` settles them.

| Reason | Applies to | When |
|---|---|---|
| `dead_window` | a `live` record | its project was fully enumerated and its window was not seen there |
| `dead_pane` | a `live` record | its pane is gone or dead, and its process is provably gone |
| `capture_missing` | a `frozen` record | its capture file no longer exists, so there is nothing left to read or restore from |

A project counts as fully enumerated only when every tmux session that belongs to it was listed successfully. A project with no tmux session on the server is not enumerated at all, so none of its records are retired. `ait monitor` and `ait minimonitor` count a window as seen only when they found an agent in it; `reconcile` counts any window of the project's sessions.

These rules decide what survives a tmux restart. A frozen record is never retired because its window or pane is gone, so a frozen agent stays until you drop it, a verified restore consumes it, or its capture file goes missing. A `live` record whose agent died with the server stays only until a full enumeration of its project finds its window or its pane gone. An agent started again in that window before then takes over the record when it is the only `live` record in that window to have lost its process; one started after then gets a new record.

A record that still holds captured text that [sitrep]({{< relref "/docs/workflows/sitrep" >}}) has not harvested is kept, whichever reason applies.

`aitask_frozen.sh reconcile` runs this cleanup as its last step; when reconcile runs is in [The freeze engine](#the-freeze-engine).

## The freeze engine

`.aitask-scripts/aitask_frozen.sh` freezes, restores, drops and reconciles records; the monitors, the [frozen-agent viewer]({{< relref "/docs/tuis/frozenagent" >}}) and `ait ide` all call it. It has no `ait` subcommand: `ait frozenagent` is the viewer. Its forms:

| Command | What it does |
|---|---|
| `freeze <pane_id>` | freeze one agent pane |
| `freeze --all [--dry-run]` | freeze every agent pane on every aitasks session, one at a time (the **Z** key); `--dry-run` lists what it would freeze and stops |
| `restore <id> [--repick] [--session NAME]` | restore one record: resume its session, or with `--repick` re-pick its task |
| `restore --all [--repick] [--session NAME]` | restore every `frozen` record (see [Restore-All](#restore-all)) |
| `drop <id> [--skip-harvest]` | harvest the capture into sitrep, then remove the record, its capture and its viewer; refused when the harvest fails, and `--skip-harvest` discards the capture without it |
| `reconcile` | settle every record that is not `live`, then apply the [cleanup rules](#cleanup-rules) |
| `gone --root <path>` / `gone --all-roots` | list, without changing anything, the frozen records whose viewer is not tracked, for one project or for every project grouped by project |
| `reopen <id> [--session NAME]` / `reopen --root <path> [--session NAME]` | bring those viewers back; the agents stay frozen |
| `companions --root <path>` / `companions --all-roots` | give every tracked viewer the minimonitor its window should have; running it again starts no second one |

`gone`, `reopen` and `companions` are the steps of the [`ait ide` frozen-agent check]({{< relref "/docs/tuis/frozenagent/reference" >}}#the-ait-ide-frozen-agent-check). With `--session NAME`, an agent or viewer whose pane is gone lands only in `NAME`, and only when that session belongs to the record's project; otherwise that record fails and nothing is created. `NAME` may not contain `.` or `:`.

Each command prints one result line per pane or record on standard output. Four forms end with a summary line: `restore --all` prints `RESTORE_ALL:<succeeded>/<total>`, `gone` prints `GONE_COUNT:<n>`, `companions` prints `COMPANION_COUNT:<n>`, and `freeze --all --dry-run` prints one `WOULD_FREEZE:` line per pane it would freeze, then `FREEZE_ELIGIBLE:<n>`.

The exit status is `0` when every result succeeded (an empty batch counts as success), `1` when at least one failed, and `2` for a usage error. Two commands differ: `gone` exits `1` only when the session store cannot be read, and `reconcile` always exits `0`, even when it prints `RECONCILE_FAILED:` lines.

`reconcile` respawns a viewer whose pane died, settles a freeze or a restore whose coordinator was killed part-way from what tmux can be seen to hold, and unmarks an agent that came back but still carries its frozen mark, so it can be frozen again. It runs on the maintenance tick of any open `ait monitor` or `ait minimonitor`, about a minute after the TUI starts and then every 10 minutes, and whenever you run it yourself.

### Restore-All

`restore --all` works through every `frozen` record in the store, from every project, one at a time. One record's failure never stops the batch: with three frozen agents and one missing binary, the other two come back. After the per-record lines it prints `RESTORE_ALL:<succeeded>/<total>`.

Without `--repick`, a record fails before anything starts when it has no recorded session id, when its agent cannot resume a session (OpenCode), or when its CLI is unknown or is not the one the restore would launch (see [Which CLI owns the session](#which-cli-owns-the-session)). Such a record keeps its capture; re-pick it with `--repick`. With `--repick`, a record without a task id fails the same way.

A record whose viewer is still in its pane is restored in that pane. When the pane is gone, the agent comes back in a new window of its project's tmux session, under its recorded window name; if that name is taken, the window gets a `-2` suffix (then `-3`, and so on). When the project has no tmux session, one is created the way `ait ide` creates it, named by `tmux.default_session`. A session name already held by another project is never borrowed: that record fails and its capture is kept.

## Overrides

Two environment variables move the state, for a home directory with an unusual layout:

| Variable | Replaces |
|---|---|
| `AITASKS_AGENT_SESSIONS_FILE` | `~/.config/aitasks/agent_sessions.json` |
| `AITASKS_FROZEN_DIR` | `~/.config/aitasks/frozen` |
