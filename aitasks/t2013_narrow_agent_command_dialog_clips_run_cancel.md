---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [tui, aitask_monitormini]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-15 22:56
updated_at: 2026-10-15 23:13
---

## Symptom

In `ait minimonitor`, the code-agent selection dialog that opens before a
`/aitask-pick` launch (`n` = pick next sibling, `p` = pick task by number)
does **not show its bottom Run / Cancel buttons**: there is not enough vertical
space. The other narrow launch dialogs on the same screen look fine, e.g.
`E` (launch shadow with agent pick).

## Root cause

All of these dialogs are `AgentCommandScreen(..., narrow=True)`
(`.aitask-scripts/lib/agent_command_screen.py`). What differs is the content
above the action buttons, and the narrow CSS spends rows freely.

1. **Only the pick dialog has a Profile row.** `build_pick_screen`
   (`agent_command_screen.py:1276`) passes `skill_name="pick"` (`:1306`), and
   `compose()` renders `#profile_row` (Profile label + `(E)dit` button) only when
   `skill_name` is set. The shadow dialog (`minimonitor_app.py:3725`) and the
   switcher's explore/raw dialogs (`tui_switcher.py:1208`, `:1310`) pass no
   `skill_name`, so they are 8 rows shorter.
2. **Narrow mode stacks rows but keeps wide-mode heights.** The narrow block
   (`:306`–`:360`) switches rows to `layout: vertical`, but:
   - `#agent_row Label, #profile_row Label { height: 3 }` (`:224`) is not
     overridden, so each "Profile: …" / "Agent: …" label takes 3 rows;
   - every stacked button gets `margin: 0 0 1 0` (`:332`);
   - the title's bottom padding, the row margins and the Input margin each add
     another row.
   Rendered at 40×44, about 11 of the dialog's rows are blank.
3. **No overflow fallback.** `#agent_cmd_dialog` (`:202`) is a plain
   `Container`: `height: auto; max-height: 90%` with `overflow: hidden`.
   Content past the bottom is clipped and cannot be scrolled to.
   (`AgentCommandScreen.narrow #agent_cmd_tabs { max-height: 1fr }` at `:318`
   also makes the TabbedContent as tall as the whole dialog, 37 rows at 40×44,
   which is dead space if the dialog becomes scrollable.)

## Measured (Textual 8.2.7, `run_test`, `TMUX` set so the tmux tab is active)

Real minimonitor panes on this machine are 31–40 cols × 44 rows (some 61).

| case | dialog rows (y) | `#btn_run_tmux` y | `#btn_tmux_cancel` y | visible? |
|---|---|---|---|---|
| pick, 40×44 | 0–38 (39) | 41–43 | 45–47 | **both clipped** |
| pick, 35×44 | 0–38 | 41–43 | 45–47 | **both clipped** |
| shadow, 40×44 | 0–38 | 33–35 | 37–39 | Run yes; Cancel only 1 of 3 rows |
| pick, 40×61 | 0–53 (54) | 41–43 | 45–47 | yes |

Rendered pick dialog at 40×44: the dialog ends at the "Window na(m)e:" input.
Rows 2–3, 9–11, 13, 17–18 and 23 are blank, and the 5 rows under the dialog
(90% max-height) are unused.

The dialog also grows **after it opens**, so a shadow, explore or raw dialog that fits
today can overflow too:
- `#btn_use_last_agent` (`:479`, shown by `_refresh_agent_row` after an agent
  override) adds a stacked button: **+4 rows**;
- choosing "+ Create new session" shows `#tmux_new_session_row` (`:704`):
  **+5 rows**;
- the Direct tab (outside tmux) stacks Prompt label, prompt row with its copy button, and
  Copy cmd / Run in terminal / Cancel.

## Goal

The narrow `AgentCommandScreen` always shows its action buttons (Run in tmux /
Cancel on the tmux tab; Run in terminal / Cancel and Copy on the Direct tab), or
can always reach them.

1. **Compact the narrow layout** so the pick dialog's Run/Cancel are fully
   visible **on open** at 31–40 cols × 44 rows, on both tabs. Scope every
   change under `AgentCommandScreen.narrow`: the wide dialog (board, monitor,
   codebrowser, trails, brainstorm) must render exactly as before. Candidate
   cuts: Profile/Agent labels `height: 1` in narrow; drop or shrink the per-button
   stacking margins; trim the title padding and row margins; fix the inflated
   `#agent_cmd_tabs` `max-height: 1fr`. Textual 8.2.7's `Button` accepts
   `compact=True`, a 1-row borderless button, if that reads acceptably in narrow mode.
2. **Guarantee reachability when content still can't fit** (shorter panes,
   use-previous button visible, new-session row shown): the dialog body must
   scroll, and the action buttons must stay reachable. They can stay visible
   by sitting outside the scroll region, or the region can scroll them into view when they take
   focus. Escape/`r` must keep working as before. Keep the existing
   key routing (`on_key`, `ShortcutsMixin` labels, t1279 debounce) intact.

## Tests (extend `tests/test_agent_command_dialog_narrow.py`)

That file currently checks **horizontal** fit only. Add a vertical-fit check:

- Pick dialog (with `skill_name`) and shadow-like dialog (no `skill_name`),
  at (31,44), (35,44), (40,44): every visible action button's region lies
  fully inside `#agent_cmd_dialog`'s content region and inside the screen, on
  the tmux tab **and** the Direct tab.
- **Tallest state** (per the "layout budget: force the widest/tallest
  combination" lesson): profile row, a visible `#btn_use_last_agent` and
  the new-session row all shown together, at a short height (e.g. 40×30).
  Assert the buttons are reachable: visible, or brought into view by
  focusing them or by `scroll_visible`.
- Make the environment deterministic. Today the test inherits ambient `TMUX`
  and real `get_tmux_sessions()` / `is_tmux_available()`, so the active tab
  depends on where the suite runs. Pin `TMUX` and stub the tmux helpers
  imported into `agent_command_screen` (`get_tmux_sessions`,
  `is_tmux_available`, `load_tmux_defaults`).
- **Negative control:** the new pick-at-40×44 vertical assertion must fail
  against the pre-fix CSS.
- Wide mode: the existing `test_default_is_not_narrow` still passes. Add a
  check that the wide dialog's rendered layout or regions at e.g. 120×40 are
  unchanged.

## Repro probe

```python
# run with ~/.aitask/venv/bin/python, TMUX set
import asyncio, os, sys
from pathlib import Path
REPO = Path("<repo>")
sys.path.insert(0, str(REPO / ".aitask-scripts" / "lib"))
from textual.app import App
from textual.widgets import Label
from agent_command_screen import build_pick_screen

class Host(App):
    def compose(self): yield Label("host")
    def on_mount(self): self.push_screen(build_pick_screen(REPO, "5_5", narrow=True))

async def run():
    app = Host()
    async with app.run_test(size=(40, 44)) as pilot:
        for _ in range(4): await pilot.pause()
        s = app.screen
        print(s.query_one("#agent_cmd_dialog").region,
              s.query_one("#btn_run_tmux").region,
              s.query_one("#btn_tmux_cancel").region)
os.environ.setdefault("TMUX", "/tmp/fake,1,0")
asyncio.run(run())
```

## Related (not folded)

- t1570: TaskDetailDialog footer clipped horizontally at 40 cols. Different
  dialog, different axis.
- t1296: AgentCommandScreen key collisions. If the fix moves buttons or
  changes focus order, check it does not collide with that task's key work.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T20:13:53Z status=pass attempt=1 type=human
