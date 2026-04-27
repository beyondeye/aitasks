---
date: 2026-04-27
title: "v0.18.3: Brainstorm agents run interactive by default, Brainstorm sessions that don't get stuck, and MissedHeartbeat is gone (and that means a small migration)"
linkTitle: "v0.18.3"
description: "v0.18.3 is mostly a brainstorm release — the TUI got a lot more transparent and a lot more resilient when things flake out. The agent-crew state machine also took a small but breaking turn."
author: "aitasks team"
---


v0.18.3 is mostly a brainstorm release — the TUI got a lot more transparent and a lot more resilient when things flake out. The agent-crew state machine also took a small but breaking turn.

## Brainstorm agents run interactive by default

Every brainstorm agent type — initializer, detailer, explorer, comparator, synthesizer, patcher — now launches in a tmux pane by default instead of headless. You can watch each agent work and step in if you need to, without having to override `launch_mode` in `codeagent_config.json`. There's also a new dim-cycling activity indicator next to the initializer banner and the Status tab that flashes on each poll, so you can tell the agent is alive even when nothing visible has changed.

## Brainstorm sessions that don't get stuck

A handful of failure modes that used to leave brainstorm sessions silently broken are now recoverable. If `ait brainstorm` initializer fails, you get a scrollable error modal with the captured stderr/stdout and a "Delete branch & retry" action that handles the common stale-crew-branch case for you. `ait brainstorm delete` now actually cleans up its stale branches so the next `init` doesn't fail with "branch already exists". And the TUI no longer spuriously prompts you to apply changes on session load before the initializer has actually finished writing them.

## MissedHeartbeat is gone (and that means a small migration)

The `MissedHeartbeat` agent status that shipped in v0.18.2 has been removed. Heartbeat freshness is now decoupled from terminal status entirely — stale heartbeats no longer mutate `_status.yaml`; if you want to know whether an agent is alive, call `get_stale_agents()` or `check_agent_alive()`. **If you have crews in-flight from v0.18.2, run `ait crew cleanup --crew <id>` before resuming work** — the trimmed state machine will reject any `MissedHeartbeat` values written under the old runner.

## A friendlier `install.sh` and a hardened review prompt

`install.sh` now offers an interactive overwrite prompt when it detects an existing install in a TTY, and the non-TTY error message spells out all three recovery paths inline (`ait upgrade latest`, `bash -s -- --force`, `bash install.sh --force`) instead of leaving you to find them in the docs. On the workflow side, the Step 8 user-review prompt is now non-skippable across auto-mode and execution-profile overrides, and the workflow now offers to spin off a follow-up task for any upstream defects you flagged while patching.

---

---

**Full changelog:** [v0.18.3 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.18.3)
