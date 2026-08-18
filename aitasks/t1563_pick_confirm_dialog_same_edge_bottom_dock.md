---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui, aitask_monitormini]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-08-18 09:49
updated_at: 2026-08-18 10:01
---

## The defect

`TaskPickConfirmDialog` in `.aitask-scripts/monitor/monitor_shared.py` docks two
sibling widgets to the **same bottom edge** inside `#task-detail-dialog`:

| DOM order | id | CSS |
|---|---|---|
| 1 | `#pick-confirm-row` | `:1495` — `dock: bottom; height: auto` |
| 2 | `#task-detail-footer` | `:1501` — `dock: bottom; height: 1` |

Both are yielded as siblings of `#task-detail-dialog` (`compose` `:1590-1631`),
with the footer **last** in DOM order.

Under Textual 8.2.7 same-edge docked siblings do not stack. Where the heights
are equal they get the identical region; where they differ — as here — the
regions **overlap** and the later-in-DOM widget wins. So the 1-row
`q/Esc: cancel` footer is expected to paint over the confirm row's bottom row,
which in the narrow (minimonitor, ~40 col) variant is one of the stacked
buttons (`#pick-buttons` is `layout: vertical` under `.narrow`).

## Provenance

Found while fixing t1499 (the same bug class on minimonitor's **top** edge,
where `#mini-session-bar`, `#mini-shadow-stale` and `#mini-loop-status` were all
painted over by `#mini-own-agent` and never rendered in any state). Not fixed
there: different screen, different guard, and t1499's scope was deliberately
held to the minimonitor top chrome.

**The overlap is inferred from the CSS + DOM order, not yet observed on a
composited frame.** First step is to confirm it by booting the dialog and
reading regions — `tests/test_minimonitor_pick_by_number.py:700-721` already has
a `_ConfirmHost` with region assertions to build on.

## Fix direction

Same as t1499: keep at most one docked widget per edge. Either undock the footer
and let it flow as the last child, or fold both into one docked container.

The guard must assert **rendered geometry** — non-overlapping regions plus the
text present in `screen._compositor.render_strips()` — never `display` /
`visible` / a lone `region`, all of which stay green under this fault. See
`tests/test_minimonitor_top_chrome_render.py` (t1499) for the idiom, and the
`aitask_board.py` `#filter_area` comment (t1278) for the precedent.

**Note the load-bearing comment at `monitor_shared.py:1508-1513`** — it explains
why `#pick-confirm-row { dock: bottom }` exists (the body scroll must give up
space, not the controls). Any fix has to preserve that property.

### Files touched

- `.aitask-scripts/monitor/monitor_shared.py` — `TaskPickConfirmDialog` CSS
  (`:1486-1521`) and `compose` (`:1590-1631`)
