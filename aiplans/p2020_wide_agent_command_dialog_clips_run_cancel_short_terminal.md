---
Task: t2020_wide_agent_command_dialog_clips_run_cancel_short_terminal.md
Base branch: main
Output branch: main
---

# t2020: wide AgentCommandScreen clips Run / Cancel on short terminals

## Context

t2013 made the **narrow** agent-command dialog (minimonitor) scroll instead of
clip. The **wide** dialog, used by board, monitor, codebrowser, trails,
brainstorm and the switcher, still clips its buttons. Three rules in
`.aitask-scripts/lib/agent_command_screen.py` cause this:

- `#agent_cmd_dialog` is a plain `Container` with `overflow: hidden`, so content
  below the bottom edge cannot be scrolled to.
- `#agent_cmd_tabs { max-height: 20 }` caps the tabs.
- `#tmux_content` and `#direct_content` use `Container`'s default `height: 1fr`,
  which pads each tab out to that cap with blank rows. At 120×40 the tabs sit at
  y17..36, past the dialog's bottom edge at 35.

Below about 40 rows, Run in tmux / Cancel (and the Direct tab's buttons at 30
rows) sit below the dialog edge. Tab focus does not bring them into view.

Outcome: the wide dialog sizes to its content and scrolls when that content is
taller than the terminal. Focusing a button (Tab) scrolls it into view, and the
mouse wheel scrolls the body. At 40 rows or more the tmux tab renders as it does
now. The Direct tab drops its 7 filler rows, which in centered hosts moves its
controls (see "Accepted layout change" below).

### Measured design (in-memory probe, Textual 8.2.7, the test file's `_isolate` fixture, CSS monkeypatched)

Wide pick dialog, opened state. "focus" means each action button was focused in
turn and then checked against the dialog's content region.

| size / tab | current: buttons on open → after focus | proposed: on open → after focus |
|---|---|---|
| 120×44, 120×40, both tabs | ok → ok | ok → ok (`max_scroll_y` 0) |
| 120×38 tmux | CLIP → **CLIP** | CLIP → ok (max 2) |
| 120×34 tmux | CLIP → **CLIP** | CLIP → ok (max 6) |
| 120×30 tmux / direct | CLIP → **CLIP** / CLIP → **CLIP** | CLIP → ok (max 9) / CLIP → ok (max 2) |
| 120×24 tmux / direct | CLIP → **CLIP** | CLIP → ok (max 15 / 8) |

The same results hold in the "tallest" state (`(U)se previous` shown plus
"+ Create new session" chosen). In wide mode that state is **no taller** than
the open state: `(U)se previous` sits inside the horizontal agent row, and the
new-session row replaces the new-window row (see "Upstream defect observed"
below). Short terminals are therefore the only trigger for the wide case.

### Accepted layout change: the dialog height follows the active tab

The wide dialog's height now follows the active tab, as the narrow dialog's
already does. At 120×40 the tmux-tab dialog keeps its 36 rows (the tabs go
20 → 17 rows, which only removes clipped filler). The Direct-tab dialog shrinks
36 → 29 rows. Where its controls end up depends on the host's `Screen` CSS:

- **Top-anchored hosts**: monitor, codebrowser, minimonitor, and the test file's
  `_DialogHost`. `ModalScreen` sets no `align`, so only the bottom edge moves
  and **no control moves**. The test golden: `agent_cmd_tabs` (3,17,90,20) →
  (3,17,90,17) tmux / (3,17,90,10) Direct; Direct `agent_cmd_dialog`
  (0,0,96,36) → (0,0,96,29). Every other region is unchanged.
- **Centered hosts**: board (`aitask_board.py:2006`), trails
  (`trails_app.py:228`) and brainstorm (`brainstorm/styles.py:4`) all set
  `Screen { align: center middle; }`. Probe at 120×40:
  - On the **Direct tab** the dialog re-centers from (12,2,96,36) to
    (12,5,96,29), so every Direct control moves **down 3 rows**. Copy cmd /
    Run in terminal / Cancel go y26 → y29; Copy Prompt goes y22 → y25; the tab
    bar goes y19 → y22.
  - The **tmux tab is unchanged**: dialog (12,2,96,36), Run / Cancel at y33.
  - Consequence: switching tmux ⇄ Direct in these hosts now shifts the tab
    bar by 3 rows. Today it stays put, because both tabs are padded to the
    same 20-row cap.

**This movement is accepted deliberately.** The filler rows that kept both tabs
the same height are what clipped the buttons. Keeping the height stable would
mean either reintroducing filler, or giving the tabs a `min-height` coupled to
the tmux tab's current row count. That second option is fragile, because the
count changes with the new-session, split and (U)se-previous states. The task
allows a deliberate wide-layout change. A centered-host test (Step 2 item 8)
documents the movement, so it is pinned rather than accidental.

The short-terminal fix behaves the same in a centered host. Probe at
120×{38,34,30,24}, both tabs: every action button sits inside the dialog's
content region after focus.

## Implementation

### Step 1: CSS in `.aitask-scripts/lib/agent_command_screen.py` (no DOM, compose, focus or key change)

Make the scroll behaviour a property of the **base** rules, so both modes
share it. Then delete the three narrow-only duplicates that become redundant.
The probe showed this consolidation leaves the narrow layout **identical**: 0
region differences over 12 cases ({31×44, 40×44, 40×30} × both tabs ×
{open, tallest}).

1. Base `#agent_cmd_dialog`: add `overflow-y: auto;` and
   `scrollbar-size-vertical: 1;`. Move the narrow rule's comment here and widen
   it to "Scroll instead of clipping when the content outgrows the terminal (a
   short terminal, a narrow pane, the new-session row shown).
   Screen.set_focus scrolls a focused control into view."
2. Base `#agent_cmd_tabs`: drop `max-height: 20;` and keep `height: auto;`.
   Comment: no cap, because once the dialog scrolls a cap only clips the tab
   content inside the TabbedContent, and the Run/Cancel row is clipped first.
3. New base rule `#direct_content, #tmux_content { height: auto; }`, with the
   existing comment "Container defaults to height: 1fr, which in the
   auto-height dialog fills it with blank rows below the buttons." This also
   covers the no-tmux layout, where `#direct_content` sits directly in the
   dialog.
4. Narrow block: remove `overflow-y: auto; scrollbar-size-vertical: 1;` and its
   comment from `AgentCommandScreen.narrow #agent_cmd_dialog`. Delete the
   `AgentCommandScreen.narrow #agent_cmd_tabs { max-height: initial; }` rule and
   the `AgentCommandScreen.narrow #direct_content, … #tmux_content { height: auto; }`
   rule, with their comments. Every other narrow rule stays.

Screen `DEFAULT_CSS` is scoped (`SCOPED_CSS = True`), so the new base
`#tmux_content` rule cannot reach `settings_app.py`'s unrelated
`VerticalScroll#tmux_content`. `test_settings_reload_all.py` is in the
neighbour run regardless.

### Step 2: tests in `tests/test_agent_command_dialog_narrow.py` (written first, run red against the HEAD module)

Reuse the existing `_isolate`, `_DialogHost(narrow=…)`, `_settle`, `_show_tab`,
`_enter_tallest_state` and `_assert_inside_dialog` helpers. The only new
fixture is the one-line `_CenteredDialogHost` subclass (item 8).

1. Module docstring: add a t2020 paragraph. The wide dialog gets the same
   fallback: content-sized tabs, and a scrolling body on short terminals.
2. Regenerate the golden (`test_wide_layout_unchanged`):
   - Move `agent_cmd_dialog` and `agent_cmd_tabs` out of the shared
     `_WIDE_HEADER` and into each tab's entry: tmux `(0,0,96,36)` /
     `(3,17,90,17)`, Direct `(0,0,96,29)` / `(3,17,90,10)`. All other values stay
     unchanged.
   - Rewrite the comment: values captured after t2020. Relative to t2013 only
     the tab heights and the Direct-tab dialog height changed, and every
     control is where it was. Regenerate only for a deliberate wide-layout
     change.
   - Update the docstring to match.
3. Add the constant `_WIDE_SHORT_SIZES = ((120, 38), (120, 34), (120, 30))`,
   taken from the task's measured clipped rows.
4. New test `test_wide_buttons_reachable_on_short_terminal`: subTests over
   host {`_DialogHost`, `_CenteredDialogHost`} × sizes × {tmux, Direct}, wide,
   open state. For the tmux tab, first assert `dialog.max_scroll_y > 0`, which
   pins that the matrix really scrolls at every size. Then focus each action
   button in `_ACTIONS[tab]`, settle, and `_assert_inside_dialog`. The centered
   host is where board, trails and brainstorm users hit the bug.
5. `test_tab_content_has_no_filler_rows`: also run it wide at (120,44). Loop
   `(narrow, size)` over `((True, (40, 44)), (False, (120, 44)))` × the existing
   tab cases.
6. `test_tallest_state_buttons_reachable`: also run it wide. Loop
   `(narrow, size)` over `((True, _SHORT_PANE), (False, (120, 30)))`. The
   shown-rows assertion holds in wide too (the probe showed `profile_row`,
   `btn_use_last_agent` and `tmux_new_session_row` all on screen), and so does
   `max_scroll_y > 0` (9 on tmux, 2 on Direct).
7. `test_keys_work_in_scrolled_narrow_dialog`: rename it to
   `test_keys_work_in_scrolled_dialog` and run both modes (narrow `_SHORT_PANE`,
   wide (120,30)), with the same `r` → `TmuxLaunchConfig` and Escape → `None`
   assertions. This pins that the now-scrollable wide Container does not take
   the keys.
8. New host class `_CenteredDialogHost(_DialogHost)` with
   `CSS = "Screen { align: center middle; }"`. Its docstring names the three
   hosts it mirrors (board, trails, brainstorm). New test
   `test_wide_layout_in_centered_host` (120×40, both tabs) pins
   `agent_cmd_dialog`, `agent_cmd_tabs` and each tab's action buttons:
   - tmux: dialog (12,2,96,36), tabs (15,19,90,17), `btn_run_tmux`
     (43,33,16,3), `btn_tmux_cancel` (60,33,16,3);
   - Direct: dialog (12,5,96,29), tabs (15,22,90,10), `btn_copy_prompt`
     (90,25,15,3), `btn_copy_command` (33,29,16,3), `btn_run_terminal`
     (50,29,19,3), `btn_cancel` (70,29,16,3).

   The comment states that the Direct tab's 3-row drop (from y2/y26 pre-t2020)
   is the accepted, deliberate consequence of content-sizing in centered hosts.

### Step 3: negative control (live tree, before the CSS edit; never stash or restore)

With the tests written and `git diff --quiet HEAD -- .aitask-scripts/lib/agent_command_screen.py`
confirming the module is still at HEAD, run
`~/.aitask/venv/bin/python tests/test_agent_command_dialog_narrow.py`.

Expected: non-zero exit.
- Should fail: both wide golden subTests, both centered-host golden subTests
  (tmux on the tabs height only; Direct on the dialog, tabs and buttons), the
  wide filler-row subTests, the wide tallest-reachability subTests, and the
  new short-terminal test in both hosts (tmux at every size, Direct at
  120×30).
- Should pass: every narrow subTest. The wide keys subTest is expected to pass
  too, as a regression pin.

Record the command and the failure summary in Final Implementation Notes. Then
apply Step 1 and re-run to green.

## Verification

- `~/.aitask/venv/bin/python tests/test_agent_command_dialog_narrow.py`: red
  before Step 1 (as Step 3 expects), green after.
- Every test module that references `AgentCommandScreen` (25 files, from
  `grep -l AgentCommandScreen tests/*.py`) plus `test_settings_reload_all.py`,
  via `~/.aitask/venv/bin/python -m pytest -n 4 --dist loadfile <files>`.
- Full suite: `bash tests/run_all_python_tests.sh`. Read only the final
  `PYTHON SUITE:` verdict line, and use `PIPESTATUS` if piping.

## Upstream defect observed (out of scope; report at Step 8b)

Choosing "+ Create new session" in the tmux tab hides the window-name input,
although `_show_new_session_input` explicitly shows it ("always create new
window"). The cause is the call order: `win_select.clear()` posts a
`Select.Changed(NULL)`, and its handler `_on_window_changed` runs the
else-branch, `_hide_new_window_input()`. The launch then uses the hidden
default name (`agent-pick-5_5` in the keys test), so the user cannot edit it.
The probe shows this in both modes (`tmux_new_window_row` region 0×0). It is
not touched here.

## Step 9 reference

Current-branch mode under profile `fast`: commit the code as
`bug: … (t2020)` and the plan separately, then archive via Step 9
(Post-Implementation).

## Risk

### Code-health risk: low
- The CSS change applies to every wide host (board, monitor, codebrowser,
  trails, brainstorm, switcher). The dialog becomes a scroll container, and its
  height now follows the active tab: the Direct tab is 7 rows shorter at
  120×40.
  - In top-anchored hosts no control moves.
  - In the centered hosts (board, trails, brainstorm) the Direct tab's
    controls drop 3 rows, and switching tabs shifts the tab bar.

  This is accepted deliberately (see "Accepted layout change"). · severity:
  low · → mitigation: none needed (the top-anchored golden and the
  centered-host golden, Step 2 items 2 and 8, pin both outcomes; Step 2 items
  4–7 cover scrolling and keys)
- Folding the narrow-only rules into the base rules could shift the narrow
  layout. · severity: low · → mitigation: none needed (the probe showed 0
  region diffs over 12 narrow cases; the existing narrow tests stay green)

### Goal-achievement risk: low
- Between about 30 and 38 rows the buttons are still below the fold when the
  dialog opens. They are reachable by Tab (which scrolls), by mouse wheel, and
  by the `r` / Escape hotkeys, and the dialog shows a scrollbar. Compacting the
  wide layout so they fit on open is not what the task asks for. · severity:
  low · → mitigation: none needed (the task's suggested fix is this exact
  fallback; Step 2 test 4 pins reachability at 38/34/30 rows)
