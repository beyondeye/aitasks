---
title: "Feature Reference"
linkTitle: "Reference"
weight: 30
description: "Keybindings, header fields, states, exit codes and configuration for ait frozenagent"
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
| `Escape` | Close the search box, else clear the selection | |
| `shift+↑` / `shift+↓` | Extend a line range from the cursor | |
| `y` | Copy the selection | Keyboard range first, else the mouse selection |
| `g` / `G` | Jump to the top / bottom | |
| `R` | Restore the agent | No confirmation |
| `p` | Re-pick the task | No confirmation; needs a task id on the record |
| `k` | Drop the record | Confirms — this deletes the capture |
| `Enter` | Open the highlighted record | List mode only |
| `j` | TUI switcher | |
| `?` | Shortcut editor | |
| `q` | Quit | |

The footer advertises only `Keys`, `Quit`, `Plain/ANSI`, `Markdown`, `Search`,
`Copy`, `Restore`, `Re-pick` and `Drop`; the rest are bound but unlisted.

While an operation is in flight on a record, that record's `R`, `p` and `k` are
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
| `restore failed: <reason> — capture kept` | kept | the attempt failed; the viewer is back |
| `restore ended — capture kept` | kept | ended with no recorded reason |
| `restore did not start — run 'ait frozenagent' or reconcile` | kept | nothing was dispatched |
| `restore still <state> after the grace — run reconcile; capture kept` | kept | still transitional |
| `record vanished` | — | the record is gone |
| `dropped — capture removed` | deleted | drop succeeded |
| `drop failed — record kept` | kept | nothing was deleted |

A viewer that returns after a failed restore shows the store's memory of it:
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
| `capture_max_lines` | `50000` | How far back into the pane's scrollback a freeze reaches. The capture is the tail of the scrollback, so a pane with more history than this keeps only its most recent lines |
| `restore_ack_grace` | `20` (seconds) | How long a restore waits for the resumed agent's SessionStart hook to acknowledge it, before falling back to confirming on liveness alone |

`restore_ack_grace` is read from the **record's own project**, not from whichever
project you happen to be viewing from, because a freeze-all spans projects.

It sets a **waiting period, not an outcome.** Raising it only helps an agent
whose acknowledgement is slow to arrive; one that never acknowledges at all —
because its CLI reports no session on startup, or because the session hook is not
installed — reaches `restored, unverified — capture kept` however long the grace
is. Nothing is lost in that case: the unverified outcome is the one that keeps
the capture.

## See also

- [Monitor]({{< relref "/docs/tuis/monitor" >}}) and
  [Minimonitor]({{< relref "/docs/tuis/minimonitor" >}}) — where agents are
  frozen (**f**, **Z**) and frozen rows are listed, filtered and revived.
