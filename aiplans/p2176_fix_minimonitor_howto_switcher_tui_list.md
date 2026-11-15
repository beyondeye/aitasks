---
Task: t2176_fix_minimonitor_howto_switcher_tui_list.md
Base branch: main
Output branch: main
---

# t2176 — Fix the switcher TUI list in the minimonitor how-to

## Context

`website/content/docs/tuis/minimonitor/how-to.md` "How to Jump to Another TUI"
hand-lists the switcher's entries. The list is wrong: it includes
**minimonitor** ("the current TUI"), which the switcher never lists
(`TUI_REGISTRY` in `.aitask-scripts/lib/tui_registry.py` has it
`in_switcher=False`), and it omits trails, stats, syncer, applink, chatlink and
frozenagent. A hand-copied list drifts every time the registry changes, which
is how it went wrong.

The canonical description lives in `website/content/docs/tuis/_index.md`
§"Navigating between TUIs" (anchor `#navigating-between-tuis`), which already
states minimonitor is not listed and is linked by that anchor from other pages.

**Same defect, same fix, two sibling spots** (folded in rather than spawned,
since they are the identical stale-copy pattern and a one-line edit each):
- `website/content/docs/tuis/monitor/how-to.md:134-143` — same hand list, also
  includes minimonitor and omits the same TUIs.
- `website/content/docs/tuis/monitor/_index.md:76` — parenthetical
  "(board, monitor, codebrowser, settings, stats, brainstorm, syncer)", missing
  trails, frozenagent, chatlink, applink.

## Approach

Replace each hand list with a short description plus a link to the canonical
section — no per-TUI enumeration to drift. `diffviewer` stays unmentioned
(CLAUDE.md: omit it from user-facing lists).

### 1. `website/content/docs/tuis/minimonitor/how-to.md` (lines ~394-403)

Replace the intro line + 6-bullet list with:

```markdown
Press **j** to open the TUI switcher overlay. It lists the TUIs integrated with the tmux workflow — board, trails, monitor, codebrowser, settings, stats, syncer and more — plus your configured git TUI and any running code agent and brainstorm windows. Minimonitor itself is not listed. [Navigating between TUIs]({{< relref "/docs/tuis" >}}#navigating-between-tuis) has the full list and the multi-session controls.
```

Keep the following "Select a target …" sentence and the SCREENSHOT comment.

### 2. `website/content/docs/tuis/monitor/how-to.md` (lines ~136-143)

Same replacement (keeping "from any zone"), and drop both the `monitor … (the
current TUI)` and `minimonitor` bullets with the list. Keep its "Select a
target …" sentence and SCREENSHOT comment.

### 3. `website/content/docs/tuis/monitor/_index.md:76`

Replace the parenthetical with "(board, trails, codebrowser, settings, stats,
syncer and more — see [Navigating between TUIs]({{< relref "/docs/tuis" >}}#navigating-between-tuis) for the full list)".

## Verification

- `grep -rn 'the current TUI)\|minimonitor\*\* —' website/content/docs/tuis/` → no hits.
- `cd website && hugo build --gc --minify` (relref resolves) and
  `python3 check_links.py --build` → no broken links/fragments.
- Re-read the three edited passages in context.

## Post-implementation

Step 9: commit `documentation: … (t2176)` on main, archive the task and plan.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Post-Review Changes

### Change Request 1 (2026-11-15 17:20)
- **Requested by user:** The three new pointers promise a "full list" at `/docs/tuis/#navigating-between-tuis`, but that canonical paragraph omitted App Linker, which `tui_registry.py` lists with `in_switcher=True`. Add it there so every pointer is accurate.
- **Changes made:** Verified that `_build_tui_list` (`.aitask-scripts/lib/tui_switcher.py`) passes every `switcher_tuis()` entry through unfiltered, so App Linker is shown, on quick-jump key `a`, which the bottom hint row deliberately does not advertise. Added "App Linker" to the canonical list and "App Linker on **`a`**" to the sentence naming the keys the hint row omits.
- **Files affected:** `website/content/docs/tuis/_index.md`

## Final Implementation Notes
- **Actual work done:** The three hand-copied switcher lists became a short summary plus a relref to `/docs/tuis/#navigating-between-tuis`. They were in `website/content/docs/tuis/minimonitor/how-to.md` ("How to Jump to Another TUI"), `website/content/docs/tuis/monitor/how-to.md` (same section) and `website/content/docs/tuis/monitor/_index.md` ("Jumping to Another TUI"). Minimonitor is no longer presented as a switcher entry. Review-driven: the canonical paragraph in `website/content/docs/tuis/_index.md` now includes App Linker (and its `a` key), so the "full list" the pointers promise is complete.
- **Deviations from plan:** One extra file (`tuis/_index.md`) from Change Request 1. The plan had assumed the canonical paragraph was already complete.
- **Issues encountered:** None. `check_links.py --build` passed before and after the review change; the stale-list grep finds nothing.
- **Key decisions:** Link instead of enumerate, so the per-page text cannot drift from `TUI_REGISTRY` again; only the canonical paragraph lists every TUI. `diffviewer` stays unmentioned (CLAUDE.md). The summary names the git TUI and running agent/brainstorm windows because `_build_tui_list` and the switcher append them dynamically.
- **Upstream defects identified:** None
