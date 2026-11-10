---
title: "Feature Reference"
linkTitle: "Reference"
weight: 20
description: "Keybindings, columns, request results, timing and launch details of the sitrep TUI"
maturity: [experimental]
depth: [advanced]
---

## Keybindings

Every key below can be rebound. Press **?** for the in-place editor, or open
[Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}}). See
[Shortcut scope](#shortcut-scope) for the scope each screen uses.

A key whose condition does not hold is hidden from the footer and does nothing.
**r** and the request keys are greyed out instead (shown, but disabled) while
their own run or request is in progress. While a dialog is open, none of the
keys below apply.

### Main list

| Key | Footer label | Action | Shown when |
|-----|--------------|--------|------------|
| `Enter` | Details | Open the highlighted item's details | An item row is highlighted |
| `d` | Show done / Hide done | Show or hide the **Recently done** and **Dismissed** groups; showing moves the highlight to the first of them | Always |
| `l` | Q&A log | Open the Q&A log | Always |
| `s` | Situation | Show or hide the situation text | Always |
| `f` | Labels | Open the label filter | Some task in the list has a label, or a filter is on |
| `F` | Clear filter | Clear the label filter | A filter is on |
| `r` | Refresh | Collect new wrap-ups, then re-check the list | Always; greyed out while a run is in progress |
| `x` | Dismiss | Dismiss the item, with a reason | The item is open or unknown |
| `p` | Pick | Launch `/aitask-pick` for the item's task, or switch to its running agent window | An open task item that names a task of this repository |
| `b` | Board | Show the item's task in the board | The item names a task of this repository |
| `z` | Trails | Show the item's task in `ait trails` | The task is known to be in at least one trail |
| `P` | Push cmd | Show the push command, with a Copy button | The item is a push reminder |
| `R` | Restore | Restore `todo.md` / `qa.md` from the last good copy | One of them cannot be read |
| `A` | Respawn agent | Start the sitrep agent again beside the TUI | The agent is not running |
| `t` | Triage | Request: `>t c<N>` | The agent runs, and the item is an open triage or unparsed-output review item |
| `a` | Ask agent | Request: `>q c<N> <question>` (asks for the question first) | The agent runs, and an item is highlighted |
| `w` | Situation text | Request: `>w <theme>` | The agent runs, and the item's context names a work area (theme) |
| `T` | Trail refresh | Request: `>tr c<N>` | The agent runs, and the item is an open watch that refresh checks through its trail |
| `n` | Pick advice | Request: `>p` | The agent runs |
| `j` | (hidden) | TUI switcher | Always |
| `?` | Keys | Shortcut editor | Always |
| `q` | Quit | Quit | Always |

`x`, `p`, `b`, `z`, `P` and the item requests `t`, `a`, `w`, `T` are also
hidden while `todo.md` cannot be read. All request keys are hidden when the TUI
does not run in a pane of the aitasks tmux server.

### Item details

| Key | Footer label | Action | Shown when |
|-----|--------------|--------|------------|
| `Enter` | Open | Open the highlighted link | The links list has focus and a link that can be opened is highlighted |
| `Tab` | Text/links | Move the focus between the text and the links list | Always |
| `Escape` | Back | Close the details | Always |
| `r` | Refresh | As on the main list | As on the main list |
| `x` `p` `b` `z` `P` | | As on the main list, for this item | As on the main list |
| `t` `a` `w` `T` `n` | | As on the main list, for this item | As on the main list |

On a details screen, `z` uses the highlighted trail row; with none highlighted
it opens the task's only trail, or a picker when there are several.

### Source viewer

| Key | Footer label | Action | Shown when |
|-----|--------------|--------|------------|
| `m` | Rendered/raw | Switch between rendered Markdown and the raw text with line numbers | A Markdown source that opened without an error |
| `Escape` | Back | Close the viewer | Always |

### Q&A log and Q&A entry

| Key | Footer label | Action |
|-----|--------------|--------|
| `Enter` | Open | Open the highlighted entry (in the log) or item (in an entry) |
| `Tab` | Text/links | Move the focus between the text and the links (in an entry) |
| `Escape` | Back | Close the screen |

### Dialogs

Dialogs have no footer; `Escape` cancels each of them.

| Dialog | Keys and buttons |
|--------|------------------|
| Dismiss | A reason field (required; `Enter` confirms), **Dismiss** / **Cancel** |
| Confirm (restore, restart the agent) | The confirm button / **Cancel**; the focus starts on **Cancel** |
| Push command | **Copy** / **Close** |
| Label filter | `Space` checks a label, `Enter` applies; **Apply** / **Clear** / **Cancel** |
| Ask | A one-line question field (`Enter` asks), **Ask** / **Cancel** |
| Trail picker | `Enter` on a trail opens it; **Cancel** |
| Result panel | **Close** |

A click in any list only selects the row; `Enter` opens it.

## Shortcut scope

| Screen | Scope |
|--------|-------|
| Main list (and the app-level keys shown on item details) | `sitrep_tui` |
| Item details | `sitrep_tui.detail` |
| Source viewer | `sitrep_tui.viewer` |
| Q&A log | `sitrep_tui.qa` |
| Q&A entry | `sitrep_tui.qa_entry` |

The dialogs have no scope of their own. The pick dialog is the shared agent
command dialog of the other TUIs. A rebind of `p`, `b`, `P`, `x`, `r`, `t`, `a`
or `T` changes the key the items' **How** lines name.

## The main list

### Header

The first line is `Sitrep · <repository root>`. The second line is
`<state> · read HH:MM:SS · <agent>`, followed by
`· refreshed HH:MM ok` (or `with errors`) once a collect-and-re-check run has
finished:

- `<state>`: `no items yet`, or `N items · M open in Now` (`1 item` for one). While the done and
  dismissed groups are hidden it adds `· N done, M dismissed hidden`. While a
  label filter is on it adds `· filtered by: <labels> · N hidden (F clears)`.
- `read`: the time of the last read of the list.
- `<agent>`: `agent: running`, `agent: not running — press A`, or
  `agent: unknown` (the tmux query failed, or the TUI does not run in a pane of
  the aitasks tmux server).

When `todo.md` cannot be read and no good copy was read earlier, `<state>` is
`store unusable`.

### Groups

In this order: **Now** (stored as *Pick now*), **Next**, **Waiting**, then
**Recently done** and **Dismissed** while `d` shows them. Each group heading
shows its count, `(0)` included.

### Columns

| Column | Shows |
|--------|-------|
| Item | The item id (`c<N>`) |
| Checked | `—` (never checked), `just now`, `Nm ago`, `Nh ago`, `Nd ago`, `Ny ago`, `long ago`; `invalid` for an unreadable time, `future` for one more than a minute ahead |
| Pri/Eff | The task's priority and effort as `hi`, `med` or `lo` (other values cut to three letters, an empty one `?`), e.g. `hi/med`; `—` when the task file is not found; blank for an item that names no task of this repository |
| Created | The task's `created_at`: `HH:MM` when it is today (`today` for a date without a time), `MM-DD` in the current year, `YYYY-MM-DD` otherwise; `—` when the file is missing or has no `created_at`, `?` when it cannot be read; blank for an item that names no task of this repository |
| What to do | The item's "What to do" line (below), cut to the pane's width |

### What to do

Each item gets one "What to do" line (the list column and the first line of its
details) and one "How" line (in its details). They depend on the item's kind
and state. The keys named are the default ones; a rebind changes them.

| Item | What to do | How |
|------|-----------|-----|
| Open triage question | `Triage <task>'s wrap-up: decide which closing notes become actions or watches` | `t` sends `>t c<N>`; typing `>t` in the agent triages every open wrap-up |
| Open unparsed-output review | `Review unparsed agent output …` | `t` sends `>t c<N>` |
| Other open question | `Decide: <title>` | `a` asks the agent (`>q c<N> …`) |
| Open task of this repository | `Pick t<N> (status: …): …` | `p` launches `/aitask-pick`, `b` shows it in the board |
| Open task of another project | `Pick <project>#<N> …` | Run `/aitask-pick` in that project |
| Open task without a task reference | `Pick: <title>` | Pick it with `/aitask-pick <id>` |
| Open push reminder | `Do: <title>` | Push it yourself; `P` shows the command; a re-check closes it once the commit is on the remote |
| Other open action | `Do: <title>` | Do it yourself; `x` dismisses it with a reason |
| Open watch checked through a trail | `Waiting on: <title> — nothing to do now` | `r` re-checks its trail; `T` has the agent refresh the trail (`>tr c<N>`) |
| Other open watch | `Waiting on: <title> — nothing to do now` | Refresh does not check it; `a` asks the agent, `x` dismisses it |
| Done / dismissed | `Done: <title>` / `Dismissed: <title>`, with the outcome | Nothing to do |
| Unknown, re-checkable | `Unknown — needs a re-check: <title>` | `r` re-checks it |
| Unknown, not re-checkable | `Unknown — needs a re-check: <title>` | `a` asks the agent to look at its sources, or `x` dismisses it |

The **How** lines name the request keys even while the agent is not running;
the keys themselves appear only once it runs.

## Item details

The title is `c<N> · <title>`. The body, in order:

- **Item**: **What to do**, **How**, and **About** when the item has a reference
  (`push of branch <b> (commit <sha>)`, `task <N> in project <p>`, or the
  reference itself).
- For a task item: **Priority** (`<priority> · effort <effort>`), **Task status**
  (`(archived)` when the task is archived) and **Created** (the stored
  `created_at`), or `task file not found`; and **Trails**: the trails with
  their waves, `none`, `looking…` until the first scan, or `unknown (<reason>)`.
  A failed or partial scan never reads as `none`.
- **Checked** (`never`, or the time and its age) and **Outcome**.
- **Context**: **Background**, **Origin** (Agent, Task, Commit, Date, Skill,
  Pane), **Theme**, and for an unparsed-output review its case and the
  `ait sitrep case show <case>` command. `No context entry.` when the item has
  none.

### Links

| Link | Enter opens |
|------|-------------|
| `Task description: t<N> (<path>)` | The task file, rendered |
| `In trail: <name> (<handle>) — wave <n>` | `ait trails` on that trail, with the task's card focused |
| `Closing message`, `Workflow result`, `Retained text` | The retained text the harvest kept, at its lines |
| `Excerpt of the unparsed output`, `Raw input (review case)` | The excerpt, or the whole kept input of a review case (verified against its checksum first) |
| `Review case: origin record` / `parser analysis` / `review record` | The case record |
| `Task t<N>`, `Plan of t<N>` (`(archived)` when archived) | The task or plan file, rendered |
| `File <path>` | The file; a Markdown file rendered |
| `Commit <sha>` | `git show --stat` of the commit |
| `Trail <handle>` | The trail's stored content and its drift check |
| `Web link <url> (shown, never opened)` | The address only; it is never opened |
| `Related: item c<N> — <title>`, `Mentioned by item c<N> — <title>` | That item's details |
| `Q&A entry <time>` | That Q&A entry |

A source that points at lines (`, line N`, `, lines A–B`) or that fails to open
starts as raw text with line numbers, scrolled to the line. Links inside a
rendered file are never followed. A file larger than 256 KiB shows its first
256 KiB. A source the TUI will not open shows `Not followed: <reason>`. The
harvest's identity receipts (KEY sources) stay in the store but are not listed.

## Requests

| Key | Typed into the agent | Applies to |
|-----|----------------------|------------|
| `t` | `>t c<N>` | An open triage item, or an unparsed-output review item |
| `a` | `>q c<N> <question>` | Any item |
| `w` | `>w <theme>` | An item whose context names a work area |
| `T` | `>tr c<N>` | An open watch that refresh checks through its trail |
| `n` | `>p` | The whole list |

These are the request lines the [`/aitask-sitrep`]({{< relref "/docs/skills/aitask-sitrep" >}})
skill documents. The question in the ask dialog is one line of at most 300
characters, with no tabs or control characters, and it may not end with an
`@mention` (that would open the agent's file picker, which would take the
Enter). Runs of spaces are collapsed to one.

A request key works only while the agent is running, and one request at a time:
a second press while one is being delivered is refused, never queued. Every key
re-checks the item first: when it changed since the details were opened, nothing
is sent.

Supported agents are Claude Code, Codex CLI and OpenCode, whose input boxes the
TUI knows how to read. Any other agent is refused before anything is typed.

## Request results

Every result shows a short message. Every result except `submitted` also opens a
panel with the request line, the result and its detail. The panel border is red
only for `unknown`.

| Result | Message | Typed / submitted | What to do |
|--------|---------|-------------------|------------|
| `submitted` | "Sent to the sitrep agent" | Typed and submitted | Nothing |
| `typed_not_submitted` | "Typed into the sitrep agent but NOT submitted — check its composer" | Typed, not submitted. Detail `composer_changed`: the input box no longer equals the request. `submit_unconfirmed`: the Enter's effect could not be confirmed while the request was still there | Read the whole input box; submit only when it holds exactly the request |
| `typed_not_submitted:in_mode` | "Typed into the sitrep agent but NOT submitted: its pane is in a tmux mode (e.g. scrolled back). The request is waiting in its composer — leave the mode and press Enter there" | Typed, not submitted | Leave copy mode, read the input box, then press Enter |
| `typed_not_submitted:mode_unreadable` | "Typed into the sitrep agent but NOT submitted: its pane mode could not be read. The request is waiting in its composer" | Typed, not submitted | Read the input box, then press Enter if it holds exactly the request |
| `skipped` | "Not sent: the sitrep agent pane changed just before typing (nothing typed)" | Nothing | Press the key again |
| `refused:<reason>` | "Not sent: …" with the reason below | Nothing submitted; nothing typed except for `identity_changed` | Remove the reason, then press the key again |
| `unknown` | "Could not verify what happened — look at the sitrep agent pane" | **May have been submitted**, including after the Enter was sent | Read the agent's conversation before you retry |

Refusal reasons:

| Reason | Message |
|--------|---------|
| `not_ready:dialog` | the agent is waiting for an answer to a dialog |
| `not_ready:draft` | the agent's composer holds unsent text (left untouched) |
| `not_ready:working` | the agent is working |
| `not_ready:unknown` | the agent's state could not be read (also: an agent the TUI cannot read) |
| `not_ready:in_mode` | the agent pane is in a tmux mode (e.g. scrolled back) |
| `not_ready:mode_unreadable` | the agent pane's mode could not be read |
| `identity_changed` | the agent was replaced before the Enter. The line had already been typed into the replaced agent: check the new agent's input box before you retry |
| `no_agent` | no running sitrep agent pane for this repository |
| `frozen` | the sitrep agent is frozen |
| `dispatch_failed` | the request could not be handed to tmux (nothing typed) |
| `invalid_request` | the request is not a single plain line |

### Recovering from a result

The [how-to]({{< relref "/docs/tuis/sitrep/how-to" >}}#how-to-hand-work-to-the-sitrep-agent)
gives the same rules in steps: never press Enter in the agent's pane without
reading its whole input box first; treat `unknown` as possibly sent; and after
`identity_changed`, look for a leftover line before you retry.

## Action results

| Situation | Message |
|-----------|---------|
| The list cannot be read | "The store is unusable — press R to restore it" |
| The item is gone | `c<N> is no longer in the store` (the details close) |
| The item changed since its details opened | `c<N> changed since these details were opened — details refreshed; press <key> again` |
| A collect-and-re-check run is already going | "A harvest + refresh is already running" |
| A dismissal raced another change | The dialog opens again: `c<N> changed since you looked (rev A→B); check it and confirm again.`; when the item is no longer open: `c<N> changed meanwhile and is now <state> — nothing dismissed` |
| The list's writer is busy | "The store is busy (another writer holds it) — confirm to retry." |
| Restore, nothing damaged | "The store reads fine — nothing to restore" |
| `b` / `z` outside an aitasks tmux session | `Not in an aitasks tmux session — run: ./ait board --focus <id>` / `… run: ./ait trails --trail <handle> --task <id>` |
| No tmux session runs the project | "No tmux session runs this project — start one with: ait ide" |

The collect-and-re-check panel has one line for each half: `Harvested: N added,
M existing`, `Nothing new to harvest` or `Harvest failed: <why>`, then
`Refreshed: N checked, M changed`, `Nothing to refresh (<reason>)` or
`Refresh failed: <reason>`. The re-check runs even when the collection failed.

## Timing

- The list is re-read every 2 seconds; it is parsed again only when `todo.md` or
  `qa.md` changed. The age labels update on every read.
- The agent's state is checked every 3 seconds.
- Trail membership is scanned in the background after the list changes, when a
  task item's details open, and every 60 seconds.
- Collect-and-re-check runs once at startup (reported in a short message, no
  panel) and on `r`.

## Launch and environment

| Launch | Notes |
|--------|-------|
| `ait sitrep` | Opens the sitrep window with the TUI below the agent, or switches to it; adds the TUI when it is missing |
| `ait sitrep tui [--root <path>]` | Runs the TUI alone. `--root` defaults to the current directory; a linked task worktree maps to its main worktree. An empty value or a path with a `..` segment is refused |

- **Store** — `<main worktree>/.aitask-sitrep/` (`todo.md`, `qa.md`), the same
  store the sitrep agent and the harvest use. The TUI writes it only through the
  list's writer.
- **Damaged files** — the TUI keeps the last good view, and a red banner says
  `Store unusable: <error>` (or `Q&A log unusable: <error>`) and
  `Press R to restore the last good generation.`
- **Missing packages** — when `textual` or `pyyaml` is missing, the launcher
  stops and tells you to run `ait setup`.
- **Outside tmux** — the header reads `agent: unknown`, and the request keys
  and `A` are hidden (the agent's state cannot be read there). Run `ait sitrep`
  from inside tmux to start or reach the sitrep agent. `b` and `z` still work
  and name the command to run (`./ait board --focus <id>`,
  `./ait trails --trail <handle> --task <id>`).
