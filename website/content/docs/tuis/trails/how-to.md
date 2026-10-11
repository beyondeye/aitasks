---
title: "How-To Guides"
linkTitle: "How-To Guides"
weight: 10
description: "Task-oriented guides for reading implementation trails with ait trails"
maturity: [experimental]
depth: [intermediate]
---

### How to Open a Trail

Run `ait trails`, or press **j** then **i** from any other TUI. The TUI scans the project and opens straight into the **trail selector**, which lists every trail it found; choose one and it opens in a tab, with its waves drawn as columns.

If you close the selector without choosing, the subtitle reads `no trail selected — press s`. Press **s** to open the selector again.

If the project has no trails yet, the TUI says so. Create one with the [`/aitask-trail`]({{< relref "/docs/skills/aitask-trail" >}}) skill in your coding agent, or with **T** on a task card in the board — see [Creating a Trail]({{< relref "/docs/workflows/implementation-trails" >}}#creating-a-trail).

### How to Open Several Trails and Switch Between Them

Press **s** to reopen the selector and choose another trail: it opens in a new tab, and the trails you already opened stay in theirs. Rows for trails that are already open are marked `● open`; choosing one switches to its tab instead of opening a second copy.

Switch tabs with **[** and **]** (previous / next, wrapping around), **1**–**9** to go to a tab by its number, or a click on the tab. Switching is instant: it reads nothing from disk or storage, and each tab comes back with the card you last focused in it. Press **Ctrl+W** to close the active tab.

The mark at the end of each tab is that trail's freshness (`✓` current, `⚠` stale, `⟳` checking), and `•` means the trail changed while you were looking at another tab — see [Tabs](../reference/#tabs) for every mark.

**s** lists the trails found by the last scan; it does not scan again. To pick up a trail created since — for example by `/aitask-trail` in another session — press **r** inside the selector to re-scan. When the last scan found no trails at all, **s** scans again by itself.

### How to Read the Waves and the Summary

Each wave is a column headed `W1 · <title>`, with its entries in order; use the arrow keys to move between cards and waves. Each card carries the member's classification glyph, its confidence, its task status and any drift marker. Members that are not live tasks in this repository — archived, cross-repo or deleted — appear as read-only ghost cards.

The pane under the columns holds the trail's summary, its prose answer to "what should land next, and why". Press **v** to open it in a scrollable dialog when it is longer than the pane. The subtitle states the trail's authoring depth (`· lite` or `· deep`) when the trail records one.

### How to Read One Member's Reasoning

Press **Enter** on a card. The detail screen leads with that member's own material — its entry, its wave, its drift reasons, and the observations and evidence that concern it — and withholds the trail-wide sections that are about other cards, summarized as a count. Press **a** to reveal the whole document, and **a** again to return.

### How to Keep a Trail Current

Pick the key by **what changed** — they read different things, and none of them reads everything:

- **A task's status changed on this machine** → press **r**. It re-reads the task files from disk and redraws the trail it already has loaded. It is instant, but it does not look at the stored trail, so it never picks up a new or updated trail.
- **The shown trail may have a newer stored version, or you want its freshness re-checked** → press **d**. It fetches the active trail again from storage and re-runs the freshness (drift) check. It never writes the trail.
- **A trail was created since the last scan, or on another machine** → press **s**, then **r** in the selector. The selector re-scans for trails, so the new one is listed.
- **The trail's reasoning is out of date** → press **R**. This opens the agent workflow that re-authors the shown trail — the slowest option by far. When the new version lands, the view reloads it on its own.

There is no sync key in this TUI. When the change was made elsewhere, sync task data first — `ait sync` in a shell, or **S** in the board's By-Trail view — and then:

1. press **r** for task statuses,
2. press **d** for the shown trail's latest stored version,
3. press **s**, then **r** in the selector, if a new trail may have arrived.

Pressing only **r** after a sync leaves a new or updated trail unseen.

### How to Start a Trail for a Member

Focus a live card and press **T**. This opens the [`/aitask-trail`]({{< relref "/docs/skills/aitask-trail" >}}) trail-creation workflow for that task in a code agent, through the usual agent-launch dialog — the TUI itself writes nothing. The agent gathers the task state, shows you the proposed waves and their reasoning, and writes a new trail **only after you confirm** its proposal. To re-author the trail you are already reading, use **R** instead.

The view does not switch to the result by itself. Once the agent has written the trail, press **s**, then **r** in the selector to re-scan, and select the new trail — it opens in a new tab.

**T** needs a live local task under focus. On a ghost card, or with nothing focused, it shows a warning and launches nothing.

### How to Pick a Member

Focus a live card and press **p**. This opens the same agent-launch dialog as **p** in the board, for [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) on that task. The TUI writes nothing. The launched workflow claims the task and plans it with you. If an agent window for that task is already running, **p** switches to it instead of starting a second one.

**p** is hidden on a ghost card and when nothing is focused.

### How to Move a Wave onto the Board

Moving tasks into board columns (`M` for a whole wave, `m` for one card) happens in the board, not here. Switching TUIs carries **neither the selected trail nor the focused card** — the board keeps its own active trail, independent of the one you are reading in `ait trails`:

1. Press **j** then **b** to switch to the board, then **z** for its By-Trail view. The board opens its trail selector on **z** only when it has no active trail yet; otherwise it shows the trail it last had.
2. Check the subtitle, which names the trail on screen. If it is not the one you want, press **s** and select it.
3. Focus a **live** member card in the wave you want to move — not a ghost card — and press **M**. The review dialog lists the wave's tasks in wave order before you choose a destination column.

See [Moving a wave into a column]({{< relref "/docs/tuis/board/reference" >}}#moving-a-wave-into-a-column) for what `M` and `m` skip and report.

---

**Related:** [Implementation Trails]({{< relref "/docs/workflows/implementation-trails" >}}) — the end-to-end workflow · [Reference](../reference/) — every key in one table.
