---
Task: t2025_fix_new_session_hides_window_name_input.md
Base branch: main
Output branch: main
---

# t2025 — Keep the window-name row visible after "+ Create new session"

## Context

In the agent command dialog (`AgentCommandScreen`, shared by board, trails,
monitor, minimonitor, codebrowser and brainstorm), choosing "+ Create new
session" on the tmux tab hides the "Window na(m)e" input. The user cannot see or
edit the window name. The launch still uses the hidden default
(`TmuxLaunchConfig(new_session=True, new_window=True, window=<default>)`), so the
launch works but a control is missing.

**Root cause (confirmed with Textual 8.2.7 source + an in-memory probe):**
`on_session_changed(sentinel)` → `_show_new_session_input()` →
`win_select.set_options([])`. `set_options` calls `_init_selected_option()`,
which sets `value = NULL`. When the window Select held a real value (the
"✦ New window" sentinel on open, or a window index), the `_watch_value` watcher
posts `Select.Changed(NULL)`. The following `clear()` is a no-op (the value is
already NULL). `_show_new_session_input` then shows `#tmux_new_window_row`, but the
queued `Changed(NULL)` reaches `on_window_changed` → `_on_window_changed(NULL)`.
Its else-branch calls `_hide_new_window_input()`.

Probe (current code): after choosing the sentinel, `tmux_new_window_row` is
`(0,0,0,0)` in both wide (120×40) and narrow (40×44). The no-sessions-at-open
path (initial value is already the sentinel) shows the row, because
NULL→NULL posts nothing.

The intended rule is already encoded in `_build_tmux_config`
(`agent_command_screen.py:1271`): `if new_session or win_select.value ==
_NEW_WINDOW_SENTINEL` → read `#tmux_new_window_input`. The row's visibility
should follow that same rule.

## Implementation

### 1. Write the tests first (red proof on the unfixed code)

File: `tests/test_agent_command_dialog_narrow.py` (it already holds `_isolate`,
`_DialogHost`, `_settle`, `_enter_tallest_state`, `_assert_inside_dialog`, and
t2020's tallest-state tests). Add a t2025 paragraph to the module docstring.

Add the new tests as methods of the existing `AgentCommandDialogNarrowTests`.
That class already covers wide mode too (t2020) and owns `setUp` → `_isolate`,
`_run` and `_assert_inside_dialog`, so nothing needs refactoring.

a. `test_new_session_shows_window_name_row`. For each mode in
   `((True, (40, 44)), (False, _WIDE_SIZE))` × each prior window state
   (`"new"` = the open default `_NEW_WINDOW_SENTINEL`; `"existing"` = window
   Select set to `"1"` first, so the split row is showing), run as a subTest:
   - open `_DialogHost(narrow=…)`, `_settle`. For `"existing"`, set
     `#tmux_window_select` `.value = "1"`, `_settle`, and assert as a
     precondition that `#tmux_split_row` is displayed and `#tmux_new_window_row`
     is not.
   - `_enter_tallest_state(app, pilot)` (sets the session Select to
     `acs._NEW_SESSION_SENTINEL`, which posts the same `Changed` a user's choice
     does).
   - assert `#tmux_new_window_row` region is non-zero and `#tmux_split_row` is
     zero-sized.
   - `screen.set_focus(None)`, `await pilot.press("m")`, `_settle`. Assert
     `app.focused` is `#tmux_new_window_input` and
     `_assert_inside_dialog(screen, "tmux_new_window_input", size)` (focus
     scrolls it into view, so this holds on the overflowing new-session state).
   - edit through keys: `pilot.press("end", "ctrl+u", *"my-win")` (the Input
     selects all on focus; `end` drops the selection, `ctrl+u` is Textual
     Input's `delete_left_all`). Assert the input value is `"my-win"`.
   - `screen.set_focus(None)`, press `"r"`, `_settle`. Assert the dialog
     dismissed with one `TmuxLaunchConfig`: `new_session=True`,
     `session="aitasks"`, `new_window=True`, `window="my-win"`.

b. `test_switching_back_to_existing_session_follows_window_select`. Guards
   the new predicate against leaking into an existing session. Choose the
   sentinel, then set the session Select to `"other"`, `_settle`:
   - the window Select is repopulated with the new-window default, so
     `#tmux_new_window_row` is displayed and `#tmux_split_row` is not;
   - set the window Select to `"1"`, `_settle`: `#tmux_new_window_row` is
     hidden and `#tmux_split_row` is displayed.
   Run in both modes.

Run the file. (a) must fail on the current code: the region assertion reports
"not displayed" or zero-sized. (b) should already pass, because it pins behaviour
the fix must keep.

### 2. Fix `.aitask-scripts/lib/agent_command_screen.py`

Add a helper next to the other session/window helpers:

```python
    def _new_session_pending(self) -> bool:
        """True while the session selector holds "+ Create new session"."""
        try:
            sess_select = self.query_one("#tmux_session_select", Select)
        except Exception:
            return False
        return sess_select.value == _NEW_SESSION_SENTINEL
```

Change the first branch of `_on_window_changed` (currently `:758`):

```python
    def _on_window_changed(self, value) -> None:
        # A new session always launches into a new window (_build_tmux_config),
        # so its name row stays shown whatever the window Select holds — the
        # Changed(NULL) that _show_new_session_input's set_options([]) posts
        # arrives here after that row was shown.
        if value == _NEW_WINDOW_SENTINEL or self._new_session_pending():
            self._show_new_window_input()
            self._selected_window = None
        elif value and value != Select.NULL:
            ...unchanged...
```

The rule keys on the session Select's live value, not on `_selected_session`.
`_selected_session` is also `None` when the session Select is blank. This is
also the value `_build_tmux_config` reads. Keying on the session Select
also makes the rule independent of the order in which messages from the two
Selects arrive. Nothing else changes: `_show_new_session_input`
still shows the row immediately, and `_update_window_options` (an existing
session) runs with the session Select already off the sentinel.

### 3. Re-check t2020's tallest-state tests (same file)

The new-session state now shows the window-name row too, so it is one row group
taller in both modes:
- `_enter_tallest_state` docstring: list the window-name row in the "all at
  once" set.
- `test_tallest_state_buttons_reachable`: add `"tmux_new_window_row"` to the
  `shown` list, so the tallest fixture asserts the tallest combination is on screen.
- `test_keys_work_in_scrolled_dialog`: unchanged. It still launches with the
  default `agent-pick-5_5`, and that remains correct.
The scroll fallback should absorb the extra height. These tests prove it
(`max_scroll_y > 0` and every action button stays reachable by focus).

## Verification

- `python3 -m pytest tests/test_agent_command_dialog_narrow.py -v`: red for
  test (a) before step 2, all green after it (including the wide goldens. The
  open state is unchanged because the session is not the sentinel).
- The dialog's sibling test modules:
  `python3 -m pytest tests/test_agent_command_dialog_default_session.py
  tests/test_agent_command_dialog_empty_prompt.py
  tests/test_agent_command_open_debounce.py -q`.
- Docs: no user-facing page describes this dialog path (grep for
  "Create new session" in `website/content/` finds nothing), so there are no doc changes.

## Step 9 reference

Current-branch mode (profile `fast`): no worktree or merge. Step 9 archives the
task and plan after the Step 8 review commit.

## Risk

### Code-health risk: low
- The new-session tmux state grows by one row group in both dialog modes, so
  short terminals overflow a little more · severity: low · → mitigation: none
  needed — t2020's scroll fallback absorbs it, and step 3 strengthens the
  tallest-state test so that it asserts the row is shown and every button is
  still reachable.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** As planned. `.aitask-scripts/lib/agent_command_screen.py`
  gained `_new_session_pending()` (reads the live `#tmux_session_select` value),
  and `_on_window_changed` now shows the window-name row when
  `value == _NEW_WINDOW_SENTINEL or self._new_session_pending()`. In
  `tests/test_agent_command_dialog_narrow.py`: a t2025 docstring paragraph, a
  `_assert_window_rows` helper,
  `test_new_session_shows_window_name_row` (narrow 40x44 and wide 120x40 ×
  prior window = new-window default / existing window "1"; checks the row is
  shown and the split row hidden, `m` focuses the input inside the dialog,
  `end`+`ctrl+u`+typing edits it, and `r` launches
  `TmuxLaunchConfig(new_session=True, session="aitasks", new_window=True, window="my-win")`),
  `test_switching_back_to_existing_session_follows_window_select`, and
  `"tmux_new_window_row"` added to the `shown` list of
  `test_tallest_state_buttons_reachable` (with the `_enter_tallest_state`
  docstring updated).
- **Deviations from plan:** None. The new tests are methods of the existing
  `AgentCommandDialogNarrowTests` class, as the revised plan said.
- **Issues encountered:** None. Red proof, taken before the source fix:
  `test_new_session_shows_window_name_row` failed with
  `#tmux_new_window_row Region(x=0, y=0, width=0, height=0)`, and the
  strengthened `test_tallest_state_buttons_reachable` failed with
  `#tmux_new_window_row not shown`. The switch-back test passed both before and
  after, as intended. After the fix, the four dialog test modules (45 tests) and
  `tests/test_textual_markup_colours.py` (48 tests) all pass.
- **Key decisions:** The row is keyed on the session Select's live value, not on
  `_selected_session` (which is also `None` for a blank session) and not on
  the window `value == NULL`. This mirrors `_build_tmux_config`'s rule (a new
  session always gets a new window) and does not depend on the order in which
  the two Selects' `Changed` messages arrive. Textual 8.2.7 detail: the
  `Changed(NULL)` comes from `set_options([])` → `_init_selected_option()`; the
  following `clear()` is a no-op on an already-NULL value. The no-sessions
  open path therefore never had the bug, because NULL→NULL posts nothing.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/agent_command_screen.py:1294-1297` — on an existing
    session, choosing the window Select's blank entry (`allow_blank=True`) hides
    both the window-name row and the split row, yet `_build_tmux_config` falls
    through to "Default to new window" and launches a new window under the
    hidden default name. A hidden control decides the launch, the same class of
    problem as t2025, reached through the blank option instead of the
    new-session path.
