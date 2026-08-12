---
priority: high
effort: low
depends: [1498]
issue_type: bug
status: Ready
labels: [tui, aitask_monitormini, shadow]
anchor: 1159
followup_kind: verification_failure
created_at: 2026-08-12 17:21
updated_at: 2026-08-12 17:21
---

## Failed verification item from t1498

> **Before** sending any recheck: press `c` again. Confirm the picker now
> shows the red stale banner, and that it names the round and how far the
> block predates the change. Confirm `#mini-shadow-stale` also warns.

The **picker** half passed. The `#mini-shadow-stale` half failed.

## The defect

`#mini-shadow-stale` — minimonitor's live shadow-staleness banner — **never
renders**, in any state. Nor does `#mini-session-bar`. Both are painted over by
`#mini-own-agent`.

`MiniMonitorApp.compose` yields three widgets that all set `dock: top`
(`.aitask-scripts/monitor/minimonitor_app.py:470-474`, CSS at
`:275-299`):

| DOM order | id | CSS |
|---|---|---|
| 1 | `#mini-session-bar` | `dock: top; height: 1` |
| 2 | `#mini-shadow-stale` | `dock: top; height: auto` |
| 3 | `#mini-own-agent` | `dock: top; height: auto` |

Under **Textual 8.2.7** (the pinned runtime in `~/.aitask/venv`), sibling
widgets docked to the same edge do **not** stack — they are all assigned the
identical region and only the **last in DOM order** is composited. So
`#mini-own-agent` wins and the two above it are invisible forever.

The state machine behind the banner is fine — `_refresh_shadow_stale_banner`
computes the right verdict and `_set_shadow_stale_banner` writes the right
text. Only the *surface* is dead. This makes the t1493 docstring claim that the
live banner "owns the became-stale transition"
(`minimonitor_app.py:2257-2262`) untrue in production: the picker is currently
the only place a user can ever see staleness.

**Not a t1493 regression.** t1493 added a new signal to an already-dead
surface. The overlap dates from whenever `#mini-own-agent` became the third
`dock: top` sibling (the t1382/t1383 followed-agent panel).

## Evidence

Compositor dump from the **real** `MiniMonitorApp` (headless `run_test`,
40x30), after `_set_shadow_stale_banner(...)` and a session-bar update:

```
mini-session-bar     dock=top height=1     region=Region(x=0, y=0, width=40, height=1)
mini-shadow-stale    dock=top height=auto  region=Region(x=0, y=0, width=40, height=1)
mini-own-agent       dock=top height=auto  region=Region(x=0, y=0, width=40, height=1)
mini-pane-list       dock=none height=1fr  region=Region(x=0, y=1, width=40, height=21)
mini-key-hints       dock=bottom           region=Region(x=0, y=22, width=40, height=8)

y=0: '                                        '   <- blank; neither marker painted
y=1: ' ── aitasks ──                          '
```

Minimal Textual 8.2.7 control (three `dock: top` Statics A/B/C): all three get
`Region(0,0,20,1)` and row 0 renders `'CCC'` only.

Live confirmation, `tmux -L ait capture-pane -p` on two independently launched
minimonitor panes (`%271`, `%276`): the session-bar text
(`"<session>  N agents"`, written unconditionally every tick by
`_rebuild_session_bar`) appears **nowhere** in either pane, and no `⚠` appears
while the picker opened from the same app simultaneously reported
`⚠ These concerns may be stale — the agent has moved on — round 1 was produced
1m33s before the agent's latest change`.

## Fix direction

Stop docking siblings to the same edge. Wrap the top chrome in a single
`dock: top` container (e.g. a `Vertical`) holding the session bar and the
staleness banner, with the own-agent panel following it in normal flow — or
give each its own dock-free slot in a vertical layout. Whatever the shape, the
regression guard must assert **rendered geometry**, not widget state:
non-overlapping `region`s for the three, and the banner/session-bar text
present in `render_strips()`. Asserting `_shadow_stale_banner_text` alone is
exactly what let this survive.

Note the fix restores `#mini-session-bar` too, which will consume a row that
minimonitor panes have not been paying for — check the narrow-width layout.

### Source

- **Manual-verification task:** `aitasks/t1498_live_recheck_round_positive_control.md` (item #5)
- **Origin feature task:** t1498 (verification of t1493)

### Commits that introduced the failing behavior

_(not a commit regression — see "Not a t1493 regression" above)_

### Files touched

- `.aitask-scripts/monitor/minimonitor_app.py` — `compose` (:470-474), `DEFAULT_CSS` (:275-299)
