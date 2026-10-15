---
Task: t2027_fix_blank_window_select_hides_new_window_name.md
Base branch: main
Output branch: main
---

# t2027 — Blank window choice: show the name row the launch uses

## Context

In the agent command dialog's tmux tab, the window Select is built with
`allow_blank=True`, so its overlay offers a blank entry. On an **existing**
session, choosing it sets the value to `Select.NULL`. Two parts of
`.aitask-scripts/lib/agent_command_screen.py` then disagree:

- `_on_window_changed` (lines 766-787) sends NULL to its `else` branch, which
  hides **both** the window-name row and the split row.
- `_build_tmux_config` (lines 1283-1297) sends NULL to its final `else`
  ("Default to new window"), which launches `new_window=True` under
  `self.default_window_name`. It does not read `#tmux_new_window_input`.

So a control the user cannot see decides the launch. This is the same kind of
bug t2025 fixed for the new-session path, reached here through the blank entry.

**Chosen fix (task suggestion 1):** treat the blank value like
"✦ New window". Both sides branch on one shared predicate, so the visible rows
and the launch agree by construction:

- `_on_window_changed` shows the name row.
- `_build_tmux_config` launches a new window named by that row's input. An
  edited name is now honoured too, which the old fallback ignored.

**Rejected: `allow_blank=False`.** In Textual 8.2.7 it raises
`EmptySelectError` for the empty option list that the new-session path builds
at construction and passes to `set_options([])`, and `clear()` raises
`InvalidSelectValueError`. The t2025 new-session flow would have to be rebuilt.

**Ordering facts relied on (Textual 8.2.7, `_select.py`):**

- `set_options()` always resets the value to NULL (`_init_selected_option()`),
  and `_watch_value` posts `Changed` only when the value changes.
- A session switch (`_update_window_options`) therefore queues `Changed(NULL)`
  and then `Changed(<computed value>)`. The last message wins, because
  `_on_window_changed` depends only on (value, whether a new session is pending).
- The computed value is never NULL, so the transient NULL briefly shows the
  name row and the final message settles the rows. A new test pins this.

## Implementation

### 1. `.aitask-scripts/lib/agent_command_screen.py`: shared predicate

Add a module-level helper next to `should_default_to_new_window` (it needs
`_NEW_WINDOW_SENTINEL` and `Select`, both already in scope):

```python
def _is_existing_window(value) -> bool:
    """True when a window Select value names a live window to split into.

    Every other value — "✦ New window" and the blank entry alike — launches a
    new window named by #tmux_new_window_input. _on_window_changed (which row
    shows) and _build_tmux_config (what launches) both branch on this one
    test, so a visible control always decides the launch (t2027).
    """
    return bool(value) and value != Select.NULL and value != _NEW_WINDOW_SENTINEL
```

### 2. `_on_window_changed`: two branches instead of three

```python
    def _on_window_changed(self, value) -> None:
        # Mirrors _build_tmux_config: only an existing window on an existing
        # session splits. Everything else launches a new window named by the
        # name row, so that row shows — for "✦ New window", for the blank entry
        # (t2027), and while a new session is pending whatever the window
        # Select holds, since the Changed(NULL) that _show_new_session_input's
        # set_options([]) posts arrives after that row was shown (t2025).
        if _is_existing_window(value) and not self._new_session_pending():
            self._hide_new_window_input()
            self._selected_window = value
            # Show split direction for existing windows
            try:
                self.query_one("#tmux_split_row").remove_class("hidden")
            except Exception:
                pass
        else:
            self._show_new_window_input()
            self._selected_window = None
```

The old third branch (hide both rows) goes away. NULL was the only value that
could reach it, and NULL is now a new-window case. `_show_new_window_input`
already hides the split row.

### 3. `_build_tmux_config`: same predicate, input name for every new window

Replace the window-resolution `if / elif / else` (lines 1283-1297) with:

```python
        if (
            not new_session
            and win_select is not None
            and _is_existing_window(win_select.value)
        ):
            window = win_select.value
            new_window = False
        else:
            # A new window — "✦ New window", the blank entry or a new session:
            # the states whose name row _on_window_changed shows (t2027).
            try:
                window = self.query_one("#tmux_new_window_input", Input).value.strip()
            except Exception:
                window = ""
            if not window:
                window = self.default_window_name or "aitask"
            new_window = True
```

The fallbacks are unchanged: an empty input falls back to the default name, and
a missing input does too. When `win_select` is `None`, the old code used the
default name directly. The new code reads the input first, which in practice is
also missing, so the result is the same.

### 4. `tests/test_agent_command_dialog_narrow.py`

- **Module docstring:** add a t2027 paragraph after the t2025 one. Choosing the
  window Select's blank entry on an existing session used to hide both rows
  while the launch created a new window under the hidden default name. It now
  shows the name row, and the launch uses that row's input.
- **`_DialogHost`:** add an optional `default_tmux_window: str | None = None`
  and pass it to the non-shadow `AgentCommandScreen`. The default leaves every
  existing caller unchanged.
- **New `test_blank_window_choice_shows_window_name_row`** (a method of
  `AgentCommandDialogNarrowTests`). It runs in narrow `(40, 44)` and wide
  `_WIDE_SIZE`, × `prior` ∈ {"new" (the "✦ New window" default), "existing"
  (window "1")}:
  1. Settle. For `prior == "existing"`, set the window Select to `"1"`, settle,
     and use `_assert_window_rows(screen, False, …)` as a precondition.
  2. Blank the window Select the way a user does. `screen.set_focus(None)`,
     press `w` and assert the window Select is focused. Then press `enter`
     (opens the overlay), `home` (the blank entry at index 0) and `enter`, and
     settle. Assert `win_select.value is Select.NULL`, so the blank state was
     really reached through the overlay.
  3. `_assert_window_rows(screen, True, where)`: name row shown, split row
     hidden. Assert the name input shows `"agent-pick-5_5"`.
  4. As in t2025's test: `set_focus(None)`, press `m`, assert the name input
     is focused, and `_assert_inside_dialog(screen, "tmux_new_window_input", …)`.
     Press `end`, `ctrl+u`, then type `my-win`, and assert the value.
  5. `set_focus(None)`, press `r`. The screen dismisses. Assert one
     `TmuxLaunchConfig` with `new_session=False`, `session="aitasks"`,
     `new_window=True` and `window="my-win"`.

  The two halves fail separately. Without step 2 of the fix, the row assertion
  fails. Without step 3, `window` is `"agent-pick-5_5"` instead of `"my-win"`.
- **New `test_session_switch_keeps_existing_window_default`**: a
  characterization guard for the message order above. It uses
  `_DialogHost(narrow, default_tmux_window="1")` in both modes:
  1. On open, the window value is `"1"` and the rows are `False` (split shown).
  2. Set the session Select to `"other"` and settle. The window value is still
     `"1"` and the rows are still `False`, even though the transient
     `Changed(NULL)` from `set_options` now shows the name row for a moment.
  3. Press `r`. Expect `session="other"`, `new_session=False`,
     `new_window=False` and `window="1"`.

  It passes both before and after the fix, by design. It pins the final state
  the new NULL handling must still settle to.

## Verification

1. **Red proof, isolated** (never stash or restore in this dirty shared
   worktree). Write a scratch runner in the session scratchpad that loads
   `git show HEAD:.aitask-scripts/lib/agent_command_screen.py` as a separate
   module (`acs_head`). It patches `AgentCommandScreen` methods with the HEAD
   versions and runs only the new blank test, once per patch set:
   - both methods → the blank test fails on the rows
   - only `_on_window_changed` → fails on `#tmux_new_window_row`
   - only `_build_tmux_config` → fails on `window == "agent-pick-5_5"`

   The session-switch guard passes under all three, as intended.
2. `~/.aitask/venv/bin/python -m pytest tests/test_agent_command_dialog_narrow.py -q`
   passes.
3. The neighbouring dialog modules pass unchanged:
   `tests/test_agent_command_dialog_default_session.py`,
   `tests/test_agent_command_dialog_empty_prompt.py`,
   `tests/test_agent_command_open_debounce.py`,
   `tests/test_pick_command_screen.py`, and `tests/test_textual_markup_colours.py`
   (Rule C scans `tests/`).
4. No website doc changes: the docs describe only "New window" and choosing an
   existing window, never the blank entry.

## Step 9 (Post-Implementation)

Commit the code and tests with `bug: … (t2027)`, then archive through the
standard Step 9 flow on the current branch (`fast` profile, no worktree).

## Risk

### Code-health risk: low
- A session switch's transient `Changed(NULL)` (from `set_options`) now shows
  the name row for a moment instead of hiding both rows. The final state relies
  on the following `Changed(<value>)` arriving last, which it did before as
  well · severity: low · → mitigation: none needed — pinned by
  `test_session_switch_keeps_existing_window_default` in step 4.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** As planned. `.aitask-scripts/lib/agent_command_screen.py`
  gained the module-level `_is_existing_window(value)`. `_on_window_changed`
  now has two branches: an existing window on an existing session shows the
  split row, and everything else shows the window-name row. `_build_tmux_config`
  splits only under the same test; every other state launches a new window
  named by `#tmux_new_window_input`, falling back to the default name when the
  input is empty. The old hide-both-rows branch and the input-ignoring
  "Default to new window" branch are gone. In
  `tests/test_agent_command_dialog_narrow.py`: a t2027 docstring paragraph,
  an optional `default_tmux_window` on `_DialogHost`,
  `test_blank_window_choice_shows_window_name_row` (narrow 40x44 and wide
  120x40 × prior = new-window default / existing window "1"; the blank entry is
  chosen through the real overlay with `w`, `enter`, `home`, `enter`), and the
  characterization guard `test_session_switch_keeps_existing_window_default`.
- **Deviations from plan:** None.
- **Issues encountered:** None. Red proof, from a scratch runner that patched
  HEAD's methods into `AgentCommandScreen` without touching the tree:
  - both methods from HEAD → the blank test failed in all 4 subtests with
    `#tmux_new_window_row Region(x=0, y=0, width=0, height=0)`;
  - only HEAD's `_on_window_changed` → the same row failure;
  - only HEAD's `_build_tmux_config` → `'agent-pick-5_5' != 'my-win'` in all
    4 subtests;
  - unpatched → both tests pass.

  The session-switch guard passed in every mode, as intended. After the fix,
  `test_agent_command_dialog_narrow.py` (15 tests), the neighbouring dialog
  modules plus `test_textual_markup_colours.py` (123 tests in all), and 13
  further dialog-consuming modules (332 tests) all pass.
- **Key decisions:** One shared predicate drives both which row is visible and
  what launches, so the two cannot drift apart again. I rejected
  `allow_blank=False`: in Textual 8.2.7 it raises `EmptySelectError` for the
  new-session path's empty options and `set_options([])`, and
  `InvalidSelectValueError` for `clear()`. The blank Select still shows its
  dim "Select" prompt; the visible name row is what states the launch.
- **Upstream defects identified:** None
