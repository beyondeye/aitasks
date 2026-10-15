---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [frozen, tui, textual, clipboard]
gates: [risk_evaluated]
created_at: 2026-10-15 10:07
updated_at: 2026-10-15 10:07
---

Three usability defects in the `ait frozenagent` viewer, plus a requested change to its copy keys. Reported live on 2026-10-15 while reading a frozen Claude Code agent's stand-in pane in a downstream project (`thinking_backend`, window `agent-pick-153`). Textual 8.2.7, tmux 3.7c with `set-clipboard on`, theme `textual-dark`. The downstream `.aitask-scripts/frozenagent/` is byte-identical to this repo's.

## 1. Mouse selection is unreadable (selected text = background colour)

**Symptom.** Dragging with the mouse over the capture paints a blue bar, but the selected text inside it cannot be seen. The live pane's escapes show `38;2;9;68;114` on `48;2;9;68;114`: foreground and background are both `#094472`.

**Root cause.** `CaptureLog._selection_style()` (`.aitask-scripts/frozenagent/capture_log.py:96-106`) gets the selection style from `self.screen.get_component_rich_style("screen--selection")`. In Textual 8.2.7:
- `$screen-selection-foreground` defaults to `transparent` (`textual/design.py:526-527`);
- `$screen-selection-background` is `$primary` at 50% (`design.py:523-524`).

`get_component_rich_style` builds a Rich style through `DOMNode.rich_style`, which blends the transparent foreground over the background. The result is a style whose `color == bgcolor`. `_paint_span` (`capture_log.py:113-150`) applies that as an override (`style + selection`), so the cell's own captured colour is replaced by the background colour.

Measured headless (`App.run_test`, real theme): `color == bgcolor` in `textual-dark` (#094472), `textual-light` (#7092ac), `nord`, `gruvbox` and `tokyo-night`. Every theme is affected, in both ANSI and plain mode (`r`).

The keyboard range (shift+↑/↓) is unaffected: `_repaint_marks` paints it with `reverse`, so it stays readable.

**The pinned docstring is wrong.** `_selection_style` says this accessor is the safe one and that `Style.from_styles(get_component_styles(...))` is the one that gives fg == bg "(measured)". In a real render, the accessor it uses gives fg == bg itself. Textual's own Visual path (`textual/visual.py:220-223`) uses `Style.from_styles(...)`, which keeps `transparent` as "use the cell's own foreground".

**Test gap.** `CaptureLogSelectionTests.test_extraction_and_painting_match_stock_log` (`tests/test_frozenagent_app.py:205`) compares only the selected run's `bgcolor` with stock `Log` and with the unselected run. It never checks the foreground. Stock `Log` (`textual/widgets/_log.py:340-345`) stylizes with the same accessor, so parity with `Log` may hide the same defect. Verify that before keeping the comparison as the oracle.

**Fix direction (settle in the plan).** Keep the theme's selection background. When the theme's selection foreground is transparent, keep each cell's captured foreground (for example, apply only `bgcolor`, or build the style from `get_component_styles` the way `visual.py` does). If the theme sets an explicit selection foreground, honour it. Consider a contrast fallback (for example `reverse`) for a captured foreground that is close to the selection background. Correct the docstring.

## 2. `/` opens the search box but typing shows nothing

**Symptom.** Pressing `/` makes a search area appear, but nothing typed shows up in it ("I cannot type in it").

**Root cause.** `FrozenAgentApp.CSS` sets `#fa-search { height: 1; display: none; }` (`.aitask-scripts/frozenagent/frozenagent_app.py:184`). Textual's `Input` has a 2-row `tall` border and `padding: 0 2`. Measured headless at 100x30 after `/`: the region is 2 rows high (just the top `▔` and bottom `▁` border lines) and `content_region` is **0 rows** high.

The keys *are* received. After `/` and typing `step`, focus is on `#fa-search` and `box.value == 'step'`. But neither the placeholder nor the typed text is ever drawn, and Enter runs a search the user cannot see.

**Test gap.** `SearchTests` (`tests/test_frozenagent_app.py:334`) sets `app._search_term` directly and calls `action_search_next()`. No test presses `/`, types, or checks what is rendered.

**Fix direction.** Either `height: 3` (as `lib/shortcut_editor_modal.py` `#se_search` does) or a compact single-row input (`border: none; height: 1`). Pick one in the plan. Check that the header and log layout still fit when the box opens.

## 3. Copy keys: one action on `y` and `ctrl+c`, shown only when there is a selection

**Today:**
- `y` (`frozenagent_app.py:203`) runs `action_copy` (`:750`). It copies the keyboard range first, else the mouse selection, through `lib/tui_clipboard.copy_to_system_clipboard` (OSC 52 plus `tmux load-buffer -w`), and shows `Copied N line(s)`. It is always listed in the footer, even with nothing selected.
- `ctrl+c` is not bound by the viewer. It reaches Textual's built-in Screen binding `ctrl+c,super+c → screen.copy_text` (`textual/screen.py:272`, `:985-991`). That path:
  - copies only the **mouse** selection;
  - does so **silently** (no toast);
  - goes through bare `app.copy_to_clipboard`, bypassing the `tui_clipboard` seam. So from a pane in a background window it never reaches the system clipboard (the defect the seam exists for).
  
  With only a keyboard range it raises `SkipAction`, and the press falls through to the App's `help_quit` ("Press q to quit"). None of this is documented.
- Live evidence: the user's mouse selection did reach tmux as a single paste buffer (`buffer1060`, 462 bytes). That fits the ctrl+c path, since the seam path normally leaves a pair (OSC 52 plus `load-buffer`).

**Wanted (user request):**
1. `ctrl+c` runs the **same** copy action as `y`: the keyboard range first, else the mouse selection, always through the seam, always with the toast. The viewer's binding must take precedence over Textual's Screen-level `ctrl+c`.
2. Both keys work for **both** kinds of selection.
3. The copy keys appear in the footer **only while a selection exists** (a keyboard range from `_selection_bounds()`, or a non-empty mouse `text_selection`), and are hidden otherwise. The footer must refresh (`refresh_bindings()`) on every selection change:
   - the mouse path, `CaptureLog.selection_updated`;
   - the keyboard path, `_extend_selection`, `_clear_selection`, and any other path that sets or clears `_sel_start`/`_sel_end`.
4. No dead keys. With nothing selected:
   - `ctrl+c` still gives Textual's "Press q to quit" hint (the reason that binding exists);
   - `y` still gives `Nothing selected`, not silence.
   
   Hiding a binding via `check_action → False` also deactivates it, so the plan must choose a mechanism that hides the footer entry without swallowing the press. The existing `check_action` docstring (`:808`) already states the rule: silently swallowing a press is worse than refusing it.
5. The new binding must be registered and rebindable through `ShortcutsMixin` (`?` editor, Settings → Shortcuts) like the viewer's other keys.

**Risk to handle.** A priority app-level `ctrl+c` would also take the key from the search `Input`, whose own `ctrl+c,super+c → copy` binding (`textual/widgets/_input.py:134`) copies text selected inside the box. Decide what `ctrl+c` does while the search box has focus, and keep the input's own copy working. Consider `super+c` too, since Textual binds it alongside `ctrl+c`.

## 4. Docs

- `website/content/docs/tuis/frozenagent/reference.md`: add `ctrl+c` to the keybinding table. Update the footer sentence (lines 33-34) to say the copy keys appear only while a selection exists.
- `website/content/docs/tuis/frozenagent/how-to.md`: in the copy section (lines 26-39), mouse drag followed by `y`/`ctrl+c`.
- `website/content/docs/tuis/frozenagent/_index.md` (line 106) and `website/content/docs/workflows/freeze-and-restore-agents.md` (lines 52-54, 76): mention `ctrl+c` next to `y`.

## Acceptance criteria

- A mouse selection over ANSI-coloured text and over plain text is readable in the default theme and in at least one light theme. The selected cells' foreground differs from their background, and captured ANSI foregrounds are kept unless the theme sets an explicit selection foreground.
- Pressing `/` shows a search box with a visible text row. The placeholder and typed characters are rendered, and Enter finds the typed term.
- `y` and `ctrl+c` both copy a keyboard range and a mouse selection, through `copy_to_system_clipboard`, with the `Copied N line(s)` toast.
- The footer lists the copy keys only while something is selected, and updates as soon as a mouse or keyboard selection starts or is cleared (Escape, a click, a new drag).
- With nothing selected, `ctrl+c` shows Textual's quit hint and `y` shows `Nothing selected`.
- `ctrl+c` inside the focused search box does not copy the log selection instead of what the user expects there (behaviour decided in the plan, and tested).
- The shortcut editor lists the new binding under the `frozenagent` scope.

## Tests to add or fix (`tests/test_frozenagent_app.py`)

- Selection paint: assert the **foreground** of the selected run, not just its `bgcolor`, for an unstyled cell and for an ANSI-coloured one, under the default theme. Do not use stock `Log` parity as the oracle unless it is shown to be correct.
- Search: a pilot test that presses `/` and types. It asserts `content_region.height >= 1` and that the typed text appears in the rendered screen (for example `export_screenshot()`), not only in `Input.value`.
- Copy: `ctrl+c` with a keyboard range, and `ctrl+c` with a mouse selection, both reach the patched `copy_to_system_clipboard`. Footer/active-binding visibility toggles on selection start and clear. The no-selection fallbacks for both keys.

## Related

- **t1842** (manual-verification carry-over): its deferred `[t1705_6]` item checks that `/` finds text, that shift+down selects and that `y` copies in this viewer. Its `/` step cannot pass until defect 2 is fixed. It is linked here, not folded.
- t1705_6 introduced `CaptureLog` and the viewer.

## Out of scope (observed, not investigated)

Two defunct `[tmux: client]` zombie children sat under the live viewer process (`frozenagent_app.py --record f5d2ad20`). Some fire-and-forget tmux spawn is not being reaped. If it matters, file it as a separate task.
