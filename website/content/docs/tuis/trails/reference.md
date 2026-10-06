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
| `s` | Open the trail selector from the list found by the last scan; it scans first only when that list is empty or the last scan failed | Any time; the selector also opens (after a scan) on launch |
| `[` / `]` | Previous / next tab; wraps around | Two or more tabs open |
| `1`–`9` | Go to tab 1–9 | That tab exists |
| `Ctrl+W` | Close the active tab | A tab is open |
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

### In the trail selector

| Key | Action |
|-----|--------|
| `Up` / `Down` | Move between trails |
| `Enter` | Open the trail in a new tab — or, on a row marked `● open`, switch to its tab |
| `r` | Re-scan the project for trails and reopen the selector with the new list |
| `Escape` | Close the selector |

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
| `s` | — | — | Not read — the list from the last scan is shown (scanned only when that list is empty or the last scan failed) |
| `r` in the selector | — | Fetched again for every trail | Re-scanned |
| `[` / `]` / `1`–`9` | — | — | — (the tab is redrawn from memory) |
| `R` | — | A new version is written by the agent after you confirm; the view reloads it when it lands | — |

None of `r`, `d`, `s` and the tab keys writes anything. `r` re-reads the task files for every tab, not only the active one: the other tabs show the new statuses when you switch to them. For the costs of each key and the drift reasons a card can show, see [By-Trail]({{< relref "/docs/tuis/board/reference" >}}#by-trail) in the board reference — the view is the same.

## Tabs

Every trail you open from the selector gets its own tab, in the row under the title bar. Trails found by a scan are only listed in the selector; they get a tab when you open them. A tab reads `<number> <title> <freshness>`:

| Mark | Meaning |
|------|---------|
| `✓` | Current — the freshness check found no drift |
| `⚠` | Stale — the freshness check found drift |
| `⟳` | The freshness check is still running |
| `?` | The freshness check could not run |
| `✗` | The trail could not be loaded |
| `•` | The trail changed while its tab was in the background — a freshness result, a reload or a newer stored version arrived. Cleared when you switch to the tab |

Switching tabs reads nothing: no task files, no stored trail, no freshness check. Each tab keeps its last freshness result and the card you last focused in it. Click a tab to switch to it.

Closing the active tab shows the tab to its right, or to its left when it was the last one. Closing the only tab returns to the `no trail selected — press s` state.

When a scan (`r` in the selector) finds a newer stored version of a trail that is open in a tab, that tab is updated and its freshness is re-checked.

`R` keeps watching for the new version after you switch to another tab, and reloads that trail's tab when the version lands. Only one `R` refresh is watched at a time: starting `R` for a second trail stops watching the first, so press `d` on the first trail once its refresh has finished. Closing a trail's tab stops the watch for that trail.

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
- **Separate selection** — the open tabs are independent of the trail the board's By-Trail view shows; switching TUIs does not carry them across, and they are not kept when you quit.
