---
title: "Feature Reference"
linkTitle: "Reference"
weight: 20
description: "Keybindings, refresh semantics, shortcut scope and launch details for ait trails"
maturity: [experimental]
depth: [advanced]
---

## Keybindings

Every key below can be rebound — press **?** for the in-place editor, or open
[Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}}). See
[Shortcut scope](#shortcut-scope) for how a rebind here relates to the board.

| Key | Action | Context |
|-----|--------|---------|
| `s` | Open the trail selector — re-scans the project for trails first | Any time; the selector also opens on launch |
| `r` | Re-read task files from disk and redraw the loaded trail | Trail selected |
| `d` | Fetch the active trail again from storage and re-check its freshness | Trail selected |
| `R` | Open the agent workflow that re-authors the active trail | Trail selected; not while a launch is already starting |
| `v` | Open the trail's summary in a scrollable dialog | The trail has a summary |
| `T` | Open the `/aitask-trail` creation workflow for the focused task — the workflow confirms before it writes | Focused live local card (a ghost card, or no focus, gives a warning) |
| `Enter` | Open the focused member's detail screen | Focused card |
| `Up` / `Down` / `Left` / `Right` | Move between cards and waves | |
| `j` | TUI switcher | |
| `?` | Shortcut editor | |
| `q` | Quit | |

### In the detail screen

| Key | Action |
|-----|--------|
| `a` | Reveal the whole trail document, or return to the focused member's own material |
| `Escape` | Close the detail screen |

## What each refresh reads

| Key | Task files | Stored trail | List of trails |
|-----|------------|--------------|----------------|
| `r` | Re-read | Not read — the loaded copy is redrawn | Not read |
| `d` | — | Fetched again, then freshness re-checked | Not read |
| `s` | — | — | Re-scanned |
| `R` | — | A new version is written by the agent after you confirm; the view reloads it when it lands | — |

None of `r`, `d` and `s` writes anything. For the costs of each key and the drift reasons a card can show, see [By-Trail]({{< relref "/docs/tuis/board/reference" >}}#by-trail) in the board reference — the view is the same.

## Not available here

These keys belong to the board's By-Trail view and do nothing in `ait trails`:

| Key | Board action | Why not here |
|-----|--------------|--------------|
| `m` | Move the focused entry's task to a column | There are no board columns in this TUI |
| `M` | Move the focused wave's tasks to a column | Same — use the board ([how-to](../how-to/#how-to-move-a-wave-onto-the-board)) |
| `S` | Sync task data with the remote, then redraw | Sync from the board or with `ait sync`, then refresh here |

## Shortcut scope

The trail keys are the board's own shortcuts: `ait trails` registers under the `board` scope and uses the same bindings, so an override such as

```yaml
shortcuts:
  board:
    trail_select: o
```

in `aitasks/metadata/userconfig.yaml` rebinds the key in both `ait trails` and the board's By-Trail view.

The `?` editor inside `ait trails` lists the `board` rows this TUI uses — the trail keys, navigation and quit — plus the shared actions. To rebind a key that only the Kanban board uses, open the editor from `ait board` or use [Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}}).

## Launch and environment

| Launch | Notes |
|--------|-------|
| `ait trails` | From a shell in the project |
| `j` → `i` | From any TUI, through the [TUI switcher]({{< relref "/docs/tuis" >}}#navigating-between-tuis); `i` is not shown on the switcher's hint row, but the entry is listed |

- **Task directory** — read from `TASK_DIR` (default `aitasks`).
- **Read-only** — the TUI never writes a trail, a task, or `board_config.json`; a project without a board configuration file is left without one.
- **Separate selection** — the trail shown here is independent of the trail the board's By-Trail view shows; switching TUIs does not carry it across.
