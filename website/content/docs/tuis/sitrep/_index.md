---
title: "Sitrep"
linkTitle: "Sitrep"
weight: 19
description: "The list view of the sitrep window: the repository's todo list, with keys for the routine work and for requests to the sitrep agent"
maturity: [experimental]
depth: [intermediate]
---

The sitrep TUI shows the repository's [sitrep]({{< relref "/docs/workflows/sitrep" >}}) todo list: the follow-up tasks, actions, questions and watches that finished agents left behind. It runs in the sitrep window, in the pane below the sitrep agent. Routine work on the list happens in the TUI itself: collecting new wrap-ups and re-checking the items, dismissing an item, restoring a damaged list, picking a task, showing a task in the board or in a trail, and showing a push command. Work that needs the agent's judgement (triage, questions, situation text, a trail refresh, advice on what to pick) is typed into the agent as a request when you press a key.

<!-- SCREENSHOT: aitasks_sitrep_tui_main_view.svg — the sitrep window: agent above, the sitrep TUI's list below, minimonitor on the right -->

> **Customizable keys:** every shortcut here can be rebound. Press `?` in this
> TUI for the in-place editor, or open
> [Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}}).
> The "How" line of each item names the key as you bound it.

## The sitrep window

`ait sitrep` opens one window per repository, named `agent-sitrep`, with three panes:

```
+----------------+------+
| sitrep agent   | mini |
+----------------+ moni |
| sitrep TUI     | tor  |
+----------------+------+
```

- **The sitrep agent** (top left) is the [`/aitask-sitrep`]({{< relref "/docs/skills/aitask-sitrep" >}}) code agent. You talk to it, and it triages wrap-ups and answers questions from the items' sources.
- **The sitrep TUI** (below it) shows the list and does the routine work.
- **A [minimonitor]({{< relref "/docs/tuis/minimonitor" >}})** (the right column) follows the sitrep agent, as it does beside any other agent.

The panes are independent. When the agent exits, the TUI and the minimonitor stay: press **`A`** in the TUI, or run `ait sitrep` again, to start a new agent above the TUI. When the TUI is missing, `ait sitrep` adds it back under the agent.

## Launching

- `ait sitrep` from inside tmux opens the window, or switches to it when it is already open. **`S`** in [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}), a minimonitor or the TUI switcher does the same.
- `ait sitrep tui` runs the TUI on its own, for example in a spare pane. The list, the details and the actions work there too. The request keys and **`A`** need the sitrep agent's tmux server, so they stay hidden outside tmux; run `ait sitrep` from inside tmux to reach the agent.

The TUI reads the list of the repository it is started in. Started from a linked task worktree, it reads the main worktree's list, which is the one list the repository has.

## What it never does

The TUI never pushes, commits or edits a task or plan file. It changes the list only through the list's own locked writer, the same one the agent uses. The only pane it types into is the sitrep agent's, and only when you press one of its request keys. It refuses to type while the agent is busy, waiting at a dialog, holding text you typed, or scrolled back, so it never mixes its request into your input.

---

**Next:** [How-To Guides](how-to/) — reading the list, acting on an item, and handing work to the sitrep agent.
