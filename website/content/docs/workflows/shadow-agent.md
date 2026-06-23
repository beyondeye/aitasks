---
title: "Shadow Agent"
linkTitle: "Shadow Agent"
weight: 83
description: "Launch an advisory companion agent that reads a running agent's output and helps you explain it, answer its prompts, or interrogate its plans"
depth: [intermediate]
---

When you have a coding agent working a task, it is not always easy to follow what it is doing — its output can be dense, a plan it produced may assume background you don't have, or it may pause on a question whose context has scrolled away. The **shadow agent** is an advisory companion you launch beside the agent you are watching (the *followed agent*). It reads that agent's terminal output and helps you reason about it, in plain terms, on demand.

The shadow is **read-only and advisory by design**. It explains and suggests; it never types into the followed agent's pane. You remain the one who answers prompts and approves plans — the shadow just makes you a better-informed driver.

## Launching a shadow

You launch a shadow from the [minimonitor](../../tuis/minimonitor/) sidebar that sits next to each running agent: focus the agent's card and press **e**. By default the shadow opens as a new pane in the **same tmux window** as the followed agent, so the two sit side by side. (You can configure it to open in a separate window instead — see [Configuration](#configuration).)

The shadow is a companion pane, like minimonitor itself: it never appears in the agent list, and it closes automatically when the agent it shadows exits.

See [How to Launch a Shadow Agent](../../tuis/minimonitor/how-to/#how-to-launch-a-shadow-agent) for the minimonitor keybinding details.

## What happens once it is running

When the shadow starts, it greets you with a short summary of what it can do, then waits for you to tell it — in your own words — what you'd like. There is no mode to pick up front: you just describe what you want, and it routes to the right capability.

Two things are worth knowing:

- **It reads the followed agent's current screen, and can re-read it any time.** The agent keeps working after you launch the shadow, so its state changes. Ask the shadow to refetch whenever you want it to look at the latest output.
- **It offers help proactively.** Each time it reads the screen, the shadow glances at what is visibly there and, if something obviously useful applies, it offers it without being asked — for example, if the agent is paused on a question, it offers to help you decide; if a plan is on screen awaiting approval, it offers to explain or pressure-test it. These are suggestions you can take or ignore; they never restrict what you can ask for.

## What the shadow can do

All of the following are served in a single flow — you reach them just by asking.

### Explain what the agent is doing

Ask "what is this agent doing right now?" (or about a specific error or message) and the shadow reads the current screen and explains, in plain terms, what is happening, what the agent is waiting on, or what a message means.

### Help you answer a prompt

When the followed agent is paused on a question — including one shown without the underlying task or plan visible — the shadow can fetch the relevant task and plan in the background, lay out what each option means and its trade-offs, and **suggest** an answer with its reasoning. You type the answer into the agent yourself; the shadow never does.

### Interrogate a plan

Before you approve a plan an agent has produced, the shadow can examine it for you in four distinct ways:

- **Explain it to a non-expert** — beyond a plain-terms summary, it identifies the technical subjects the plan rests on and offers, for each one you choose, a short introduction and why the plan relies on it, then walks through the plan in plain language.
- **Challenge it** — acting as a constructive adversary, it actively looks for where the plan could fail (regressions, missed edge cases, a wrong-shaped approach, blast radius, verification gaps, unstated dependencies) and gives you a prioritized list, separating problems that should block approval from improvements you could accept as follow-ups.
- **Question it (Socratic)** — instead of telling you what's wrong, it asks open-ended questions that lead you to examine the plan's own reasoning and trade-offs, a few at a time.
- **Surface its assumptions** — it enumerates what the plan quietly takes for granted (about the environment, the data, other code's behavior, sequencing, and scope) and highlights the assumptions that are both load-bearing and unverified — the ones most likely to make a plan silently go wrong.

Ask for one of these specifically, or ask broadly ("review this plan") and the shadow runs several and presents a combined result.

### Forward concerns to the followed agent

When the shadow interrogates a plan, alongside its human-readable findings it also emits a structured, machine-parseable **concern block** — a fenced list (`===AITASK-CONCERNS===` … `===END-CONCERNS===`) of `- [priority | region] body` items, where `priority` is `high`, `medium`, or `low` and `region` names the part of the plan the concern targets. The block is additive: the shadow still prints its normal prose; the block is an extra copy meant for pick-and-forward.

From [minimonitor](../../tuis/minimonitor/) you can then **selectively forward** these concerns to the followed agent without retyping them. Press **c** to open a checklist of the shadow's concerns, tick the ones you want, and minimonitor copies them — with a short preamble — to your clipboard for you to paste into the agent. When a fresh concern block appears, minimonitor also proactively hints that the shadow raised concerns. This keeps the advisory-only contract intact: the concerns land on *your* clipboard, and you decide what to paste. See [How to pick shadow concerns](../../tuis/minimonitor/how-to/#how-to-pick-shadow-concerns).

## Advisory only

The shadow is read-only with respect to the followed agent. It never sends keystrokes or answers into the agent's pane — not even an answer it just suggested. Everything it produces goes to you, and you decide what to do with it. This is the core contract of the shadow: it informs your decisions without ever making them for you.

## Configuration

Two settings control the shadow, both editable in [`ait settings`](../../tuis/settings/):

- **Placement** — `tmux.shadow_same_window` (Tmux tab). `true` (the default) splits the shadow into the followed agent's window; `false` opens it in its own window.
- **Agent and model** — the `shadow` row on the Agent Defaults tab selects which coding agent and model the shadow runs as. You can run the shadow as a lighter, faster model than the agent it watches.

---

**Next:** [Explain](../explain/) — use code evolution history to rebuild understanding of why code exists.
