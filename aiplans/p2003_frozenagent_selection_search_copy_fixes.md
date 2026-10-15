---
Task: t2003_frozenagent_selection_search_copy_fixes.md
Base branch: main
Output branch: main
---

# t2003 — frozenagent: readable selection, visible search box, unified copy keys

## Context

The `ait frozenagent` viewer has three usability defects, reported live, plus a
requested change to the copy keys:

1. A mouse selection paints the selected text in the background colour.
2. `/` opens a search box whose text row is 0 rows high, so typing shows nothing.
3. `ctrl+c` reaches Textual's Screen `copy_text`. That path copies silently,
   copies only the mouse selection, and bypasses the clipboard seam. The user
   wants `ctrl+c` and `y` to run one copy, and wants both keys in the footer only
   while a selection exists.

The docs must follow. Every root cause below was re-measured headless on Textual
8.2.7 during planning. The probes ran from the scratchpad and wrote nothing to
the repo.

### Measured facts the design rests on

- **Selection colour.** `screen.get_component_rich_style("screen--selection")`
  returns `color == bgcolor` in textual-dark (#094472), textual-light, nord,
  gruvbox, tokyo-night, catppuccin-latte and solarized-light.
  `screen.get_component_styles(...)` keeps the foreground transparent
  (`Color(0,0,0,a=0)`).
  - **Stock `Log` has the same defect.** Its selected run renders `#094472` on
    `#094472`, so Log parity hid the bug and cannot be the colour oracle.
  - A theme can set an explicit selection foreground through `Theme(variables=…)`.
    `#204060` on `#214161` is a legitimate, if poor, choice, and the two colours
    are 1.7 RGB units apart.
- **Search box.** With `#fa-search { height: 1 }`, the box region is 2 rows and
  `content_region.height == 0`. `height: 1; border: none` gives a 1-row content
  region, and the typed text appears in the screenshot.
- **Key dispatch.**
  - A `ctrl+c` binding in `FrozenAgentApp.BINDINGS` **replaces** App's
    `ctrl+c → help_quit`, because `DOMNode._merge_bindings` assigns
    `keys[key] = …`.
  - The Screen's `ctrl+c,super+c → screen.copy_text` precedes the App in the
    non-priority chain. Our binding therefore must be `priority=True`, both to
    dispatch and to appear in the footer.
  - Priority bindings also fire while a modal is open.
- **Rebinding (reviewer concern 1, reproduced).** After `ShortcutsMixin` moves
  the copy binding to `ctrl+y`, the live `ctrl+c` bucket is empty, because
  `help_quit` was already clobbered at merge time.
  - `ctrl+c` with nothing selected then does **nothing**.
  - `ctrl+c` with a mouse selection does a **bare** `app.copy_to_clipboard`
    through `Screen.copy_text`.
  - `super+c` does the same bare copy even with default bindings.
  - A viewer default screen whose `action_copy_text` runs the viewer's copy fixes
    all three cases. It was probed with a seam copy or the quit hint on
    `ctrl+c`, `ctrl+y` and `super+c`, both with and without a selection.
- **Footer.** `check_action → False` hides a binding but also stops it
  dispatching, so `y` would go silent. Swapping the live `Binding` for
  `dataclasses.replace(b, show=…)` and calling `refresh_bindings()` hides or
  shows the Footer entry while the key still dispatches (probed).
- **Shared lists.** `BindingsMap.copy()` is shallow. `self._bindings.key_to_bindings[k]`
  is the class-level `_merged_bindings` list, so an in-place edit would leak into
  every later app instance. Assign new lists instead.
- **Escape.** Textual's `Screen._key_escape` already clears the mouse selection,
  which calls `CaptureLog.selection_updated(None)`.

## Decisions (settled here)

- **Selection style.**
  - The selection takes the theme's blended background.
  - When the theme's selection foreground is transparent (the default), each
    cell keeps its captured foreground.
  - When the theme sets an explicit foreground, it is honoured **as is**, even if
    it is close to the background.
  - The contrast fallback applies **only to captured foregrounds**, meaning only
    in the transparent branch. A captured colour within a small RGB distance of
    the selection background is swapped for that background's contrast text
    colour.
- **Search box.** Compact single row: `height: 1; border: none`. A stand-in pane
  is often a small split, and this costs 1 row where `height: 3` costs 3.
- **One copy routine, `_copy_or_quit_hint()`, reached two ways:**
  1. Through the registered, rebindable, footer-visible
     `Binding("ctrl+c", "copy_or_quit_hint", "Copy", priority=True)`.
  2. Through a viewer default screen, `_ViewerScreen(Screen)`, whose
     `action_copy_text` calls the same routine. Textual's own
     `ctrl+c,super+c → screen.copy_text` binding therefore never does a bare
     copy on the viewer screen.

  The routine works like this:
  - If the search box has focus, it never touches the log. If the box has
    selected text, it raises `SkipAction` so `Input`'s own copy runs. Otherwise
    it shows the quit hint.
  - Otherwise it copies the keyboard range, or else the mouse selection, through
    `copy_to_system_clipboard` and shows the `Copied N line(s)` toast.
  - If there is nothing to copy, it calls Textual's `action_help_quit()`.

  The priority action alone also checks `isinstance(self.screen, _ViewerScreen)`.
  If a modal is active, it raises `SkipAction` and leaves the key to the modal.
- **What the old key does after a rebind.** Rebinding `copy_or_quit_hint` (for
  example to `ctrl+y`) moves the *registered* shortcut: the footer-visible,
  priority key. `ctrl+c` then falls back to Textual's own screen-level copy key,
  which this viewer routes through the same routine: seam copy with the toast,
  the quit hint when nothing is selected, and never the log while the search box
  has focus. A rebind therefore cannot revive a bare copy or a dead key on
  `ctrl+c`. `super+c` gets the same routing wherever a terminal delivers it.
- **Footer.** The `y` and `ctrl+c` entries are both shown only while a selection
  exists. Textual places `^c Copy` at the footer's left edge, because the key
  keeps the Screen's slot, and `y Copy` at its declared position. Changing that
  would need a custom footer.

## Implementation

### 1. `.aitask-scripts/frozenagent/capture_log.py`

- Imports: `math`, `textual.color.Color`, `textual.message.Message`.
- Add a module constant `_MIN_SELECTION_FG_DISTANCE = 48.0`. Comment it as the
  RGB distance below which a **captured** foreground is unreadable on the
  selection background.
- Add a helper `_too_close(fg, bg) -> bool`. It returns False if either colour is
  None, and otherwise
  `math.dist(fg.get_truecolor(), bg.get_truecolor()) < _MIN_SELECTION_FG_DISTANCE`.
- Add a nested `class SelectionChanged(Message)`, documented as "posted whenever
  the native selection is set, moved or cleared". `selection_updated` posts it
  after the cache clear and refresh. The app handles it in
  `on_capture_log_selection_changed`.
- Rewrite `_selection_style()`. In the docstring, replace the wrong
  "(measured)" claim with the measurement above.
  ```python
  try:
      styles = self.screen.get_component_styles("screen--selection")
      blended = self.screen.get_component_rich_style("screen--selection")
  except Exception:
      return RichStyle(reverse=True)
  if blended.bgcolor is None:
      return RichStyle(reverse=True)
  if styles.color.a == 0:          # theme default: transparent = keep the cell's colour
      return RichStyle(bgcolor=blended.bgcolor)
  return blended                   # the theme chose a foreground: honour it verbatim
  ```
- In `_paint_span`, build the contrast style **only when the selection style
  carries no foreground and has a background**, which is exactly the
  transparent branch:
  ```python
  contrast = None
  if sel.color is None and sel.bgcolor is not None:
      contrast = RichStyle(color=Color.from_rich_color(sel.bgcolor)
                           .get_contrast_text(1.0).rich_color)
  ```
  For each segment, `painted = sel if style is None else style + sel`. Then
  `if contrast is not None and _too_close(painted.color, painted.bgcolor): painted += contrast`.
  An explicit theme foreground sets `sel.color`, so it is never corrected, and
  the `reverse` fallback has no background, so it is skipped as well.
  Update the docstring: the override carries only the background in the
  transparent branch, captured colours are kept, and the fallback is limited
  to captured colours.

### 2. `.aitask-scripts/frozenagent/frozenagent_app.py`

- Imports: `dataclasses`, `from textual.actions import SkipAction`,
  `from textual.screen import Screen` (alongside the existing `ModalScreen`).
- Add a module constant `_COPY_ACTIONS = frozenset({"copy", "copy_or_quit_hint"})`.
- New `class _ViewerScreen(Screen)`, with a docstring explaining that Textual
  binds `ctrl+c,super+c → screen.copy_text` on every screen, and that its stock
  action does a silent, mouse-only, bare `copy_to_clipboard`.
  `action_copy_text(self)` calls `self.app._copy_or_quit_hint()`. Follow the
  `codebrowser_app.py:667` / `trails_app.py:316` precedent:
  `FrozenAgentApp.get_default_screen()` returns `_ViewerScreen()`.
- CSS: `#fa-search { height: 1; border: none; display: none; }`. Comment that
  the stock `Input`'s 2-row `tall` border left a 0-row text area.
- BINDINGS: after `y`, add
  `Binding("ctrl+c", "copy_or_quit_hint", "Copy", priority=True)`. The comment
  should say three things:
  - priority puts it ahead of the Screen binding, and lets it take that key's
    footer slot;
  - declaring it removes App's `help_quit`, so the routine calls `help_quit`
    itself;
  - `_ViewerScreen` covers this key after a rebind.
- New helpers in the keyboard-selection section:
  - `_has_selection() -> bool`. False in list mode or when the capture is
    missing. Otherwise True if there is a keyboard range from
    `_selection_bounds()` or `log.text_selection is not None`. This check is
    cheap: it never extracts the text, because `get_selection` joins up to
    50000 lines and this runs on every drag event.
  - `_sync_copy_keys()`. For each `key, bucket` in
    `self._bindings.key_to_bindings`, if any `_COPY_ACTIONS` binding has
    `show != wanted`, assign a **new** list built with
    `dataclasses.replace(b, show=wanted)`. Call `refresh_bindings()` only if
    something changed. The docstring explains why `check_action` is not used
    (it disables dispatch), why a new list is needed (the lists are shared at
    class level), and why bindings are matched by action (so a rebind is
    followed).
  - `_selected_text() -> str`. The keyboard range, else the mouse extraction,
    else `""`. This logic moves out of today's `action_copy`.
  - `_copy_selected() -> bool`. Copies through `copy_to_system_clipboard` and
    shows `Copied N line(s)`. Returns False if there is no text.
  - `_copy_or_quit_hint()`. The shared routine described in Decisions: the
    search-focus rule first, then `_copy_selected()`, else
    `self.action_help_quit()`.
- `action_copy` (`y`): `if not self._copy_selected(): notify("Nothing selected", severity="warning")`.
  In list mode this now says "Nothing selected" too, instead of doing nothing.
- `action_copy_or_quit_hint`: `if not isinstance(self.screen, _ViewerScreen): raise SkipAction()`,
  then `self._copy_or_quit_hint()`. This keeps the guard scoped to the active
  screen, per `tui_conventions.md` "Priority bindings".
- Call `_sync_copy_keys()` from:
  - `on_mount`, before the list-mode branch, so both modes start hidden;
  - the end of `_clear_selection` and `_extend_selection`;
  - `_open_selected`, after the mode switch;
  - a new `on_capture_log_selection_changed` handler, which covers drag, click
    and Escape.

### 3. Docs (current-state prose only)

- `website/content/docs/tuis/frozenagent/reference.md`:
  - Add a `ctrl+c` row after `y`: "Copy the selection — same as `y`. With
    nothing selected it shows Textual's quit hint, and in the search box it
    copies the text selected there. If you rebind it, `ctrl+c` keeps copying
    as Textual's own copy key."
  - Rewrite the footer sentence: `Copy` (`y` and `ctrl+c`) is listed only while
    a selection exists.
  - Update the `Escape` row only if the new test confirms that Escape also
    clears a mouse selection while the search box is open.
- `website/content/docs/tuis/frozenagent/how-to.md`, copy section: make step 3
  "Press **y** (or **ctrl+c**)". Change the mouse sentence to "drag with the
  mouse instead of step 2, then press **y** or **ctrl+c**", and add that `Copy`
  appears in the footer once something is selected.
- `website/content/docs/tuis/frozenagent/_index.md` (~line 106): "**y** or
  **ctrl+c** copies…".
- `website/content/docs/workflows/freeze-and-restore-agents.md` (lines 52-54
  and 76): "copy with **y** (or **ctrl+c**)".

### 4. Tests: `tests/test_frozenagent_app.py`

New tests use `patch.object(self.app_mod, "copy_to_system_clipboard", …)` and
`app.notify = spy`, which are the file's idioms. A spy on
`app.copy_to_clipboard` detects any bare copy. With the seam patched, that spy
must see **zero** calls unless `Input`'s own copy is the expected path.

- **Selection paint.** In `test_extraction_and_painting_match_stock_log`, keep
  the extraction and cut-position parity with `Log`, drop the bgcolor parity,
  and say in the docstring that stock `Log` shares the defect. Add
  `SelectionPaintTests`:
  - Under `textual-dark` and `textual-light`, render
    `plain \x1b[31mred\x1b[0m` with the whole line selected. Every selected
    segment has `color != bgcolor`, and `bgcolor` equals the theme's blended
    selection background. The red cell keeps its captured red, and the
    unstyled cell keeps the widget foreground.
  - A captured truecolor foreground equal to the selection background becomes
    the contrast colour, so `color != bgcolor`.
  - **Close-colour explicit theme (reviewer concern 2).** Register
    `Theme(variables={"screen-selection-foreground": "#204060", "screen-selection-background": "#214161"})`.
    The selected cells are painted exactly `#204060` on `#214161`, and the
    contrast fallback does **not** replace the theme's foreground. This applies
    to both an unstyled cell and a red-captured cell.
- **Search.**
  - Press `/`.
  - Assert `content_region.height >= 1` and that the placeholder appears in
    `export_screenshot()`, with SVG tags stripped and HTML unescaped.
  - Type `step` and check that it is rendered. The log keeps at least 1 row and
    does not overlap the box.
  - Press Enter and check that `_match_line == 2`.
- **Copy.**
  - `ctrl+c` with a keyboard range, and `ctrl+c` with a mouse selection, each
    reach the patched seam with the toast; the bare-copy spy stays silent.
  - With nothing selected, `y` gives "Nothing selected" and `ctrl+c` gives
    Textual's "…to quit the app" hint. The seam is not called.
  - With the search box focused and a mouse selection on the log, `ctrl+c`
    gives the quit hint and never calls the seam. With text selected in the
    box, `Input`'s own copy receives that text.
  - With the Markdown modal open, `ctrl+c` does not copy the log.
  - `super+c` with a mouse selection goes through the seam with the toast, and
    with nothing selected gives the quit hint.
- **Rebind matrix (reviewer concern 1).** Patch
  `keybinding_registry.load_user_overrides` to map
  `{"frozenagent": {"copy_or_quit_hint": "ctrl+y"}}`. For each of the **new**
  key (`ctrl+y`) and the **old** key (`ctrl+c`), check three cases:
  - mouse selection: seam copy and toast, no bare copy;
  - keyboard range: seam copy and toast;
  - nothing selected: the quit hint is shown, not silence.

  The footer shows the `ctrl+y` entry while something is selected.
  **Negative control:** with `get_default_screen` patched back to a stock
  `Screen`, the same old-key press with a mouse selection reaches the bare
  `copy_to_clipboard`. This proves the matrix can fail.
- **Footer.**
  - A helper reads the `FooterKey.action` set and the `active_bindings` show
    flags. Every transition first asserts the state before it.
  - Neither copy action is listed at mount. shift+up shows them and Escape hides
    them.
  - Assigning `app.screen.selections = {log: …}` shows them, `pilot.click("#fa-log")`
    hides them, a new assignment shows them, and Escape hides them.
  - A second app instance starts hidden, which proves the class-level lists were
    not mutated.
- **Shortcuts.** `keybinding_registry.iter_scope_bindings("frozenagent")`
  includes `copy_or_quit_hint` / `ctrl+c` / `Copy`.
- **Internals pin.** An upgrade guard in the same style as `CaptureLog`'s pins
  these internals:
  - `App.action_help_quit`;
  - `Screen.BINDINGS`, which maps `ctrl+c` and `super+c` to `screen.copy_text`;
  - `FrozenAgentApp._merged_bindings`, which holds only our action on `ctrl+c`
    (the clobber);
  - `type(app.screen) is _ViewerScreen`;
  - `Input.selected_text`.

## Verification

- Run `~/.aitask/venv/bin/python -m pytest tests/test_frozenagent_app.py -q`.
  If pytest is absent, use `-m unittest`.
- Run `bash tests/test_tui_clipboard_seam.sh`,
  `~/.aitask/venv/bin/python -m pytest tests/test_shortcut_scopes.py -q` and
  `bash tests/test_no_raw_tmux.sh`.
- Run `set -o pipefail; bash tests/run_all_python_tests.sh` and read the final
  `PYTHON SUITE:` line.
- Run `cd website && python3 check_links.py --build`.
- Spot-check the search row and a selection in a headless screenshot.
- The live tmux check (drag is readable, `/` typing is visible, `ctrl+c` works
  from a background window) belongs to the Step 8c manual-verification offer
  and to t1842's carry-over items.

## Step 9 (Post-Implementation)

This task runs in current-branch mode. Commit the code; commit the plan through
`./ait git`. Archive through the standard Step 9 flow.

## Out of scope — follow-ups to offer, not fix here

- `.aitask-scripts/logview/logview_app.py:48` uses the same
  `#search-box { height: 1 }` stock-`Input` CSS, so its search row has the same
  zero height.
- `ShortcutsMixin._relink_live_bindings` calls
  `mapping.setdefault(new_key, []).append(…)`. When a rebind targets a key that
  is already bound, this appends to the **class-level** shared list, because
  `BindingsMap.copy()` is shallow.
- The task notes two defunct `[tmux: client]` zombies.

## Risk

### Code-health risk: medium
- The footer toggle swaps `Binding`s in Textual's private
  `App._bindings.key_to_bindings` (`ShortcutsMixin` already does this). A Textual
  upgrade could silently break the toggle, and an in-place edit would leak to
  other instances. · severity: medium · → mitigation: none (handled in-plan:
  new-list assignment, internals pin, second-instance test)
- An App-level `priority=True` `ctrl+c` preempts every screen's `ctrl+c`,
  including modals and the `?` editor's Input. · severity: medium ·
  → mitigation: none (handled in-plan: `_ViewerScreen` isinstance guard raising
  `SkipAction`, plus a modal test)
- A custom default screen changes `app.screen`'s type for the whole viewer.
  Codebrowser and trails already follow this pattern, and the subclass adds no
  bindings or CSS. · severity: low · → mitigation: none (pinned by an
  internals test)
- The merge clobber removes Textual's `help_quit`, and a rebind could revive the
  bare-copy and dead-key paths. · severity: low (residual) · → mitigation: none
  (handled in-plan: the routine calls `help_quit` explicitly, and `_ViewerScreen`
  routes `copy_text`; the rebind matrix with its negative control covers it)

### Goal-achievement risk: low
- The headless assertions check style values, not pixels in a real tmux pane.
  The original defect reproduced headless with the same colours.
  · severity: low · → mitigation: none (the Step 8c manual-verification offer
  and t1842 cover the live check)
- The contrast-fallback threshold is a heuristic. It applies only to captured
  colours, so it can leave a near-but-not-equal captured foreground hard to
  read. · severity: low · → mitigation: none
