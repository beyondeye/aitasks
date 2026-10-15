---
Task: t2013_narrow_agent_command_dialog_clips_run_cancel.md
Base branch: main
Output branch: main
---

# t2013 — Narrow AgentCommandScreen clips Run / Cancel

## Context

In `ait minimonitor`, the `/aitask-pick` launch dialog (`n` / `p` →
`build_pick_screen(..., narrow=True)`) renders its Run in tmux / Cancel buttons
below the bottom edge of the dialog. They are clipped and can't be reached.
The narrow CSS (`.aitask-scripts/lib/agent_command_screen.py:307-360`) stacks
rows vertically but keeps the wide-mode heights: 3-row Profile/Agent labels, a
`margin-bottom: 1` on every stacked button and row, and title padding. The
dialog is also `overflow: hidden`, so content past the bottom can't be
scrolled to. One more cause turned up while probing: `#tmux_content` and
`#direct_content` are plain `Container`s whose default `height: 1fr` fills the
whole dialog. Together with `#agent_cmd_tabs { max-height: 1fr }`, this makes
the TabbedContent 37 rows tall at 40×44, so if the dialog scrolls, the rows
below the buttons are empty.

Outcome: in narrow mode the action buttons are fully visible when the dialog
opens at 31–40 × 44, on both tabs. When the content still doesn't fit (a
shorter pane, the `(U)se previous` button shown, the new-session row shown),
the dialog body scrolls and focusing a button scrolls it into view. The wide
dialog must render exactly as before.

## Approach (CSS only, every rule scoped under `AgentCommandScreen.narrow`)

There are no DOM, compose, focus-order or key-routing changes. `on_key`,
`ShortcutsMixin` labels and the t1279 debounce stay as they are, so this does
not collide with t1296 (which is `Ready`, not in flight). Focus scrolling comes
from Textual itself: `Screen.set_focus(scroll_visible=True)` calls
`scroll_to_center` on any scrollable ancestor.

I validated the design with an in-memory probe (CSS monkeypatched, tmux helpers
stubbed, Textual 8.2.7):

| case | dialog rows | Run / Cancel (y) | scroll |
|---|---|---|---|
| pick tmux 40×44 | 0–35 | 29–31 / 32–34 | none (max_scroll_y 0) |
| pick tmux 31×44 | 0–35 | 29–31 / 32–34 | none |
| pick direct 40×44 | 0–31 | Run term 25–27, Cancel 28–30 | none |
| shadow 40×44 | 0–31 | 25–27 / 28–30 | none |
| tallest 40×30 (profile + use-previous + new-session) | 0–26 | Run 32–34, Cancel 35–37 | max 12; after focus they sit at 20–22 / 23–25 (inside the content area 1–25) |
| tallest 40×30 direct | 0–26 | after focus Run term 20–22, Cancel 23–25 | max 8 |

### Step 1 — `.aitask-scripts/lib/agent_command_screen.py` narrow CSS block

Edit the existing narrow rules and add new ones. Every new rule is narrow-scoped:

1. `AgentCommandScreen.narrow #agent_cmd_dialog`: add `overflow-y: auto;` and
   `scrollbar-size-vertical: 1;`, with a short comment: scroll instead of
   clipping, and a focused control is scrolled into view by
   `Screen.set_focus`.
2. Replace `AgentCommandScreen.narrow #agent_cmd_tabs { max-height: 1fr; }`
   with `max-height: initial;`. This drops the inflating `1fr` and the wide
   `max-height: 20`, which would clip the taller narrow tmux tab inside the
   TabbedContent. Comment why.
3. New: `AgentCommandScreen.narrow #direct_content, AgentCommandScreen.narrow #tmux_content { height: auto; }`.
   Comment: `Container` defaults to `height: 1fr`, which fills the whole
   auto-height dialog with empty rows. This also covers the no-tmux layout,
   where `#direct_content` sits directly in the dialog.
4. New: `AgentCommandScreen.narrow #agent_cmd_title { padding: 0; }`.
5. New: `AgentCommandScreen.narrow #agent_cmd_input { margin: 0; }`.
6. New: `AgentCommandScreen.narrow #agent_row, AgentCommandScreen.narrow #profile_row { margin: 0; }`.
   This is a separate rule, not an addition to the shared
   `#agent_row, #profile_row, .agent-cmd-copy-row, .agent-cmd-buttons` stacking
   rule, because `.agent-cmd-buttons` keeps its 1-row `margin-top` as the
   visual gap above the actions.
7. New: `AgentCommandScreen.narrow #agent_row Label, AgentCommandScreen.narrow #profile_row Label { height: auto; }`.
   One row normally, and it wraps instead of truncating a long agent string or
   an `_skillrun_<pid>_<ms>` override profile name.
8. In the existing stacked-button rule
   (`… #agent_row Button, … #profile_row Button, … .agent-cmd-copy-row Button, … .agent-cmd-buttons Button`),
   change `margin: 0 0 1 0;` to `margin: 0;`. The tall button borders already
   separate the stacked buttons.
9. Add `margin: 0;` to the existing
   `.tmux-field-row, #tmux_new_session_row, #tmux_new_window_row, #tmux_split_row`
   narrow rule. Each of these rows already has its own label line.

I won't use `Button(compact=True)`. The buttons fit with room to spare, and the
other narrow dialogs (NextSiblingDialog, ChooseSiblingModal) use bordered buttons.

### Step 2 — `tests/test_agent_command_dialog_narrow.py`

Rewrite the host and fixture setup around a deterministic environment, and
keep the three existing tests:

- **`_isolate(test, *, tmux_available=True, sessions=…, previous_override=None)`**
  takes an `ExitStack` and registers it with `addCleanup`. It patches:
  - `os.environ` with `TMUX` pinned;
  - on `agent_command_screen`: `is_tmux_available`, `get_tmux_sessions` →
    `["aitasks", "other"]`, `get_tmux_windows` →
    `[("0","monitor"),("1","board")]`, `load_tmux_defaults` → a full defaults
    dict (`default_session: aitasks`, `default_split: horizontal`,
    `prefer_tmux: False`, …), and `_prune_stale_skillrun_overrides` → no-op,
    so it never deletes repo files;
  - `patch.dict(..., clear=True)` on `AgentCommandScreen._previous_agent_override`
    (seeded with `previous_override`), `_last_session_by_project` and
    `_last_window_by_project`;
  - `keybinding_registry._OVERRIDES_CACHE` → `{}` and
    `shortcuts_mixin._LABEL_CASE_CACHE` → `True`, so button labels and widths
    don't depend on the developer's `userconfig.yaml`.
- **`_DialogHost(**screen_kwargs)`** builds a pick-like dialog by default
  (`skill_name="pick"`, `default_profile="fast"`). A `shadow=True` variant
  mirrors `minimonitor_app.py:3725`: `operation="shadow"` and no
  `skill_name`. The host records the dismiss result through the
  `push_screen` callback.
- Helper `_assert_inside_dialog(widget, dialog, size)`:
  - the widget region is non-empty;
  - it lies within `dialog.scrollable_content_region` (which excludes the
    border, padding and scrollbar);
  - it lies within the screen (`0 ≤ y`, `bottom ≤ height`).

New tests:

1. **`test_action_buttons_fit_vertically_on_open`** runs as subTests over
   {pick, shadow} × {(31,44), (35,44), (40,44)} × {tmux tab, Direct tab}. Each
   one checks that every action button on the active tab is inside the dialog
   (tmux: `btn_run_tmux`, `btn_tmux_cancel`; Direct: `btn_copy_command`,
   `btn_run_terminal`, `btn_cancel`, plus `btn_copy_prompt`) and that
   `dialog.scroll_y == 0` (visible on open). There is also a no-tmux subTest
   (`tmux_available=False`, no tabs) at (40,44).
2. **`test_tab_content_has_no_filler_rows`** (40×44, pick, both tabs): the
   active tab container's region ends at its last action button. This pins the
   `height: 1fr` dead-space fix.
3. **`test_tallest_state_buttons_reachable`** at (40,30):
   - Setup: pick, `previous_override={"pick": "codex/gpt5_codex"}`, then set
     the session Select to `_NEW_SESSION_SENTINEL` (the after-open growth path).
   - Assert the tallest state is actually on screen: `#profile_row`,
     `#btn_use_last_agent` and `#tmux_new_session_row` have non-empty regions,
     and `dialog.max_scroll_y > 0`, so the overflow really happens.
   - For each tmux action button: `focus()`, settle, assert it is inside the
     dialog. Then switch to the Direct tab and do the same for its buttons.
4. **`test_keys_work_in_scrolled_narrow_dialog`** (tallest state, 40×30,
   nothing focused): `r` dismisses with a `TmuxLaunchConfig`
   (`new_session=True`, session `aitasks`); in a fresh run, `escape` dismisses
   with `None`.
5. **`test_wide_layout_unchanged`** (120×40, `narrow=False`, tmux tab and
   Direct tab) pins the exact regions captured from the **pre-fix** code
   (comment: Textual 8.2.x; regenerate only for a deliberate wide-mode change):
   - tmux: `agent_cmd_dialog (0,0,96,36)`, `agent_cmd_title (3,2,14,2)`,
     `profile_row (3,4,90,3)`, `btn_edit_profile (19,4,10,3)`,
     `agent_row (3,8,90,3)`, `btn_change_agent (31,8,10,3)`,
     `agent_cmd_input (3,13,90,3)`, `agent_cmd_tabs (3,17,90,20)`,
     `tmux_session_select (15,19,78,3)`, `tmux_window_select (15,23,78,3)`,
     `tmux_new_window_input (15,27,78,3)`, `btn_run_tmux (31,31,16,3)`,
     `btn_tmux_cancel (48,31,16,3)`
   - Direct: the same header widgets, plus `agent_cmd_prompt_label (3,20,75,1)`,
     `btn_copy_prompt (78,20,15,3)`, `btn_copy_command (21,24,16,3)`,
     `btn_run_terminal (38,24,19,3)`, `btn_cancel (58,24,16,3)`

   During implementation I'll re-capture these under the final `_isolate`
   fixture **before** editing the CSS, so the golden really is pre-fix, and
   confirm they match the values above.

### Step 3 — Negative control (isolated copy, never stash or restore in the live tree)

Copy `.aitask-scripts/lib/` into
`<scratchpad>/negctl/.aitask-scripts/lib/` and overwrite
`agent_command_screen.py` there with `git show HEAD:.aitask-scripts/lib/agent_command_screen.py`.
Copy the new test file to `<scratchpad>/negctl/tests/`, then run it from the
scratch root.

Expected:
- the file exits non-zero;
- failing: the pick 40×44 vertical-fit subTests (both tabs, including shadow
  Cancel at 40×44), the filler-row test and the tallest-reachability test;
- passing: the wide golden and the original three tests.

I'll record the command and output in Final Implementation Notes.

## Verification

- `~/.aitask/venv/bin/python -m pytest tests/test_agent_command_dialog_narrow.py -v`
  passes on the fixed code, and the Step 3 negative control fails as expected.
- Neighbouring AgentCommandScreen suites still pass:
  `test_agent_command_open_debounce.py`,
  `test_agent_command_dialog_default_session.py`,
  `test_agent_command_dialog_empty_prompt.py`,
  `test_pick_command_screen.py`, `test_minimonitor_shadow_pick.py`,
  `test_minimonitor_pick_by_number.py`, `test_tui_switcher_agent_launch.py`,
  `test_agent_model_picker_narrow.py`, `test_shortcut_scopes.py`.
- Full Python suite: `bash tests/run_all_python_tests.sh`. Read the final
  verdict line and use `PIPESTATUS` if piping.
- Manual (optional, live): open `ait minimonitor` in a ~40×44 pane and press
  `n`/`p`; Run/Cancel should be visible. In a short pane they should come into
  view with Tab or the mouse wheel.

## Step 9 reference

Current-branch mode under profile `fast`: commit the code (`bug: … (t2013)`)
and the plan separately, then archive via Step 9 (Post-Implementation).

## Risk

### Code-health risk: low
- The narrow dialog becomes a scroll container (`overflow-y: auto`), a new
  behaviour for every narrow host (minimonitor pick/shadow, switcher
  explore/raw in minimonitor) · severity: low · → mitigation: none needed
  (covered by plan Step 2 tests 1–4; all rules narrow-scoped, wide pinned by
  test 5)
- Wide-mode regression through an unscoped rule · severity: low · →
  mitigation: none needed (covered by the pinned pre-fix golden, test 5)

### Goal-achievement risk: low
- The 44-row fit is measured under `run_test` with stubbed tmux data. A real
  pane with a long agent string or a one-shot `_skillrun_*` profile name wraps
  a label by one or two rows · severity: low · → mitigation: none needed (3
  rows of slack at 40×44, plus the scroll + focus fallback covered by test 3)
- In a short pane, keyboard users reach off-screen buttons by Tab focus (which
  scrolls) or the `r`/Escape hotkeys, not by PageDown: the dialog Container is
  not focusable · severity: low · → mitigation: none needed (the task allows
  "scroll them into view when they take focus"; test 3 pins it)
