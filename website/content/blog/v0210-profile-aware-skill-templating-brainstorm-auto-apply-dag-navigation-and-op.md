---
date: 2026-05-27
title: "v0.21.0: Profile-aware skill templating, Brainstorm: auto-apply,  DAG navigation,  and operation detail, and Cross-repo project registry"
linkTitle: "v0.21.0"
description: "v0.21.0 is a big one — a foundational refactor of how skills are authored and dispatched, the brainstorm TUI graduating from "experiment" to a real DAG-driven planning workflow, first-class cross-repo project plumbing, and a fresh mobile-companion bridge."
author: "aitasks team"
---


v0.21.0 is a big one — a foundational refactor of how skills are authored and dispatched, the brainstorm TUI graduating from "experiment" to a real DAG-driven planning workflow, first-class cross-repo project plumbing, and a fresh mobile-companion bridge.

## Profile-aware skill templating

Every aitask skill is now authored once as a `.md.j2` Jinja template and rendered per execution profile, per agent. You stop maintaining four near-duplicate copies of each skill across Claude, Codex, Gemini, and OpenCode; the renderer fans out per-profile variants behind a thin stub. A new `ait skillrun` command lets you launch any agent with any skill at any profile (with `--profile-override` for ad-hoc tweaks and `--dry-run` previews), and the Per-Run profile editor lets you tweak the active profile right from the launch dialog. Saving a profile invalidates the right rendered variants automatically — running agents pick up the new values on next invocation.

## Brainstorm: auto-apply, DAG navigation, and operation detail

Brainstorm sessions now auto-apply agent outputs as they complete — explorer, synthesizer, and detailer all flow straight into the DAG without manual intervention, with `ctrl+shift+x/y/d` retries for the cases that fail. The Graph tab gained full 2D arrow-key navigation, an inline detail pane, `p`/`l` to peek a node's proposal or plan, `x` to pick a compare-with anchor, and clickable nodes. An `A` keybinding offers context-aware Explore / Detail / Patch actions on the focused node, and a new `OperationDetailScreen` (open with `o`) shows the operation overview plus per-agent Input / Output / log tail tabs.

## Cross-repo project registry

`ait projects` is the new home for working across multiple aitasks repos. Register projects to `~/.config/aitasks/projects.yaml` once (`add`), then list them, resolve names to paths, exec into them, prune stale entries, or run an interactive `doctor` to triage broken registrations. The TUI switcher surfaces registered-but-inactive projects with a `(stale)` marker and spawns tmux sessions on demand. `ait create --project <name>` lets you file a task into a cross-repo registry entry without leaving your current workspace.

## Mobile companion bridge

A new `ait applink` TUI generates a QR code carrying a LAN pairing URI for the mobile companion app (built in the sibling `aitasks_mobile` repo). The QR includes hostname and TLS fingerprint so pairing is one-tap. Full protocol design — WebSocket envelope, pairing flow, connection state machine, permission profiles, verb gating — is documented under `aidocs/applink/`.

## Quality-of-life

The monitor TUI finally distinguishes "agent awaiting user input" from "idle" with per-agent prompt-regex detection, surfaces a separate `awaiting` count, and prefers awaiting panes when auto-switching. Codebrowser gained an `E` keybinding to suspend into `$EDITOR` and now surfaces archived tasks that have no code commits with a dim `[no-code]` marker. `ait create` lets you fzf-pick archived task references into a new task's description. The TUI switcher auto-selects the focused agent pane's session when opened from inside monitor.

---

---

**Full changelog:** [v0.21.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.21.0)
