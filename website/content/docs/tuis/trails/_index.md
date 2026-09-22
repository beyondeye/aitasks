---
title: "Trails"
linkTitle: "Trails"
weight: 12
description: "Stand-alone reader for implementation trails — the board's By-Trail view as its own TUI"
maturity: [experimental]
depth: [intermediate]
---

`ait trails` is a stand-alone reader for [implementation trails]({{< relref "/docs/workflows/implementation-trails" >}}): it shows one stored trail as wave columns, with each member's classification, confidence, status and drift, and the trail's summary underneath. It is the [board's]({{< relref "/docs/tuis/board" >}}) By-Trail view (`z`) running on its own — the same lanes, cards and keys, without the Kanban board around them. The By-Trail view stays inside the board as well, and both read the same stored trails.

<!-- SCREENSHOT: aitasks_trails_main_view.svg — ait trails showing one trail's waves as columns with the summary pane below -->

> **Customizable keys:** every shortcut here can be rebound. Press `?` in this
> TUI for the in-place editor, or open
> [Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}}).
> The trail keys are the board's own `board` entries, so a rebind applies in
> both `ait trails` and the board's By-Trail view.

## Purpose

A trail answers "in what order should this group of tasks land, and why". Reading one does not need the board: `ait trails` starts directly in the trail selector, loads nothing but the task files and the trail itself, and never writes your board layout. Use it when you want to follow a trail — which wave is next, which members have landed, what has drifted — without the whole board in front of you.

The TUI is **read-only**. It never writes a trail and never changes a task. The two keys that start trail authoring — `T` to create a trail for the focused task, `R` to re-author the one on screen — open the [`/aitask-trail`]({{< relref "/docs/skills/aitask-trail" >}}) workflow in a code agent, and that workflow asks you to confirm before it writes anything.

## Relationship to the board

| Aspect | `ait board` (By-Trail view, `z`) | `ait trails` |
|--------|----------------------------------|--------------|
| Opening a trail | `z`, then the selector opens when no trail is active yet | The selector opens on launch |
| Trail keys (`s`, `r`, `d`, `R`, `v`, `Enter`) | Yes | Yes — the same bindings |
| `T` | Hidden in By-Trail; used from the kanban and By-Topic views | Opens the trail-creation workflow for the focused live card |
| Move to a column (`m` / `M`) | Yes | No — there are no board columns here |
| Sync with remote (`S`) | Yes | No — sync from the board or with `ait sync` |
| Writes `board_config.json` | Yes (board layout and settings) | Never |
| TUI switcher (`j`) | Yes | Yes |

The two TUIs keep **separate** trail selections. Switching between them with `j` does not carry the selected trail or the focused card across — see [How to move a wave onto the board](how-to/#how-to-move-a-wave-onto-the-board).

## Launching

- `ait trails` from a shell in the project.
- **`j`** then **`i`** from any TUI, through the [TUI switcher]({{< relref "/docs/tuis" >}}#navigating-between-tuis). The switcher's bottom hint row does not advertise `i`, but the entry is listed in the switcher and the key works.
- **`j`** then **`b`** from `ait trails` goes back to the board.

`ait trails` reads the task directory from `TASK_DIR` (default `aitasks`), the same as the other `ait` commands.

---

**Next:** [How-To Guides](how-to/) — opening a trail, keeping it current, and handing a wave to the board.
