---
title: "How-To Guides"
linkTitle: "How-To Guides"
weight: 10
description: "Task-oriented guides for using ait minimonitor"
maturity: [stable]
depth: [intermediate]
---

### How Minimonitor Is Auto-Spawned

Minimonitor is meant to be auto-spawned — you almost never start it yourself. Every ait TUI that launches a new code agent window also creates a minimonitor split next to it:

- [`ait board`]({{< relref "/docs/tuis/board" >}}) — when you pick a task and launch its agent (action menu or agent command screen).
- [`ait codebrowser`]({{< relref "/docs/tuis/codebrowser" >}}) — when you launch an agent from a code file or the history screen.
- [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}) — when you press **n** on an agent card to pick its next ready sibling task, which creates a new agent window.
- The TUI switcher's explore launch — when it creates an agent window for an explore target.

In every case the flow is the same: the launching TUI creates a new tmux window named `agent-...`, then the auto-spawn helper creates a horizontal right-split inside that window and runs `ait minimonitor` in it. The helper skips the split if the window name does not start with the configured agent prefix (default `agent-`) or if a monitor/minimonitor is already running in the window.

> **Auto-despawn:** minimonitor closes itself automatically when the agent pane it sits next to exits. On every refresh cycle it checks the panes in its own tmux window; the first refresh after the agent pane has gone (so there is no pane left other than minimonitor itself) triggers an `exit()` and the minimonitor pane closes. A 5-second grace period after startup prevents premature exit on cold launch. You never need to `ait minimonitor` after an agent finishes — a new one will spawn with the next agent you launch.

### How to Start Minimonitor Manually

Manual launch is an escape hatch for edge cases (an agent pane you started by hand, a killed sidebar you want to bring back). From inside a tmux session, run:

```bash
ait minimonitor
```

This starts minimonitor in the current tmux pane.

> **Single-instance guard:** `ait minimonitor` checks the current tmux **window** for any existing monitor or minimonitor process. If one is already running in the same window, the new invocation prints a short message and exits. The guard is per-window, so you can still have minimonitor split alongside each of several agent windows in the same session.

### How to Read the Agent List

Minimonitor shows a single scrollable list, **agent panes** first (windows whose names match the configured agent prefix — default `agent-`). By default the list aggregates agents from every aitasks tmux session on the current tmux server; `── <session_name> ──` divider rows separate agents that belong to different sessions.

Within each session, agents are ordered by their tmux **window name** — not by the order the windows sit in the session, which is just the order you happened to launch them in. The comparison is natural rather than alphabetical, so runs of digits compare as numbers: `agent-pick-2` comes before `agent-pick-9`, `agent-pick-10` and `agent-pick-20`. A child task's window follows its parent's (`agent-pick-100`, then `agent-pick-100_1`, then `agent-pick-101`), and two windows that share a name fall back to window index and then pane index, so the order is always stable across refreshes. The session is what groups first: an agent in a later session never rises above an earlier session's agents, however its name sorts. [`ait monitor`]({{< relref "/docs/tuis/monitor/reference" >}}#pane-order) uses the same rule — the two TUIs share one ordering key and cannot disagree.

Any pane that is **not** an agent — a shell, a log, a window you renamed off the `agent-` prefix — follows below them under a bold `── other (n) ──` section header. Only that section is headed; the agent list needs none, because the bar at the top already carries the agent count. Session dividers still apply within each section. Windows classified as TUIs (board, codebrowser, settings, brainstorm, and the monitors themselves) are not listed, and neither are companion panes — a shadow agent, or another minimonitor.

Each agent card in the list shows:

- A prioritized mark: **★** when the agent is marked, dim **☆** when it is not. In the list this is **display only** — it shows marks set from [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}) or from another project, and `Space` here marks the *followed* agent instead (see [How to Mark an Agent as Prioritized](#how-to-mark-an-agent-as-prioritized))
- A status dot: **green** when the agent has produced recent output, **magenta** when it is waiting for your input, **blue** when its task is finished, **yellow** when it is idle
- The agent window name (truncated to 20 characters on narrow layouts)
- A matching label: `PROMPT <n>s` when the agent is waiting for you, `DONE <n>s` when its task is finished, or `IDLE <n>s` when the pane has been quiet longer than `tmux.monitor.idle_threshold_seconds` (default 5 seconds). `DONE` reflects the pane's *task* — its status reads `Done`, or it has been archived — so an agent still printing output after its task landed reads `DONE`, while an agent waiting on you reads `PROMPT` even when its task is done
- For agents whose window name carries a task ID, a second dimmed line showing the task's title
- For those same agents, a third dimmed line carrying the task's **workflow phase** and its **gate summary** together — `IMPLEMENT ⏸ · 1/4 1p 1f`. Either half may be empty; the line is omitted only when both are

The phase is **advisory**: it is a hint about where the task sits in its workflow, and it never gates a key, a spawn, or anything else you can do here.

| Phase | Meaning |
|-------|---------|
| `PLAN` | The task is in planning |
| `IMPLEMENT` | The plan is approved and being implemented |
| `POSTIMPL` | Implementation is done; the task is at review, merge or archival |
| `unknown (rec off)` | Cannot tell — this task's execution profile does not record gates |
| `unknown (ledger)` | Cannot tell — only the gate ledger could be read; the agent's screen showed no workflow prompt |
| `unknown ⏸` | Cannot tell — the agent is waiting on you, but the phase did not resolve |

A trailing **⏸** on any phase means the agent is waiting for your input. The `unknown (…)` values are a real "cannot tell" state, named so you can see *why* — they are not the same as having no phase. When no phase resolves at all and the task has no gate counts either, the line is simply absent.

At narrow pane widths the line sheds detail in a fixed order, so the counts are what survive: first the gate summary abbreviates (`1/4 pass, 1 pending, 1 failed` → `1/4 1p 1f`), then the phase is clipped, then the phase is dropped entirely.

A card in the **other** section is deliberately much plainer — a dim `○`, the window name, and the pane's current command (`○ zsh  nvim`). It carries no mark, status dot, status label, task title or gate line, because none of those mean anything for a pane that is not an agent, and the ~40-column sidebar has no room to spare for them.

The header bar at the top of the pane shows either `multi: 2s · 5a 1 awaiting 2d 1 idle` when the multi-session view is active, or `<session>  5 agents 2d 1 idle` when the view is restricted to the attached session. The three counters — waiting for input, done (shown compactly as `Nd`), and idle — each disappear when zero, and every agent falls into exactly one of them. See [How to Toggle the Multi-Session View](#how-to-toggle-the-multi-session-view) below.

### Mouse Support

Minimonitor supports full mouse interaction in addition to the keyboard shortcuts:

- **Click an agent card** — focus that card (alternative to **Up** / **Down**).
- **Scroll wheel** — scroll the agent list.
- **Drag the scrollbar** — drag the thumb to move through a list too long for the pane.
- **Click dialog buttons** — buttons in the task-info dialog and TUI switcher overlay are clickable.

**Scrolling to the bottom pins the list there.** Once you reach the end of the
list — by wheel, or by dragging the scrollbar thumb to the end of its track —
minimonitor keeps you at the bottom as the list refreshes, so agents
appearing, disappearing, or growing an extra status row do not push the view
away from the newest entries. Scrolling back up releases the pin and your
position is held instead; reaching the bottom again re-engages it.

All keyboard actions documented below remain available.

### How to Navigate the Agent List

- **Up** / **Down** — Move focus between agent cards within the list.
- The footer hint summarizes the navigation and action keys for the current layout.

When minimonitor is shown as a side split next to an agent, it auto-selects the card for that agent whenever the minimonitor pane regains terminal focus — so the focused card always reflects the neighbor you are working with, unless you explicitly moved focus somewhere else.

### How to Focus the Sibling Agent Pane

Minimonitor is designed to live beside an agent pane in the same tmux window. Pressing **Tab** moves **tmux focus** to that sibling pane (the first non-minimonitor pane in the same window), so your next keystrokes go directly to the agent. This is the fastest way to jump from glancing at the status sidebar to typing into the agent it sits next to.

If minimonitor is the only pane in its window (no sibling to target), Tab shows a notification and does nothing.

### How to Focus Minimonitor from the Agent Pane (native tmux)

**Tab** only goes one way: minimonitor → agent pane. There is no built-in shortcut for the opposite direction. Because minimonitor lives as a second pane inside the agent's tmux **window**, you move focus the other way (agent pane → minimonitor) with tmux's own pane-switching keys — the same keys you would use to move between any two panes in one window:

- **`Ctrl-b o`** — cycle tmux focus to the next pane in the window.
- **`Ctrl-b` + an arrow key** — move focus directionally to the adjacent pane.

This also saves you from clicking the minimonitor pane to activate it. `Ctrl-b` is the default tmux prefix; if you remapped your prefix, substitute your own. Once you are comfortable with these native shortcuts you can use them for **both** directions instead of Tab if you prefer.

This intra-window pane switching is specific to the minimonitor split — the other ait TUIs each occupy their own full tmux window, which you reach with the [TUI switcher](#how-to-jump-to-another-tui) (press **`j`**).

### How to Send Enter to the Sibling Agent

When a code agent is waiting for you to press Enter (for example, it just asked a clarifying question), you can unblock it without moving tmux focus:

1. Make sure minimonitor has terminal focus
2. Press **Enter**

Minimonitor sends a single `Enter` keystroke to the sibling pane via `tmux send-keys`. Tmux focus stays on minimonitor, so you can keep watching the agent status while it processes the input.

### How to Switch to the Selected Agent

To jump your tmux session focus to the **selected** card's agent (which may be in a different window from the minimonitor you're in):

1. Focus the agent's card with Up/Down
2. Press **s**

Minimonitor asks tmux to switch focus to the agent's window (preferring the companion pane when the card is next to its own minimonitor). A notification confirms the switch.

### How to Show Task Info for an Agent

For agent panes whose window name carries a task ID (e.g., `agent-t42-claudecode`), minimonitor can open the same task detail dialog used by the other TUIs:

1. Focus the agent's card with Up/Down
2. Press **i**

The task cache is refreshed and the task detail dialog appears with the task's metadata and content. If the focused card has no task ID in its window name, a warning notification is shown instead.

The pane minimonitor **follows** — the one pinned at the top — is never selectable, so **i** cannot reach it. Press **I** (Shift+i) instead: it always opens the task detail dialog for the followed agent, whichever card happens to be highlighted. If this window has no agent to follow, a warning notification is shown instead.

The pinned card's header names what it is following: `── this agent ──` when that pane is classified as an agent, and `── this window ──` when it is not. A window you renamed off the `agent-` prefix still gets a panel, headed `── this window ──`, so the uncategorized state is visible rather than looking like a missing agent.

> **Note:** the pinned card is a static identity line — it shows the window name
> and task title, but never a live status badge, so it does not turn `DONE` when
> the followed agent's task lands. Use the scrollable list, or
> [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}), to see that. The header
> and name are frozen when the panel is first built, so renaming the window
> afterwards does not change them.
>
> Two things on the pinned card *do* stay current. Its prioritized mark
> (**★** / **☆**) is not a status badge but a note you left yourself, and it can
> change without the agent changing at all — you marked it from another project,
> or it expired. Its **workflow phase** is kept current too: this panel *is* the
> followed agent, and the shadow companion you launch from it picks its review
> mode from that phase, so showing it only on the list rows — which exclude the
> followed agent by construction — would put it everywhere except the one place
> it is for. The panel carries the phase and deliberately **not** the gate
> summary that shares that line on the list rows.

### How to Pick a Task by Number

When an agent finishes it usually names the tasks it created, or the one to pick next, as bare numbers. Press **p** to act on one without leaving the window:

1. Press **p** and type the task number (`1310`, or `1310_2` for a child task — a leading `t` is accepted)
2. Press Enter; the task's details open, with **OK**, **Move to column** and **Cancel** buttons and a **kill followed agent** checkbox
3. Choose **OK**, and the usual launch dialog appears so you can pick the coding agent, model, and where the new window goes

The checkbox is unchecked by default. Tick it to close down the agent this minimonitor follows once the new one has launched — the new agent always starts first, so the window teardown can never strand it. Leave it unticked to run both side by side.

**Moving the task to a board column instead.** Not every task you look up is one to start now. **Move to column** opens a picker listing the board's columns, including "Unsorted / Inbox", with the task's current column marked, plus a **`＋ New column…`** entry. Choosing an existing column moves the task to the bottom of it; choosing `＋ New column…` asks only for a title — the color is assigned automatically and the column is added at the right-hand end of the board — and then moves the task into it. The move is written straight to the task file, so it appears in `ait board` on its next refresh. The button is offered for parent tasks only: child tasks have no card on the board. When the [multi-session view](#how-to-toggle-the-multi-session-view) is on, the move targets the followed pane's **own** project, not the one this minimonitor was started in.

Unlike **n**, which only offers the followed task's next *ready sibling*, **p** reaches any task. That includes tasks that are not cleanly pickable: if the target is not `Ready`, or is still waiting on an unfinished dependency, the dialog says so and the confirm button reads **Launch anyway** instead of **OK**. Minimonitor still lets you launch it — it just never does so silently. It also warns when an agent for that task is already running in this session.

If the number does not look like a task id, or no such task exists, a warning notification is shown and nothing is launched.

### How to Launch a Shadow Agent

Press **e** to launch a *shadow agent* next to the code agent you are following — an advisory companion that reads that agent's terminal output and helps you make sense of it. By default the shadow opens as a new pane in the **same tmux window** as the followed agent, so it sits right beside the work it is watching.

The shadow is read-only and advisory: it can explain what the agent is doing, help you answer a prompt the agent is stuck on, critically interrogate a plan before you approve it, or review the code the agent actually wrote — but it never types into the followed agent's pane. You stay the driver.

Like minimonitor itself, the shadow pane is a companion: it never appears in the agent list, and it closes automatically when the agent it shadows exits. Only one shadow runs per followed agent — if a shadow is already running for the agent you are following, a second **e** is refused with a notification.

For what the shadow can do and how to drive it once it is running, see the [Shadow Agent]({{< relref "/docs/workflows/shadow-agent" >}}) workflow guide.

### How to Pick Shadow Concerns

When the shadow agent interrogates a plan, reviews an implementation, or diagnoses errors, it emits a structured **concern block** alongside its prose. You can forward a subset of those concerns to the followed agent without retyping them:

1. Make sure a shadow is running for the agent (press **e** if not)
2. Press **c**

Minimonitor reads the shadow pane, parses its concern block, and opens a checklist modal of the concerns — each tagged with a priority (`high`, `medium`, or `low`) and the plan region it targets. For a concern that priced itself, that badge is derived from the concern's own impact vector rather than the priority the shadow typed, and a `≠` beside it means the two disagree; a concern that priced nothing keeps its stated priority and shows no `≠`. Tick the ones you want, confirm, and minimonitor copies them — with a short preamble — to your clipboard, ready to paste into the followed agent. Nothing is written to the clipboard until you confirm, and minimonitor never types into the agent itself: you stay the driver.

When the block classifies its concerns — plan reviews and implementation reviews both do — the modal splits the list into **Needs addressing** and **Informational**. The second section holds findings the shadow reports for your judgement without asking for a change; they are dimmed so what needs attention reads first, and you tick them individually like any other row. A review with no informational findings shows no section headers at all. If some lines in the block could not be parsed, a warning above the list says how many, so a short list is never mistaken for a complete one. If *none* of them could be parsed, minimonitor says the shadow emitted a block that yielded nothing forwardable — rather than reporting no concerns at all.

**Reading a row's trade profile.** A concern that priced itself carries a compact **trade profile** — `▲robus ▼simpl E:lo`: what it would improve, what that would cost, and the effort. In minimonitor's companion pane the row is three lines for exactly this reason — the mark, badge and region on the first, the body on the second, and the profile on its own third line. A concern that priced nothing has no profile and stays a two-line row, exactly as before. The one-line decision reminder that a wide picker prints above the list needs about 80 columns and 24 rows, so a companion pane does not show it; the per-row profile is the data, and [Read the trade profile]({{< relref "/docs/workflows/shadow-agent" >}}#read-the-trade-profile) has the glyph key and the forward / spin-off / reject rule.

**Seeing the whole vector.** The row degrades to one improve entry, one worsen entry and the effort, with five-character labels. Where the dialog has the rows to spare, a **detail panel** below the list spells out the focused concern's vector — one line per entry, full dimension names — and re-fills as you move with ↑/↓. It needs rows more than columns, so a tall companion pane gets it while a short one does not: a 40x20 pane keeps the key hints and the compact profile instead. In a narrow pane it shows the names without their magnitude words, since the arrow colour already carries the magnitude. See [See the whole impact vector]({{< relref "/docs/workflows/shadow-agent" >}}#see-the-whole-impact-vector).

**Rejecting a concern.** Each row carries one of four dispositions, and they are mutually exclusive: unmarked (`□`), marked to forward with **Space** (`✓`), marked **rejected** with **r** (`✗`, and the row dims), or marked to **spin off** with **t** (`»` — see [How to Spin a Concern Off as Its Own Task](#how-to-spin-a-concern-off-as-its-own-task)). Rejecting says *stop raising this for this task*, so the shadow drops it from later review rounds — see [Reject a concern so it does not come back]({{< relref "/docs/workflows/shadow-agent" >}}#reject-a-concern-so-it-does-not-come-back) for what the shadow does with it.

Press **R** to review what is already rejected for this task: **Space** marks an entry to bring back, **Enter** hands those marks to the picker, and **q** or **Esc** closes the view. **R** does not always open a list — if nothing is rejected for this task yet it says so, and if the pane has no task id it warns that the rejection store is unavailable, which tells you *before* you confirm that rejections made here cannot be kept.

**Nothing is written until you confirm the picker.** Rejections and un-rejections are staged while you work; confirming with **Enter** or **OK** is what saves them, and cancelling with **Esc** discards both. When the pane has no resolvable task id, minimonitor warns that the rejections were not persisted rather than dropping them quietly. A busy or unusable store is reported too, so a rejection never fails silently.

**Seeing what was lost.** When that warning appears, press **u** to open a read-only view of the exact lines the parser could not use, together with the raw block they came from. That is what lets you tell a marker the shadow wrapped across too many rows from a genuine mistake in what it wrote — and report the latter. When *no* line parsed there is no checklist to show the warning beside, so **u**'s view opens straight away instead. Press **q** or **Esc** to close it and return to the checklist with your ticks intact.

The picker adapts down to narrow companion panes: at 30 columns and below it drops its OK/Cancel buttons and switches to a compact key hint (confirm with **Enter**, cancel with **Esc**). 24 columns is the narrowest width it is designed for — below that the concern block's own markers wrap in the shadow pane and there is nothing left to parse.

It adapts to *short* panes separately from narrow ones. The picker normally leaves a margin around itself, but on a pane too short to hold its content that way it uses the full height instead, so the key hints stay on screen for a picker whose content fits the pane at all. A pane carrying both a staleness warning and an unparsed-lines warning in around 20 rows can still run out of room — widen or lengthen the pane if the hints disappear.

If no shadow is running, pressing **c** tells you to launch one with **e**; if the shadow has not raised any concerns yet, minimonitor says so and does nothing.

> **Auto-offer:** when the shadow produces a fresh concern block, minimonitor proactively surfaces a `Shadow raised 2 concern(s) — press 'c' to pick` toast — once per block — so you don't have to poll the shadow pane for it. The count is of concerns needing attention; any informational ones are noted separately in the same toast, and the review round is named as a `(round N)` suffix when the block carries one.
>
> **A new round re-offers concerns you have already seen, and that is the point.** Each review round re-derives the shadow's findings from scratch, so the offer is keyed on the round as well as the concerns themselves. A repeat round raising an identical list means the shadow re-reviewed and still stands by it — news, not noise — so it is offered again rather than silently suppressed.

**Clean and unreadable rounds.** A review that finds nothing still records the round, and pressing **c** then reports `Clean review (round 3) — no concerns`. If the shadow emitted a block that carries a round but no readable concerns — still mid-stream, or with content minimonitor had to drop — you get a warning and the **raw block** instead. That is deliberate: reporting it as "no concerns" would hide output the shadow did produce, and the raw view is what lets you tell a rendering mishap from a real mistake in what it wrote.

> **Configuration:** two settings control the shadow, both editable in [`ait settings`]({{< relref "/docs/tuis/settings" >}}):
>
> - **Placement** — `tmux.shadow_same_window` (Tmux tab): `true` (default) splits the shadow into the followed agent's window; `false` opens it in its own window.
> - **Agent and model** — the `shadow` row on the Agent Defaults tab selects which coding agent and model the shadow runs as.

### How to Spin a Concern Off as Its Own Task

Not every concern belongs in the plan you are reviewing. Some are real but secondary, and folding all of them in is how a steerable plan turns into a sprawling one. In the concern picker, **t** marks the focused concern `»` — *keep this, but as its own task*. It is mutually exclusive with forwarding and rejecting, and unlike a rejection the row is not dimmed: the concern is being kept, just somewhere else.

When you confirm the picker, each marked concern becomes a **draft task** in `aitasks/new/`, carrying the concern's own priority, a `shadow-concern` label, and a link back to the task under review. Drafts are not tasks yet — they claim no number and touch no branch, so nothing is committed and an unwanted one is removed with `rm`. Finalize the ones you want with `ait create`.

Minimonitor reports the **paths** it created, because drafts have no id to report. `aitasks/new/` is a shared drop directory, so the toast also gives you a selector for exactly this batch:

```
2 concern(s) parked as drafts — finalize with 'ait create':
  aitasks/new/shadow_error_handling_a1b2c3d4_1.md
  aitasks/new/shadow_retry_logic_a1b2c3d4_2.md
(this batch: ls aitasks/new/*a1b2c3d4*)
```

A spun-off concern is also recorded as handled for this task, so the shadow stops raising it in later rounds — it is being tracked elsewhere now. If the drafts are created but that record cannot be written, minimonitor says so explicitly rather than reporting success: the drafts exist, the concern will come back next round, and spinning it off again would create duplicates.

### How to Edit the Payload Before It Is Copied

Ticking rows decides *which* concerns are forwarded. What actually gets pasted into the coding agent is prose, and prose sometimes needs a hand: a concern's body may be twice as long as the part that matters, the preamble may not suit this particular hand-off, or you may want to add a sentence of your own ("only the second one — the first is already handled in the plan").

Press **e** in the concern picker to open the outgoing payload in an editor, showing exactly the text that will land on the clipboard. It is a normal text box: arrow keys move, **shift+arrows** select, typing replaces the selection, and **ctrl+z** undoes. **ctrl+s** saves and returns to the picker; **Esc** returns without keeping the edit. Confirming the picker then copies your text rather than the generated payload, and the toast says "Edited payload copied to clipboard" so you can tell which one you got.

Three behaviours are worth knowing:

- **`e` needs something to edit.** With no row ticked to forward there is no payload, so `e` says so instead of opening an empty box.
- **An emptied editor is refused.** Saving a blank buffer would silently fall back to the generated text, so `ctrl+s` declines and tells you; use **Esc** if you want to abandon the edit.
- **Changing the ticks after editing discards the edit.** Your text was written against a particular selection, so if you tick or untick a row afterwards the picker copies the regenerated payload and warns you that the edit was dropped — it never quietly pastes text that disagrees with the rows you marked. (Toggling a row off and straight back on changes nothing, so the edit survives that.)

Editing only affects the clipboard. Rejections and spin-offs always record the concern's original text, because the shadow matches its own records against freshly parsed concerns on the next round.

### How to Run the Auto-Recheck Loop

Reviewing a plan with a shadow is a loop: the shadow raises concerns, you forward some, the agent revises, and then the shadow has to re-read and review again. Press **L** to have minimonitor drive that last step for you. While the loop is armed, minimonitor watches the followed agent; once it has produced real work and settled back at a prompt, minimonitor sends a single-line recheck into the **shadow** pane, naming the round to review next.

Press **L** again to disarm. A status line shows the loop's state the whole time it is armed:

| Banner | Meaning |
|--------|---------|
| `⟳ auto-recheck ARMED` | Watching the followed agent |
| `⟳ waiting for shadow to settle` | The agent is ready for a recheck, but the shadow is still busy — the loop holds rather than interrupting it |
| `⟳ auto-recheck: delivering…` | Sending the recheck |
| `⟳ recheck #2 sent — waiting for shadow` | Sent; waiting for the shadow to re-read before arming the next round |

When the loop disarms itself — the agent or the shadow pane disappeared, or the shadow was swapped for one it cannot read — the banner clears and a warning names the reason. An open picker pauses the loop rather than disarming it.

**Minimonitor only ever writes into the shadow pane.** The followed agent is never typed into: the loop automates asking the shadow to look again, not answering on your behalf. Forwarding concerns stays a clipboard step you confirm.

**Where the loop can run.** Two independent requirements, and both are checked when you press **L**:

- The **followed** agent can be any of the supported coding agents — Claude Code, Codex CLI, or OpenCode. Each one had to be qualified separately, because the loop injects keystrokes rather than merely reading: minimonitor has to be able to tell real work from a redraw caused by moving the selection in whatever dialog that agent is showing. Arming for an agent that has not been qualified refuses, and the message names the ones that have.
- The **shadow** can likewise be any of the supported coding agents, so any pairing works — a Codex agent watched by a Claude shadow, or the reverse. Minimonitor needs to recognise when that shadow is idle before it will type into it.

Other refusals are about state rather than support, and each says which: no followed agent pane; no shadow pane yet (launch one with **e**); or the shadow's agent could not be identified yet, which is usually a timing answer worth retrying a moment later rather than a permanent no.

**The manual recheck still works, and is sometimes needed.** The loop notices the agent working by watching its pane, and a revision that leaves the visible output byte-identical and grows no scrollback is invisible to it. When that happens the loop simply does not fire — just ask the shadow to refetch and recheck yourself.

### How to Mark an Agent as Prioritized

When you are following many agents, some matter more than others. Press **Space** to toggle a **prioritized mark** on the agent this minimonitor **follows** — the one pinned at the top under `── this agent ──`. It does not matter which card in the list is highlighted; `Space` here always means "the agent I am watching". Marked agents show a bright **★**; unmarked agents show a dim **☆**, so the column is always present and rows never shift when you toggle one.

The cards in the scrollable list show marks but cannot be toggled from here — to mark some *other* agent, use [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}), where **Space** acts on the focused card.

If this window has no agent to follow — including a window you have renamed off the `agent-` prefix — **Space** shows a warning and writes nothing, and the pinned card shows no mark at all. The card itself is still there, headed `── this window ──`; what a rename switches off is the agent-only actions (**k**, **n**, **e**, **E**, **I** and this mark), which is the point of taking a window out of the agent rotation.

The marks are stored **per user, outside every repository**, in `~/.config/aitasks/agent_marks.json` (override the path with `AITASKS_AGENT_MARKS_FILE`). That means a mark you set here is visible from every other project's `minimonitor` and `monitor` — usually within one refresh cycle (about 3 seconds). Marks survive restarting the TUI.

Each mark is keyed by the pair *(project root, tmux window name)*, so two projects that happen to run identically-named agent windows never share a mark.

Marks are purely visual: they do not reorder the list or change any counter.

**Automatic cleanup.** You never have to unmark stale entries by hand:

- **Age** — a mark older than about 2 days is dropped automatically. Set `AITASKS_AGENT_MARK_TTL_DAYS` to change the window (a missing or invalid value falls back to the default, so a typo cannot wipe your marks).
- **Departed agents** — when a project's tmux session is visible and the marked window is gone, its mark is dropped. This check is deliberately conservative: if a project's session cannot be seen at all — it is not running, or lives on a different tmux server — its marks are always left alone. A project you simply have not opened today never loses its marks.

> **Note:** marking the agent you are already watching is exactly the point — the mark is *per user and cross-project*, so it is how you tell every **other** view that this is the agent that matters. Check `ait monitor`, or another project's minimonitor, and the agent you flagged from here stands out there.

### How to Jump to Another TUI

Press **j** to open the TUI switcher overlay. The overlay lists the TUIs integrated with the tmux workflow:

- **board** — `ait board`
- **monitor** — `ait monitor`
- **minimonitor** — `ait minimonitor` (the current TUI)
- **codebrowser** — `ait codebrowser`
- **settings** — `ait settings`
- **brainstorm** — `ait brainstorm`

Select a target and the switcher focuses the existing tmux window running that TUI or creates a new window and launches it.

<!-- SCREENSHOT: aitasks_tui_switcher_dialog.svg — the TUI switcher overlay as shown from minimonitor -->

### How the Agent List Refreshes

The agent list refreshes on its own every `tmux.monitor.refresh_seconds` seconds (default 3) — there is no manual refresh key. Actions that change the agent set (launching or killing an agent) schedule a refresh themselves, so the list catches up immediately rather than at the next tick.

### How to Toggle the Multi-Session View

By default, minimonitor aggregates agents from every aitasks tmux session on the current tmux server. Press **M** (uppercase, Shift+m) to toggle to a single-session view that shows only the agents in the tmux session this minimonitor is running in. Press **M** again to restore the aggregated view.

The toggle is in-memory only — it applies to the current minimonitor process and is not persisted to configuration. It is also independent of the main monitor's `M` toggle; switching modes in one TUI does not affect the other.

When the multi-session view is ON, agents are grouped under `── <session_name> ──` divider rows. The divider rows are display-only — they cannot be focused, and Up/Down navigation skips over them.

For the full cross-TUI story (auto-discovery, rendering details, cross-session focus from the main monitor), see [Multi-session view]({{< relref "/docs/tuis/monitor/reference" >}}#multi-session-view) in the monitor reference.

### How to Quit

Press **q** to quit minimonitor manually. The pane running minimonitor closes; the rest of your tmux session is unaffected. Because auto-despawn already closes minimonitor whenever its companion agent exits, manual quit is mainly useful when you want to reclaim the sidebar column while the agent is still running.

### Pairing Minimonitor with Monitor

Minimonitor and monitor are complementary and can run side by side. A productive layout looks like this:

- **Window 0 — `monitor`:** full dashboard via `ait monitor` (or `ait ide`), with pane list, preview, and all controls.
- **Window 1 — `agent-t42-...`:** a code agent window. Split horizontally so that the **left pane** runs the agent and the **right pane** runs minimonitor.
- **Window 2 — `agent-t43-...`:** another agent window with its own minimonitor split.
- **Window 3+ — other TUIs:** board, codebrowser, settings, brainstorm, all reachable from any monitor via `j`.

From any of the agent windows, Tab jumps into the code agent pane and j opens the TUI switcher to hop back to the full monitor dashboard. From monitor, `s` on an agent card brings you to the companion minimonitor alongside it. See [How to Switch tmux to the Focused Pane](../monitor/how-to/#how-to-switch-tmux-to-the-focused-pane) in the monitor docs for the reverse direction.

### Configuring Auto-Spawn

Auto-spawn (from board, codebrowser, monitor's next-sibling launch, and the TUI switcher's explore launch) is controlled by two keys in `aitasks/metadata/project_config.yaml`:

```yaml
tmux:
  minimonitor:
    auto_spawn: true   # set to false to disable automatic side splits
    width: 40          # width (in columns) of the minimonitor side pane
```

You can edit these directly, or use [`ait settings`]({{< relref "/docs/tuis/settings" >}}) → Tmux tab, which writes the same keys.

### Key Bindings Quick Reference

All actions below are also available via mouse — see [Mouse Support](#mouse-support).

| Key | Action |
|-----|--------|
| `Up` / `Down` | Move focus between agent cards |
| `Tab` | Move tmux focus to the sibling pane in this window |
| `Ctrl-b o` / `Ctrl-b` + arrow | *(native tmux, not a minimonitor key)* Move tmux focus between the panes in this window — works in both directions |
| `Enter` | Send an `Enter` keystroke to the sibling pane |
| `s` | Switch tmux focus to the selected agent's window |
| `i` | Show task info for the selected agent |
| `I` | Show task info for the followed agent (the one pinned at the top) |
| `k` | Kill the followed agent (with a confirmation dialog) |
| `n` | Launch the followed agent's next ready sibling task |
| `p` | Pick any task by typing its number, then launch it or move it to a board column |
| `e` | Launch an advisory [shadow agent]({{< relref "/docs/workflows/shadow-agent" >}}) beside the followed agent |
| `E` | Launch a shadow agent, choosing the code agent and model first |
| `c` | Pick the shadow's concerns and copy the selected ones to the clipboard (inside the picker: `r` rejects a concern, `t` spins one off as its own draft task, `e` edits the outgoing payload before it is copied, `R` reviews the rejected list, `u` shows any lines that could not be parsed) |
| `L` | Arm or disarm the [auto-recheck loop](#how-to-run-the-auto-recheck-loop) — minimonitor asks the shadow for a fresh review round once the followed agent settles |
| `Space` | Toggle the prioritized mark (`★`) on the **followed** agent (the one pinned at the top) — shared across all your projects |
| `d` | Cycle the idle-detection compare mode (`≈` ANSI-stripped, `=` strict) |
| `j` | Open the TUI switcher |
| `m` | Switch to the full [monitor]({{< relref "/docs/tuis/monitor" >}}) with this agent focused |
| `M` | Toggle the multi-session view ON/OFF |
| `?` | Open the shortcut editor to rebind any of these keys |
| `q` | Quit minimonitor |

Minimonitor inherits config keys (`tmux.default_session`, `tmux.monitor.refresh_seconds`, `tmux.monitor.idle_threshold_seconds`, `tmux.monitor.capture_lines`, `tmux.monitor.agent_window_prefixes`, `tmux.monitor.tui_window_names`) from the same `project_config.yaml` section monitor uses — see the [monitor reference]({{< relref "/docs/tuis/monitor/reference" >}}#configuration) for the full list.

---

**Next:** [Code Browser]({{< relref "/docs/tuis/codebrowser" >}}) — review diffs with task-aware annotations.
