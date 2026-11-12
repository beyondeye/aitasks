---
title: "Feature Reference"
linkTitle: "Reference"
weight: 30
description: "Keybindings, header fields, states, exit codes and configuration for ait frozenagent, and the frozen-agent check ait ide runs at startup"
maturity: [experimental]
depth: [advanced]
---

## Keybindings

Every key below can be rebound — press **?** for the in-place editor, or open
[Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}}).

| Key | Action | Notes |
|-----|--------|-------|
| `r` | Toggle ANSI replay / plain text | Viewer mode only |
| `m` | Render the capture as Markdown | Selected range if any, else the whole capture |
| `/` | Open the search box | Viewer mode only |
| `n` | Jump to the next match | Wraps, and says so |
| `Escape` | Close the search box, else clear the keyboard range | Every Escape also clears a mouse selection |
| `shift+↑` / `shift+↓` | Extend a line range from the cursor | |
| `y` | Copy the selection | Keyboard range first, else the mouse selection |
| `ctrl+c` | Copy the selection | Same as `y`. With nothing selected it shows the quit hint; in the open search box it copies the text selected there. If you rebind it, `ctrl+c` still copies |
| `g` / `G` | Jump to the top / bottom | |
| `R` | Restore the agent | No confirmation |
| `P` | Re-pick the task | No confirmation; needs a task id on the record |
| `k` | Drop the record | Confirms — this deletes the capture |
| `Enter` | Open the highlighted record | List mode only |
| `j` | TUI switcher | |
| `?` | Shortcut editor | |
| `q` | Quit | |

The footer advertises only `Keys`, `Quit`, `Plain/ANSI`, `Markdown`, `Search`,
`Restore`, `Re-pick` and `Drop`, plus `Copy` (`y` and `ctrl+c`) while something
is selected; the rest are bound but unlisted.

While an operation is in flight on a record, that record's `R`, `P` and `k` are
disabled rather than queued.

## Header fields

Seven fields joined by ` · `, in this order:

| Field | Empty value |
|-------|-------------|
| Project root, shortened | — |
| tmux window name | — |
| Task (`t<id>` plus its title) | `(no task)` |
| Agent string | `(agent unknown)` |
| `frozen <timestamp>` | falls back to the record's state |
| `<n> lines` | — |
| State, or the note currently overriding it | — |

Trailing markers: `\[plain]`, `\[colour unavailable — showing plain text]`.
State suffixes: `· capture missing`, `· colour data missing`.

In list mode the header is `frozen records: <n>` instead.

## States shown

The viewer prints the record's state from the session store verbatim. The
vocabulary is `live`, `freezing`, `frozen`, `restoring` and `aborting` — a
frozen record you are reading normally shows `frozen`, and the transitional
values appear while an operation is settling.

Outcomes are sentences rather than states:

| Message | Capture | Meaning |
|---|---|---|
| `restored` | deleted | the resumed agent confirmed itself |
| `restored, unverified — capture kept` | **kept** | running, but unconfirmed — a success |
| `restore failed: <reason> — capture kept` | kept | the attempt failed; a new viewer takes the pane again |
| `restore ended — capture kept` | kept | ended with no recorded reason |
| `cannot restore: <reason> — re-pick it instead (P)` | kept | the record cannot be resumed (no session, or its CLI is unknown or not the one the restore would launch); nothing was dispatched |
| `restore did not start — run 'ait frozenagent' or reconcile` | kept | nothing was dispatched |
| `restore still <state> after the grace — run reconcile; capture kept` | kept | still transitional |
| `record vanished` | — | the record is gone |
| `dropped — capture removed` | deleted | drop succeeded |
| `drop failed — record kept` | kept | nothing was deleted |

The new viewer that takes the pane after a failed restore shows the store's
memory of it:
`last restore failed: <reason> — capture kept`.

## Exit codes

| Code | Cause |
|------|-------|
| `0` | Normal quit |
| `1` | Missing Python packages, or an interpreter older than the framework requires — both say to run `ait setup` |
| `2` | Bad arguments (`usage: ait frozenagent [--record <id>]`), or `frozenagent: unknown record <id>` |

## Configuration

Two keys under a `frozen:` block in `aitasks/metadata/project_config.yaml`
affect frozen agents. No `frozen:` block ships by default, so both defaults apply
unless you add one.

| Key | Default | Effect |
|-----|---------|--------|
| `capture_max_lines` | `50000` | How far back into the pane's scrollback a freeze reaches. The capture runs from that depth to the bottom of the visible pane, so it holds about this many lines plus one pane height; older output is left out |
| `restore_ack_grace` | `20` (seconds) | How long a restore waits to be verified — by the resumed agent's SessionStart hook, or for a Codex resume on Linux and macOS by the transcript its process holds open — before falling back to confirming on liveness alone |

`restore_ack_grace` is read from the **record's own project**, not from whichever
project you happen to be viewing from, because a freeze-all spans projects.

The same grace sets how long the viewer watches a restore before reporting
`restore still <state> after the grace — run reconcile; capture kept`: 10 seconds
for the dispatch, plus `restore_ack_grace`, plus 10 seconds of slack — 40 seconds
at the default. The viewer reads it from the record's project, so raising the
grace never turns a slow but successful restore into a stall report.

It sets a **waiting period, not an outcome.** Raising it only helps an agent
whose acknowledgement is slow to arrive. One that never acknowledges at all
within it reaches `restored, unverified — capture kept` however long the grace
is: its CLI reports no session on startup, the session hook is not installed, or
it is a Codex resume whose session cannot be read from the process. Nothing is
lost in that case: the unverified outcome is the one that keeps the capture.

## The `ait ide` frozen-agent check

When `ait ide` starts, after it has claimed its tmux session and before it
attaches, it looks for frozen records whose viewer is not tracked: after a
shutdown killed the tmux server, that is every frozen agent. The session store
covers the whole machine, so the check covers every project in it. It never
stops `ait ide` from starting: a step that fails prints a warning and the
startup goes on. `ait ide --no-frozen-check` skips the whole check, the
minimonitor top-up included.

### The listing

The listing opens with `Frozen agents whose viewer is gone (<n> in <k> project(s)):`
and has one group per project. This project comes first, labelled
`(this project)`; the others follow in order of their registry name (the
directory name when they have none). A group's header names the project and its
count, and for another project either `lands in its own tmux session` or the
reason it is not touched (see [Which projects are acted on](#which-projects-are-acted-on)).

Each row shows the window name, the task (`t<id>`), when the record was frozen,
`restore: yes|no` and `re-pick: yes|no`, and may end with a marker:

| Marker | Meaning |
|---|---|
| `(viewer open, untracked)` | a viewer window that an earlier, unfinished attempt left open and the framework lost track of; it is picked up, never duplicated |
| `(an earlier restore's agent is still running, untracked)` | a restore into a new window did not finish, and the agent it started is still running in a window no record tracks. It is never taken for a viewer, so bringing the viewers back reports it as failed |
| `(view only)` | the record can be neither restored nor re-picked |

A record whose state could not be checked is reported in a warning line instead.
When this project's Claude Code session hook is missing or invalid, a separate
note follows the listing; it concerns future sessions and does not explain the
listed records.

### The answers

`ait ide` asks one question per project it can act on,
`Choice for <project> [V/r/p/s]:`, with the counts each answer would affect:

| Answer | Effect |
|---|---|
| `V`, or an empty answer (the default) | each viewer comes back in a new window under its recorded window name (with a `-2`, `-3`… suffix when the name is taken); the agents stay frozen |
| `R` | the viewers come back, then every record that can resume is restored inside its viewer; the rest stay as viewers |
| `P` | the viewers come back, then every record that has a task id is re-picked inside its viewer; the rest stay as viewers |
| `S`, or any other answer | nothing changes; the records stay listed in `ait frozenagent` |

Every question is asked before anything runs, because each restore waits for its
agent's acknowledgement. When no listed project can be acted on, no question is
asked and the records stay listed in `ait frozenagent`.

For `R` and `P`, the viewers are brought back first, then every record is checked
again, and only then restored. A record is skipped, and the skip is reported,
when its viewer is still open but not tracked, when an earlier restore's agent
is still running for it, or when it could not be checked. If the second check
fails as a whole, nothing is restored. Each project reports
`Viewers: <n> reopened, <n> failed.` and, for `R` or `P`,
`Restored <n>, viewers <n>, failed <n>, skipped <n>.`

A record marked `(an earlier restore's agent is still running, untracked)` is
refused by restore, re-pick and drop alike, which name its window: going ahead
would start a second agent on the same session, or delete the record while that
agent runs. Close that window, then try again.

### Where the agents land

This project's agents go into the session `ait ide` is opening, including one
chosen with `--session`. Every other project's agents go into that project's own
tmux session, never into the one being opened: the first session that belongs to
the project, or a new one created the way `ait ide` creates it, under the
project's `tmux.default_session` name. Each project is handled on its own, so
when a project's session cannot be created (its name is already held by another
project, or its `tmux.default_session` cannot be read), that project's records
are reported as failed and stay frozen, and the other projects go on.

When it is done, `ait ide` names the other projects' sessions, which you reach
with `j` from any TUI or by running `ait ide` in that project, and names the
projects you skipped.

### Which projects are acted on

This project is always acted on. Another project only when it is registered (see
`ait projects list`; `ait ide` registers a project the first time it runs there)
and its directory still holds an aitasks project. Any other project's group is
listed with a reason and not touched: no question is asked and no tmux session
is created for it.

| Reason shown | Cause | What to do |
|---|---|---|
| `project directory gone` | the directory no longer holds an aitasks project | drop the records in `ait frozenagent` |
| `not a registered project` | the project is not in the registry | run `ait ide` in that project, or `ait projects add <path>` |
| `project registry unreadable` | the registry file could not be read, so no other project is acted on | fix the registry, then run `ait ide` again |
| `project directory unreadable` | the project's directory could not be looked into, for example without search permission | fix the permissions |
| `project could not be verified` | any other failure to decide | run `ait ide` again |

### Companions

Every run of the check gives each tracked frozen viewer on the tmux server that
has lost its minimonitor a new one, across all projects. It does so whatever the
answers, and also when nothing is listed. A viewer brought back by the check gets its
minimonitor the way any agent window does, and so does an agent restored inside
its viewer. A window that already has a minimonitor, even one still starting,
never gets a second. `ait ide` prints
`Companions: <n> viewer window(s) got their minimonitor back.` only when it
started one.

### Without a terminal

When standard input or output is not a terminal (a script, or `ait ide` piped
into something), nothing is asked. A one-line note on standard error says how
many frozen agents have no open viewer in this project and in the others, and
points to `ait frozenagent`. The minimonitor top-up still runs.

The same steps are available without `ait ide` through
`aitask_frozen.sh gone`, `reopen` and `companions`; see
[The freeze engine]({{< relref "/docs/development/framework-session" >}}#the-freeze-engine).

## See also

- [Monitor]({{< relref "/docs/tuis/monitor" >}}) and
  [Minimonitor]({{< relref "/docs/tuis/minimonitor" >}}) — where agents are
  frozen (**f**, **Z**) and frozen rows are listed, filtered and dropped.
