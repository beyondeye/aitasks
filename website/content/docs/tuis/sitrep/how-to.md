---
title: "How-To Guides"
linkTitle: "How-To Guides"
weight: 10
description: "Task-oriented guides for the sitrep TUI: reading the list, acting on items, and handing work to the sitrep agent"
maturity: [experimental]
depth: [intermediate]
---

### How to Read the List

The list is grouped by what you can do now. **Now** (the agent and the monitor call it *Pick now*) holds items to act on, **Next** holds what comes after them, and **Waiting** holds items that depend on something else, such as CI or a trail's next wave. Press **d** to also show **Recently done** and **Dismissed**: the highlight moves to the first of them, and the footer label changes from **Show done** to **Hide done**. While they are hidden, the header says how many done and dismissed items it leaves out.

Each row has five columns:

- **Item**: the item's id, such as `c12`.
- **Checked**: how long ago the item's live state was last checked, or `—` when it never was.
- **Pri/Eff**: the priority and effort of the task an item names, such as `hi/med`. It is blank for items that name no task.
- **Created**: when that task was created. Today's tasks show the time, older ones the date.
- **What to do**: one line saying what the item needs from you, such as "Triage t2175_2's wrap-up: …", "Pick t2182 (status: Ready): …" or "Waiting on: … — nothing to do now".

The header line shows how many items there are and how many are open in Now, whether the sitrep agent is running, and when the list was last re-checked. Above the list, the **situation** text gives a short summary per work area. Press **s** to hide or show it.

A click selects a row and **Enter** opens it. This is the same on every list in the TUI.

### How to Open an Item and Its Sources

Press **Enter** on a row to open its details. The top part says what the item needs: **What to do**, **How** (which key does it), and **About** (the task, push or reference the item points at). For a task item it also shows the task's priority and effort, its status, when it was created and which trails it is in. Then come **Checked**, the **Outcome** of the last check or action, and the item's **Context**: its background, where it came from (agent, task, commit, date), and its work area.

Below that is a list of links: the task's description, its trails, and every source the item points at, such as the agent's closing message, the workflow result, a plan, a commit or a file. Press **Tab** to move between the text and the links, then **Enter** on a link to open it:

- Task and plan files and other Markdown files open rendered. Press **m** to see the raw text with line numbers, and **m** again to go back. Links inside them are never opened.
- A source that points at particular lines opens as raw text at those lines.
- A commit opens as its summary and list of changed files.
- **Related** and **Mentioned by** links open the other item. An **In trail** link opens the trail in `ait trails`, with the task's card focused.

Press **Escape** to go back. Press **l** on the main list for the **Q&A log**: every question you asked the sitrep agent and its answer, newest first, with links to the items each one names.

### How to Collect New Wrap-ups and Re-check the List

When the TUI starts, it collects every finished agent's wrap-up that is not in the list yet and then re-checks the items it can verify: whether a task is still open, whether a push reached the remote, how far a trail has progressed. It reports the result in a short message.

Press **r** to do it again, on the main list or in an item's details. A panel then shows what the collection added and what the re-check changed. Only one run happens at a time, so **r** is greyed out while one is in progress. The header shows when the last run ended and whether it had errors.

The list on screen also follows every other change to the list, for example one the sitrep agent just wrote, within a few seconds, and keeps your selection.

### How to Act on an Item

These keys work on the highlighted row of the main list and in an item's details. Each key is shown only for the items it fits.

- **p** — open [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) for the task in a new agent window, through the usual launch dialog. It is shown only on open task items of this repository. If an agent window for that task is already running, the TUI switches to it instead.
- **b** — show the task's card in the [board]({{< relref "/docs/tuis/board" >}}). A running board in the project's session focuses the card. Otherwise a board is started.
- **z** — show the task in [`ait trails`]({{< relref "/docs/tuis/trails" >}}), with its card focused. It is shown only for a task that is in at least one trail. When the task is in several trails, a picker asks which one.
- **P** — show the push command for a push reminder, with a **Copy** button. The TUI never runs it. The reminder closes by itself once a re-check finds the commit on the remote.
- **x** — dismiss the item. You must give a reason, which is kept as the item's outcome. A dismissed item stays dismissed: later collections and re-checks never bring it back.

If the item changed while you were looking at it, for example because a re-check updated it, the key does nothing on the old view: the TUI refreshes the details and asks you to press the key again. For a dismissal, the dialog opens again and names the change.

### How to Hand Work to the Sitrep Agent

For work that needs the agent, press a request key. The TUI types a one-line request into the agent's pane and submits it, as if you had typed it there yourself:

- **t** — triage this wrap-up, or handle this unparsed-output review. Typing `>t` in the agent instead triages every open wrap-up at once.
- **a** — ask the agent about this item. A one-line dialog takes your question.
- **w** — rewrite the situation text of this item's work area.
- **T** — have the agent report on the trail this watch follows, and offer to refresh it.
- **n** — ask the agent what to pick next.

The request keys are shown only while the agent is running, and only one request is delivered at a time. The agent handles a request exactly like typed input: it re-reads the list first and still asks you before it writes anything.

The TUI types only into an agent that is idle with an empty input box (the *composer* its messages mention), and never while the agent is working, waiting for an answer to a dialog, holding text you started typing, or scrolled back in tmux copy mode. It shows "Sent to the sitrep agent" when the request was submitted. Anything else opens a panel that says what happened. Recover according to what it says:

- **Typed but not submitted.** The request is in the agent's input box, but the TUI withheld the Enter, usually because the input box no longer held exactly the request. Go to the agent's pane and read the whole input box before you press anything. If the pane is scrolled back, leave copy mode first. Press Enter only when the input box holds exactly the request line. When it holds anything else, such as text typed before or after the request or a changed line, edit or clear it first.
- **Could not verify what happened.** The request may already have been sent. Read the agent's conversation before you press the key again, or the agent gets the request twice.
- **Not sent.** Nothing was submitted. Deal with the reason the panel gives: wait until the agent is idle, answer its dialog, send or clear your own draft, or leave copy mode. Then press the key again. When the panel says the agent was replaced before the Enter, the line had already been typed: look at the new agent's input box and clear any leftover line before you press the key again.

The detailed list of results is in the [reference](../reference/#request-results).

### How to Filter by Label

Press **f** to filter the list by task labels. The picker lists the labels of the tasks in the list, each with a count. **Space** checks a label, and **Enter** or **Apply** applies the filter. The list then shows only task items whose task has at least one of the checked labels. Items that are not tasks of this repository (triage, decisions, watches, push reminders, tasks of other projects) are hidden while the filter is on, and so are task items whose task file is missing. The header names the filter and how many items it hides.

Press **F** to clear the filter. The filter lasts until you quit the TUI. It is never saved in the list.

### How to Recover a Missing Agent or a Damaged List

- **The agent is not running.** The header reads `agent: not running — press A`. Press **A** to start a new sitrep agent above the TUI, or run `ait sitrep`.
- **The agent's state is unknown.** The header reads `agent: unknown` when the TUI cannot see the agent, for example when it runs outside tmux. **A** and the request keys are then hidden: run `ait sitrep` from inside tmux to start or reach the sitrep agent.
- **The list is damaged.** A red banner says which file could not be read. The TUI keeps showing the last good view of it. Press **R** to restore the last good copy from the list's backup. The damaged file is kept beside it, and if it was repaired in the meantime, nothing is restored.

---

**Next:** [Reference](../reference/) — every key, column, result and setting.
