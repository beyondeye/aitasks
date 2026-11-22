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

## Implementation progress

- [x] Step 1: `tests/test_tui_switcher_narrow_fit.py` written (9 tests); pre-fix control run (below).
- [x] Step 2: fix in `.aitask-scripts/lib/tui_switcher.py` (`_DIALOG_WIDTH`, `_COMPACT_CLASS`, `max-width: 100%`, four `-compact` rules, `on_resize` / `_apply_compact` / `_schedule_reveal` / `_reveal_selection`, reveal after `_populate_list_for` sets the index).
- [x] Step 3: `tests/test_tui_switcher_footer_fit.sh` pins `max-width: 100%` and `width: {_DIALOG_WIDTH};` (12/12).
- [x] Step 4: new test passes post-fix (9/9 OK).

No deviation from the approved design.

### Review round (Step 8): footer key assertions

A reviewer noted the footer check required only the action words
(`switch` / `close` / `session`) and passed with the key labels removed. The
check now reads the **footer region only** (each hint row sliced to the hint's
columns, rows joined, whitespace collapsed so a wrap does not split a phrase)
and requires each phrase whole, key included: every `_HINT_ITEMS` segment, the
companion segment when on, `Enter switch`, `←/→ session` (multi mode) and
`<open-key>/Esc close` (built from `_OVERLAY_OPEN_KEY` /
`_OVERLAY_TOGGLE_CLOSES`, so a rebind still matches). Negative control (one key
label stripped from the rendered hint, `test_every_hint_word_is_on_screen` +
`test_narrow_monitor_host_gets_the_same_compaction`): drop `Enter` → 5
failures; drop `←/→` → 3 (multi-mode cases only); drop `J/Esc` → 5; no drop →
0.

### Baseline correction

An intermediate baseline built as a *subclass* of the working-tree overlay with
HEAD's DEFAULT_CSS was not faithful: Textual merges `DEFAULT_CSS` across the
MRO, so the subclass still carried `max-width: 100%` and the `-compact` rules.
Every baseline figure below therefore uses HEAD's `tui_switcher.py` loaded as its
own module (`git show HEAD:… > tui_switcher_head.py`), with asserts that it has
no `max-width` and no `_apply_compact`. (The planning-time spikes ran before the
source edit, against the genuine old module, and are unaffected.)

### Pre-fix control (final test file run against HEAD's module)

```
ran 9 failures 25 errors 0
  test_dialog_fits_narrow_screen (width=34), (width=40)
  test_every_hint_word_is_on_screen: '(S)ettings' (40/34 × 1/2 sessions),
      '(G)it' (40/34 × 1/2), '(N)ew task' (34 × 1/2), 'J/Esc close' (40/34 × 2)
  test_long_agent_window_name_stays_inside
  test_narrow_monitor_host_gets_the_same_compaction
  test_right_border_drawn_on_every_dialog_row
  test_selection_stays_drawn_after_resize
  test_short_pane_keeps_selection_drawn_while_navigating:
      (40,18)×2 sessions: '(S)ettings', '(G)it', 'J/Esc close', navigation;
      (40,17)×2, (34,18)×2, (40,14)×1: navigation
```

`WideLayoutTests` (wide layout unchanged; compaction reverts when widened)
passed against HEAD, as expected. The first pre-fix run (token-level footer
check, before the review round) also failed 25 subtests across the same 7
tests, e.g. `dialog Region(x=0, y=5, width=44, height=30) spills past a 40-col
screen`, `'Trails' at y=10 is under the footer (hint starts at y=10)`, and the
long name rebuilt as `…_clipped_n_minimonitor_pane`.

### Post-fix evidence

- `tests/test_tui_switcher_narrow_fit.py`: `Ran 9 tests … OK`.
- Switcher neighbours (pytest, 12 modules incl. hint text, group nav,
  companion spawn, agent launch, markup colour contract, open-key collision,
  default-session notify, git shortcut root, session-key collision, minimonitor
  startup latency, monitor sitrep harvest close): 269 passed.
- Other switcher-referencing modules (board keymap, work report,
  check_screenshots, git tui config, shadow guard, monitor completed status,
  minimonitor shadow pick, pick command screen, shortcut editor, settings
  shortcuts tab, screenshots sample project, shortcut scopes, textual markup
  colours, trails app): 457 passed.
- Shell: `test_tui_switcher_{brainstorm_session,footer_fit,multi_session}.sh`,
  `test_keybinding_registry.sh`, `test_shortcuts_registry_coverage.sh` all pass.
  Not run: `test_screenshots_session_live.py` (live tmux serial carve-out) and
  `test_applink_smoke.sh` — neither exercises the switcher layout.
- Sweep of the real implementation vs HEAD's module (script verbatim below):
  narrow sweep cells=288 **worse=0** improved=126; wide byte-identity
  identical=48 differ=0; resize 40x18→50x18 equals fresh HEAD 50x18: True;
  resize 50x18→34x18 selection drawn [True, True, True].

  Sweep method: hosts minimonitor/monitor/board × companion off/on × 1/2
  sessions × widths 30/34/40/43 × heights 14/16/17/18/20/24; per cell, the
  highlighted row's label must be drawn in the list area above the hint's y
  (and its region non-empty and above the hint) at the initial state and after
  each of 3 Down presses; a cell is "worse" when any step HEAD drew is not drawn
  by the fix. Wide: full composited render compared byte-for-byte at
  44×18/44×40/60×20/120×40.

### Sweep script (verbatim)

Run with the framework venv python from the repo root. It writes HEAD's module
to `headmod/` next to itself; to reproduce against a later tree, replace `HEAD`
with the pre-fix commit.

```python
"""Sweep the real t2340 implementation against HEAD's tui_switcher module.

Prints per-cell regressions and a summary.
"""
import asyncio
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path("/home/ddt/Work/aitasks")
sys.path.insert(0, str(REPO / ".aitask-scripts" / "lib"))

import tui_switcher as ts  # noqa: E402
from agent_launch_utils import AitasksSession  # noqa: E402
from textual.app import App  # noqa: E402
from textual.widgets import Static  # noqa: E402

# Baseline = HEAD's tui_switcher.py loaded as its own module (a subclass would
# inherit the working tree's DEFAULT_CSS — Textual merges DEFAULT_CSS across
# the MRO — so it would not be a faithful baseline).
_head_dir = Path(__file__).resolve().parent / "headmod"
_head_dir.mkdir(exist_ok=True)
(_head_dir / "tui_switcher_head.py").write_text(subprocess.run(
    ["git", "-C", str(REPO), "show", "HEAD:.aitask-scripts/lib/tui_switcher.py"],
    capture_output=True, text=True, check=True).stdout)
sys.path.insert(0, str(_head_dir))
import tui_switcher_head as head  # noqa: E402
assert "max-width" not in head.TuiSwitcherOverlay.DEFAULT_CSS
Base = head.TuiSwitcherOverlay


class Host(App):
    def compose(self):
        yield Static("host")


DESYNC = "main: 1↑/0↓ · aitask-data: 0↑/3↓"


async def cell(cls, w, h, host, comp, n, downs=3, resize=None):
    mod = head if cls is Base else ts
    app = Host()
    sessions = [AitasksSession(f"s{i}", Path(f"/tmp/s{i}"), f"s{i}") for i in range(1, n + 1)]
    out = []
    async with app.run_test(size=(w, h)) as pilot:
        with patch.object(mod, "discover_aitasks_sessions", return_value=sessions), \
                patch.object(mod, "_session_windows", return_value=[]), \
                patch.object(cls, "_compute_desync_summary", return_value=DESYNC), \
                patch.object(cls, "_resolve_companion_target",
                             return_value=object() if comp else None):
            ov = cls(session="s1", current_tui=host, narrow=(host == "minimonitor"))
            await app.push_screen(ov)
            await pilot.pause()
            await pilot.pause()
            if resize:
                await pilot.resize_terminal(*resize)
                await pilot.pause()
                await pilot.pause()
            lv = ov.query_one("#switcher_list")
            for step in range(downs + 1):
                if step:
                    await pilot.press("down")
                    await pilot.pause()
                hint = ov.query_one("#switcher_hint").region
                hl = lv.highlighted_child
                rows = [s.text for s in app.screen._compositor.render_strips(app.screen.size)]
                lab = hl.tui_label
                ok = (hl.region.height > 0 and hl.region.y < hint.y
                      and any(lab in rows[y] for y in range(lv.region.y, min(hint.y, len(rows)))))
                out.append(ok)
            render = "\n".join(rows)
    return out, render


async def main():
    worse = cells = improved = 0
    for host in ("minimonitor", "monitor", "board"):
        for comp in (False, True):
            for n in (1, 2):
                for w in (30, 34, 40, 43):
                    for h in (14, 16, 17, 18, 20, 24):
                        b, _ = await cell(Base, w, h, host, comp, n)
                        r, _ = await cell(ts.TuiSwitcherOverlay, w, h, host, comp, n)
                        cells += 1
                        if any(x and not y for x, y in zip(b, r)):
                            worse += 1
                            print("WORSE", host, comp, n, w, h, b, r)
                        elif b != r:
                            improved += 1
    print(f"narrow sweep: cells={cells} worse={worse} improved={improved}")
    same = diff = 0
    for host in ("minimonitor", "monitor", "board"):
        for comp in (False, True):
            for n in (1, 2):
                for w, h in ((44, 18), (44, 40), (60, 20), (120, 40)):
                    _, a = await cell(Base, w, h, host, comp, n, downs=0)
                    _, b = await cell(ts.TuiSwitcherOverlay, w, h, host, comp, n, downs=0)
                    if a == b:
                        same += 1
                    else:
                        diff += 1
                        print("WIDE DIFF", host, comp, n, w, h)
    print(f"wide byte-identity: identical={same} differ={diff}")
    _, a = await cell(Base, 50, 18, "minimonitor", False, 2, downs=0)
    _, b = await cell(ts.TuiSwitcherOverlay, 40, 18, "minimonitor", False, 2, downs=0, resize=(50, 18))
    print("resize 40x18->50x18 == fresh HEAD 50x18:", a == b)
    r, _ = await cell(ts.TuiSwitcherOverlay, 50, 18, "minimonitor", False, 2, downs=2, resize=(34, 18))
    print("resize 50x18->34x18 selection drawn:", r)


asyncio.run(main())
```

## Final Implementation Notes

- **Actual work done:** The switcher dialog caps to the screen (`max-width:
  100%`). While the screen is narrower than `_DIALOG_WIDTH` (44), a
  width-driven `-compact` class on `#switcher_dialog` drops the dialog's
  vertical padding, the title's bottom padding and the hint's top padding, and
  lowers the list minimum to one row. A post-layout reveal (`scroll_to_widget`
  on the highlighted row) runs after `_populate_list_for` sets the index and on
  every resize. New regression test `tests/test_tui_switcher_narrow_fit.py` (9
  tests). `tests/test_tui_switcher_footer_fit.sh` pins `max-width: 100%` and
  that `_DIALOG_WIDTH` is the CSS width.
- **Deviations from plan:** None from the approved plan. The approved plan
  itself grew over four pre-approval review rounds, from a one-line cap to the
  width-driven compaction. Each round's concern was verified headless before
  the plan changed: the short-pane selection, Down navigation, resize, and the
  host scope of the cap.
- **Issues encountered:** (1) Textual scopes a widget's `DEFAULT_CSS` under its
  own type, so a class set on the `TuiSwitcherOverlay` screen never matched;
  the class goes on the dialog container. (2) Textual merges `DEFAULT_CSS`
  across the MRO, so a subclass baseline with "old CSS" still carries the new
  rules. Baselines must load HEAD's module separately (see "Baseline
  correction"). (3) ListView's own scroll-to-highlight cannot help while the
  list's `min-height: 3` exceeds the space clear of the docked footer: it
  treats covered rows as visible.
- **Key decisions:** The compaction is keyed on the effective width, not the
  host's `narrow` flag, so the cap and its layout adjustments always go
  together (a Monitor host in a narrow pane gets the same treatment). The
  `narrow` flag keeps its one job (AgentCommandScreen). The reveal no-ops
  without the compact class and is scheduled only on a mounted overlay, so wide
  layouts are byte-identical (48/48) and the unmounted unit tests are
  untouched. The footer test asserts key-carrying phrases inside the hint
  region (review round), with the close key derived from
  `_OVERLAY_OPEN_KEY` / `_OVERLAY_TOGGLE_CLOSES`.
- **Upstream defects identified:** None
- **Follow-up:** the docs image
  `website/static/imgs/aitasks_tui_switcher_from_minimonitor.svg` still shows the
  clipped dialog. Refresh it with
  `/aitask-docs-screenshots tui_switcher_from_minimonitor` (that skill owns the
  preview → apply review; t2338 changes the same scene).
