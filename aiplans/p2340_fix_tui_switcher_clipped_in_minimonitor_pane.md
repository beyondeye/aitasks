---
Task: t2340_fix_tui_switcher_clipped_in_minimonitor_pane.md
Base branch: main
Output branch: main
---

# t2340 — TUI switcher clipped in the 40-column minimonitor pane

## Context

`TuiSwitcherOverlay`'s dialog (`.aitask-scripts/lib/tui_switcher.py:555`,
`#switcher_dialog { width: 44; … }`) is wider than minimonitor's usual
40-column pane. A spike at 40×40 (`run_test`, real overlay) confirmed it:
`dialog.region = Region(x=0, y=5, width=44, height=30)` on a 40-wide screen,
so the right border is missing on every row and the two widest hint rows end
`(S)etting` / `(G)i`.

The hint (`_render_hint`, :919) is one `Label` that word-wraps to the dialog's
content width, so `max-width: 100%` on the dialog re-flows it: at 40 and 34
columns the border is complete and every hint word is on screen.

### Why a bare cap is not enough (four review rounds, each verified headless)

Capping narrows the content width from 38 to 34, so the hint grows by a row and
the multi-session close line `Enter switch  ←/→ session  J/Esc close` wraps.
The docked hint then covers more of the list. `#switcher_list { min-height: 3 }`
makes the list taller than the space left clear of the footer, so ListView
treats covered rows as visible:

1. 40×18, two sessions, realistic desync line: with the cap alone, the selected
   `Task Board` sits under the footer (it was drawn before).
2. 40×17: the initial selection is drawn, but after Down `Trails` is under the
   footer.
3. Resize 40×18 → 34×18 with no key press: the list shrinks without being
   repopulated, so the selection ends up under the footer.
4. Scope: the cap would apply to every host (and Monitor at 34×20 with the
   companion hint lost `Task Board`) while the compaction applied only to
   minimonitor.

### Design: one condition — "the dialog is capped" — drives everything

The compaction is keyed on the **effective width**, not on the host's `narrow`
flag. When the screen is narrower than the dialog's 44 columns, the cap engages,
and the same condition puts a `-compact` class on `#switcher_dialog`. The class
is re-evaluated on every resize and drives:

- `#switcher_dialog.-compact { padding: 0 2; }`: drops the dialog's vertical
  padding (+2 rows);
- `#switcher_dialog.-compact #switcher_title { padding: 0; }` and
  `… #switcher_hint { padding: 0; }`: drops the gaps between rows;
- `#switcher_dialog.-compact #switcher_list { min-height: 1; }`: the list
  region then matches the space actually clear of the footer, so ListView's
  scroll-to-highlight keeps Down/Up selections drawn;
- a post-layout reveal (`scroll_to_widget(highlighted_child, animate=False)`
  via `call_after_refresh`), scheduled after `_populate_list_for` sets the
  index and on every resize. The index is set before the list has its final
  size, and a resize changes that size without repopulating.

The class sits on the **dialog container**: Textual scopes a widget's
`DEFAULT_CSS` under its own type, so a class on the `TuiSwitcherOverlay` itself
is never matched (proved in the spike). The `narrow` flag keeps its current,
sole job (the AgentCommandScreen layout).

**Evidence (headless spikes, scratchpad).** The candidate was compared with
today's code over 288 cells: hosts minimonitor / monitor / board × companion
hint off/on × 1/2 sessions × widths 30/34/40/43 × heights 14/16/17/18/20/24. In
each cell the selection was checked as drawn above the footer at the initial
state and after each of 3 Down presses. **0 cells got worse.** In many cells
the result improved (e.g. two sessions 40×17: today `n n n n` → `Y Y Y Y`;
34×18: `Y n n n` → `Y Y Y Y`; Monitor+companion 34×20: hidden → drawn). At
widths ≥ 44 (44/60/120 × 18/20/40, every host, companion, session combination:
48 renders) the output is **byte-identical** to today's. Resizing
40×18 → 50×18 returns exactly today's 50×18 render. Resizing 50×18 → 34×18 keeps
the selection drawn through Down, and Up-wrap was checked at 40×17. Where no
list row clears the footer even when compacted (very short panes), the
selection is hidden both before and after; that is the pre-existing small-height
limit t789 addressed, and it is out of scope.

Long names: list rows are wrapping `Static`s, so a long agent-window name wraps
inside the border. Textual breaks a single long token mid-word (spiked:
`agent-t2340_fix_tui_switcher_clipp` / `ed_in_minimonitor_pane`), so the test
reconstructs the name from the item's rows.

Coordination: t2338 (sitrep row in the switcher, in flight in another session)
also edits `tui_switcher.py`, but only the list/bindings. `tui_switcher.py`
currently has no uncommitted changes. t2338's extra list row lands in the
`1fr` list, which this change makes safer in short panes.

## Implementation steps

1. **Regression test first (pre-fix control).** Create
   `tests/test_tui_switcher_narrow_fit.py` (unittest; `asyncio.run` +
   `App.run_test`; host-App / patch pattern from
   `tests/test_tui_group_nav.py::SwitcherPilotTests`). Patch
   `ts.discover_aitasks_sessions` → N `AitasksSession`s, `ts._session_windows`
   → a windows list, and `TuiSwitcherOverlay._compute_desync_summary` → the
   realistic `"main: 1↑/0↓ · aitask-data: 0↑/3↓"`. For the companion case,
   patch `TuiSwitcherOverlay._resolve_companion_target` → a non-None sentinel.
   Helpers:
   - `_mount(pilot-context, size, *, host, sessions, windows, companion)`:
     `narrow = host == "minimonitor"`.
   - `_rows(app)`: `app.screen._compositor.render_strips(app.screen.size)` text.
   - `_assert_selection_drawn(app, ov)`: the highlighted child's
     `tui_label` / `window_name` appears in a rendered row above
     `hint.region.y`, and `highlighted_child.region.y < hint.region.y`.
   - `_assert_hint_words(app)`: each `_HINT_ITEMS` segment's plain text
     (`Content.from_markup(_hint_segment(...)).plain`) is split on whitespace,
     and each token must appear as a whole word (`(?<!\S)tok(?!\S)`), so
     `(S)ettings` is required and `(S)etting` fails. The same check covers
     `switch` / `close` (and `session` in multi mode).
   Tests:
   - `test_dialog_fits_narrow_screen`: minimonitor at 40×40 and 34×40
     (subTest); `dialog.region` lies inside the screen.
   - `test_right_border_drawn_on_every_dialog_row`: at 40×40, the cell at
     `x + width - 1` is non-blank on every dialog row.
   - `test_every_hint_word_is_on_screen`: at 40×40 and 34×40, with 1 and 2
     sessions.
   - `test_long_agent_window_name_stays_inside`: at 40×40, one agent window
     `agent-t2340_fix_tui_switcher_clipped_in_minimonitor_pane`. Select it,
     `scroll_to_widget(item)`, pause. Rebuild the visible text from the rows
     inside `item.region` (slice `row[x : x + width]`, strip, concatenate with no
     separator); the name must be a substring. The border check must also hold
     on those rows.
   - `test_short_pane_keeps_selection_drawn_while_navigating`: subTests
     minimonitor 40×18 / 40×17 / 34×18 with two sessions, plus 40×14 with one.
     `_assert_selection_drawn` holds initially, after each of 3 `down` presses,
     and after `up` presses back past the first item (wrap). The hint-word check
     also passes at 40×18.
   - `test_selection_stays_drawn_after_resize`: open at 40×18 with two
     sessions; `pilot.resize_terminal(34, 18)` plus two pauses; drawn with no
     key press, and still drawn after 2 `down` presses.
   - `test_narrow_monitor_host_gets_the_same_compaction` (concern 4): host
     `monitor` (`narrow=False`), companion hint on, two sessions, 34×20.
     Dialog fits, the dialog has the `-compact` class, the selection is drawn
     initially and after 2 `down` presses, and every hint word is on screen
     (including `minimonitor`).
   - `test_wide_layout_unchanged`: subTests host minimonitor and board at
     120×40 and 44×18. `dialog.region.width == 44`, no `-compact` class, and
     `#switcher_title` / `#switcher_hint` / `#switcher_dialog` keep their
     paddings (`styles.padding` (0,0,1,0) / (1,0,0,0) / (1,2,1,2)).
   - `test_compaction_reverts_when_widened`: open at 40×18, then resize to
     50×18: no `-compact` class, `dialog.region.width == 44`, title padding
     (0,0,1,0).
   Run it **before** the fix: the fit, border, hint, long-name, short-pane,
   resize and Monitor tests must FAIL, and the wide-layout and revert tests
   must PASS (nothing is compacted today). That is the pre-fix control; record
   the output in the Final Implementation Notes.

2. **The fix**, in `.aitask-scripts/lib/tui_switcher.py`:
   - Module constants beside the overlay: `_DIALOG_WIDTH = 44` (the CSS width,
     pinned by a test) and `_COMPACT_CLASS = "-compact"`.
   - `DEFAULT_CSS`: `#switcher_dialog` gains `max-width: 100%;` under
     `width: 44;`. After `#switcher_hint`, add:
     ```css
     #switcher_dialog.-compact { padding: 0 2; }
     #switcher_dialog.-compact #switcher_title { padding: 0; }
     #switcher_dialog.-compact #switcher_hint { padding: 0; }
     #switcher_dialog.-compact #switcher_list { min-height: 1; }
     ```
     Add a CSS comment: the dialog is capped to a pane narrower than its width
     (minimonitor's 40-column split, or any host in a narrow pane). Its hint
     re-flows taller, so the paddings give rows back, and the one-row list
     minimum keeps the list region equal to the space clear of the docked
     footer (t2340).
   - `_apply_compact(self, width: int) -> None`: `dialog = self.query("#switcher_dialog")`;
     return when absent; `dialog.first().set_class(width < _DIALOG_WIDTH, _COMPACT_CLASS)`;
     then `self._schedule_reveal()`.
   - `_schedule_reveal(self)`: `if self.is_mounted: self.call_after_refresh(self._reveal_selection)`.
   - `_reveal_selection(self)`: query `#switcher_list`; return when absent, when
     `highlighted_child is None`, or when the dialog lacks `_COMPACT_CLASS`
     (wide layouts keep today's behaviour exactly); otherwise
     `list_view.scroll_to_widget(list_view.highlighted_child, animate=False)`.
   - `on_mount`: first line `self._apply_compact(self.app.size.width)`, so the
     class is in place before `_populate_list_for` runs.
   - New `on_resize(self, event)` (none exists today): `self._apply_compact(event.size.width)`.
   - `_populate_list_for`, after `list_view.index = first_selectable_idx`:
     `self._schedule_reveal()`. The `is_mounted` guard keeps the existing
     unmounted unit tests (`test_tui_switcher_brainstorm_session.sh`,
     `test_tui_switcher_companion_spawn.py`, which drive `_populate_list_for`
     on a `query_one` stub) unaffected.
   - The `self._narrow` comment in `__init__` stays accurate (it still governs
     only AgentCommandScreen). Add one clause: "the dialog's own compaction is
     width-driven (`_apply_compact`)".

3. **Pin the CSS contract.** In `tests/test_tui_switcher_footer_fit.sh`, add a
   `DIALOG_MAX_WIDTH_100` probe (`"max-width: 100%" in dialog_block`) and a
   `DIALOG_WIDTH_CONST` probe
   (`f"width: {ts._DIALOG_WIDTH};" in dialog_block`), each with an `assert_eq`,
   next to the existing max-height probe.

4. Re-run the new test; everything should PASS.

## Verification

- `tests/test_tui_switcher_narrow_fit.py` with the venv python: the pre-fix
  failures described in step 1, then all pass post-fix.
- `bash tests/test_tui_switcher_footer_fit.sh`
- Neighbouring switcher suites, unchanged:
  `tests/test_tui_switcher_hint_text.py`, `tests/test_tui_group_nav.py`,
  `tests/test_tui_switcher_companion_spawn.py`,
  `tests/test_tui_switcher_agent_launch.py`, `tests/test_markup_colour_contract.py`,
  `tests/test_tui_switcher_open_key_collision.py`,
  `tests/test_tui_switcher_default_session_notify.py`,
  `tests/test_tui_switcher_git_shortcut_root.py`, run directly with the venv
  python (`-m pytest` when available). Shell suites:
  `tests/test_tui_switcher_brainstorm_session.sh` and
  `tests/test_tui_switcher_multi_session.sh`.
- The scratchpad spikes (288-cell sweep, wide byte-identity, resize) were run
  with the planned CSS through a subclass. Re-run the sweep once against the
  real implementation and record the counts.

## After the fix (not in this commit)

The docs image `website/static/imgs/aitasks_tui_switcher_from_minimonitor.svg`
still shows the clipped dialog. Per the task, refresh it with
`/aitask-docs-screenshots tui_switcher_from_minimonitor`. That skill owns the
preview → user-approved apply, so offer it at the end instead of folding it into
this code commit. t2338 changes the same scene, so if t2338 lands first, one
refresh covers both.

## Step 9

Post-implementation: review, commit (`bug: … (t2340)`), archive via the
task-workflow Step 9.

## Risk

### Code-health risk: low
None identified. The change is contained to one modal: a CSS cap, four rules
under one width-driven class, and three small methods plus `on_resize`. At
widths ≥ 44 nothing changes: the class is absent and the reveal no-ops. The
spike shows byte-identical renders at ≥ 44 for every host. Existing layout
rules stay pinned by `test_tui_switcher_footer_fit.sh`, and the wide layout and
the revert-on-widen behaviour get new tests.

### Goal-achievement risk: low
None identified. The requirement's two clauses (text and border inside a narrow
pane) are pinned for minimonitor and for a narrow Monitor host. The
selection-visibility regressions the review rounds found (short panes,
navigation, resize, host scope) each have a dedicated test, and a 288-cell
sweep found no layout worse than today's.
