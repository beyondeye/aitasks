---
Task: t1499_fix_failed_verification_t1498_item5.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1499 — Restore minimonitor's top chrome (same-edge dock collision)

## Context

`ait minimonitor` composes six widgets as direct children of the Screen. **Four**
of them set `dock: top`:

| DOM order | id | CSS | purpose |
|---|---|---|---|
| 1 | `#mini-session-bar` | `dock: top; height: 1` | session name, agent counts, awaiting/idle/done, desync summary, `rc:retry` / `rc:fb` control-channel badges, and the `Not inside tmux` startup error |
| 2 | `#mini-shadow-stale` | `dock: top; height: auto` | live shadow-staleness warning (t1104, t1493) |
| 3 | `#mini-loop-status` | `dock: top; height: auto` | auto-recheck loop status (t1159_2) |
| 4 | `#mini-own-agent` | `dock: top; height: auto` | followed-agent panel (t1382/t1383) |

Under Textual 8.2.7 (the pinned runtime in `~/.aitask/venv`) sibling widgets
docked to the same edge **do not stack** — they are all assigned the identical
region and only the **last in DOM order** is composited. Measured on the real
`MiniMonitorApp` at `run_test(size=(40,30))` with every banner populated:

```
#mini-session-bar   Region(x=0, y=0, width=40, height=1)   display=True visible=True
#mini-shadow-stale  Region(x=0, y=0, width=40, height=1)   display=True visible=True
#mini-loop-status   Region(x=0, y=0, width=40, height=1)   display=True visible=True
#mini-own-agent     Region(x=0, y=0, width=40, height=1)   display=True visible=True
#mini-pane-list     Region(x=0, y=1, width=40, height=19)
#mini-key-hints     Region(x=0, y=20, width=40, height=10)

y=0: '                                        '   <- blank
SESSIONMARK False   STALEMARK False   LOOPMARK False
```

So three surfaces are **permanently dead**, in every state:

- the shadow-staleness banner t1499's parent task (t1498 item #5) failed on;
- the auto-recheck loop banner (**not** named in t1499 — found during planning);
- the whole session bar, including the `Not inside tmux` error a user launching
  outside tmux is supposed to see.

The state machines behind them are fine (`_set_shadow_stale_banner`,
`_set_loop_banner`, `_rebuild_session_bar` all compute and write the right text).
Only the surface is dead — which is why the DOM-free test seams
(`_shadow_stale_banner_text`, `_loop_banner_text`) and the markup test in
`test_markup_colour_contract.py` all pass while the user sees nothing.

**Not a t1493 regression.** t1493 added a new signal to an already-dead surface.

The repo already fixed this exact bug class once, in the board (t1278: a docked
`#filter_area` painting over the docked `Header`, hiding every `sub_title` write
for the app's whole history). The fix there was **undock and let it flow**, and
the rule is recorded in `aitask_board.py:7980-7990`. This plan applies the same
fix and the same guard idiom.

**Intended outcome:** all four top-chrome widgets composite in DOM order at their
own rows, with **zero net row cost in steady state** — verified below.

## Files to modify

- `.aitask-scripts/monitor/minimonitor_app.py` — `CSS` (`:308-395`),
  `_set_shadow_stale_banner` (`:2253`), `_set_loop_banner` (`:2397`),
  `_maybe_build_own_agent_panel` (`:1282-1304`), `on_resize` (`:605`), plus a new
  `_refresh_short_mode` helper and four module constants. `compose()`
  (`:555-563`) is **unchanged**.
- `tests/test_minimonitor_top_chrome_render.py` — **new** regression guard.

## Implementation steps

### Pre-phase (risk mitigations)

1. `[characterize_composited_minimonitor_rows]` **Before touching any CSS**, run
   the existing modules that assert on composited minimonitor rows or on
   `MiniMonitorApp.CSS` text and confirm they are green against the unmodified
   tree: `tests/test_minimonitor_own_mark.py`,
   `tests/test_monitor_session_divider.py`,
   `tests/test_markup_colour_contract.py`,
   `tests/test_minimonitor_other_section.py`,
   `tests/test_minimonitor_gate_phase_row.py`. Record, in the plan's Final
   Implementation Notes, the row index at which `CompositedWidthTests`
   (`test_minimonitor_own_mark.py:713`) currently finds its `★` line at
   `size=(40,24)`. A characterization that was never green on the old code pins
   nothing, and without the recorded index a post-change failure cannot be told
   apart from a pre-existing one.

### 1. Undock the top chrome (`minimonitor_app.py` CSS)

Delete `dock: top;` from all four rules — `#mini-session-bar` (`:310`),
`#mini-shadow-stale` (`:319`), `#mini-loop-status` (`:330`), `#mini-own-agent`
(`:339`). Everything else in those rules stays.

`#mini-pane-list` keeps `height: 1fr` (it absorbs the remainder) and
`#mini-key-hints` keeps `dock: bottom` — it is the **sole** occupant of that
edge (verified: it is the only `dock: bottom` in the file, the app renders no
`Footer`, and `ShortcutsMixin` only ever pushes a modal screen).

Add a CSS comment above the block, modelled on `aitask_board.py:7974-7990`:

```
/* Top chrome. NEVER re-add `dock:` to any of these four (t1499). Textual
   places same-edge docked siblings at the SAME offset instead of stacking
   them, so all four landed on y=0 and only #mini-own-agent — last in DOM
   order — was composited. The other three never rendered in any state,
   silently: each still reported display=True, visible=True and a "correct"
   region, which is why the DOM-free banner seams and the markup contract
   test stayed green. Same defect and same fix as the board's #filter_area
   (t1278). Undocked, they flow in compose order and #mini-pane-list (1fr)
   takes the rest.

   `display: none` here is LOAD-BEARING, not cosmetic: an empty Static with
   `height: auto` resolves to ONE row, not zero, so without it the three
   collapsible widgets would cost 3 permanent rows in a 40-column companion
   pane. Each setter below turns display back on when it has something to
   show.

   The `max-height` caps are load-bearing too: undocked chrome GROWS, and
   unbounded it overruns the bottom-docked #mini-key-hints and paints the
   agent list off the screen at ~20 rows. Capped, chrome tops out at 11 rows;
   when even that does not fit, _refresh_short_mode compacts the hints
   instead — measuring what the chrome actually occupies, never a budget. */
```

### 2. Collapse empty chrome to zero rows (`display: none` + setters)

The old CSS comments claimed "empty text ⇒ 0 rows". That was never true — it was
masked by the dock collision. Measured: an empty `Static` with `height: auto`
occupies **1 row**. Undocking without this step would cost 3 extra rows.

Add `display: none;` to `#mini-shadow-stale`, `#mini-loop-status` and
`#mini-own-agent` (not `#mini-session-bar` — it is always populated), and flip it
on at each write site:

- `_set_shadow_stale_banner` (`:2253`) — inside the existing
  `contextlib.suppress(Exception)` block:
  ```python
  widget = self.query_one("#mini-shadow-stale", Static)
  widget.update(text)
  widget.display = bool(text)
  ```
- `_set_loop_banner` (`:2397`) — same shape on `#mini-loop-status`.
- `_maybe_build_own_agent_panel` (`:1297-1304`) — after `panel.mount_all([...])`,
  set `panel.display = True`. The panel is built once and never emptied, so the
  hidden state is only the pre-resolution window (and the not-in-tmux case).

Update both setter docstrings to state that the `display` toggle is what keeps
the row cost at zero, and fix the two stale `empty ⇒ 0 rows` CSS comments to say
*how* that is achieved.

Inline-stub safety: `tests/test_multi_session_minimonitor.sh` stubs `query_one`
with a plain `FakeContainer` class, so `panel.display = True` is an ordinary
attribute write there — no breakage.

### 3. Bound the chrome, and let the hints yield under pressure

Undocking makes the chrome *grow* for the first time, and unbounded growth
collides with the bottom-docked hints. Measured with the real worst-case
`format_shadow_stale_banner` output (`⚠ shadow feedback is stale — agent moved
on (analyzed 1m33s ago; round 12 block 2h03m older still)`, 98 chars → 3 rows at
38 usable columns), the longest loop banner, and a built own-agent panel:

```
(40,20) uncapped: chrome=11  list=(y11,h1)  hints=(y10,h10)  <- list overrun, invisible
(40,18) uncapped: chrome=11  list=(y11,h1)  hints=(y8,h10)   <- own-agent panel gone too
```

Today's collapsed chrome costs 1 row and can never overrun, so this is a
regression the fix would introduce. Two bounded changes:

**(a) Cap each collapsible widget** so worst-case chrome is a known constant:
`max-height: 3` on `#mini-shadow-stale` and `#mini-loop-status` (3 rows holds
the two common banners whole and clips only the parenthetical tail of the two
longest; the leading `⚠ shadow feedback is stale — …` clause carries the
actionable signal), and `max-height: 4` on `#mini-own-agent` — a `VerticalScroll`,
so overflow scrolls rather than vanishing. Worst case becomes
`1 + 3 + 3 + 4 = 11` rows.

**(b) Compact the key hints when the layout cannot fit both.** The hints are
static help, reachable in full via `?`; they are the right thing to yield.

The trigger measures the chrome's **actually occupied height**, not a worst-case
budget. A budget-based predicate would be wrong in the common case:
`_maybe_build_own_agent_panel` builds `#mini-own-agent` once early in a normal
tmux session and leaves it displayed forever, so "is any collapsible widget
displayed?" is true almost always — a 22-row pane with no banners would enter
short mode and lose eight hint lines for nothing.

```python
_PANE_LIST_FLOOR_ROWS = 3
_SHORT_HINT_ROWS = 2
_KEY_HINTS_ROWS = KEY_HINTS_TEXT.count("\n") + 1   # derived, not a second literal
_TOP_CHROME = ("#mini-session-bar", "#mini-shadow-stale",
               "#mini-loop-status", "#mini-own-agent")

def _refresh_short_mode(self) -> None:
    """Let the static key hints yield when live chrome needs the rows."""
    chrome = sum(self.query_one(sel).region.height for sel in _TOP_CHROME)
    self.set_class(
        chrome + _KEY_HINTS_ROWS + _PANE_LIST_FLOOR_ROWS > self.size.height,
        "short",
    )
```

```
MiniMonitorApp.short #mini-key-hints { max-height: 2; }
```

Scheduled with `self.call_after_refresh(self._refresh_short_mode)` from
`on_resize` **and** from the three chrome write sites — chrome height changes
without a resize, and the region reads must happen after layout. It converges in
one pass and cannot oscillate: chrome heights depend on width and content only,
never on the hints' height, and the predicate compares against
`_KEY_HINTS_ROWS` (the hints' *desired* height) rather than their current
rendered height, so the class does not feed back into its own input. Verified by
recomputing three times at every size — the measured chrome was identical on
every pass.

Measured with (a)+(b), driving the own panel through the real
`_maybe_build_own_agent_panel`:

| pane | own panel only (chrome 5) | + both banners (chrome 10) |
|---|---|---|
| `(40, 30)` | full hints, list h=15 | full hints, list h=10 |
| `(40, 22)` | full hints, list h=7 | **short**, list h=10 |
| `(40, 18)` | full hints, list h=3 | **short**, list h=6 |
| `(40, 16)` | **short**, list h=9 | **short**, list h=4 |

No overrun (`list.bottom <= hints.y`) and the own-agent identity line on screen
at every cell.

### 4. New regression guard — `tests/test_minimonitor_top_chrome_render.py`

Boots the **real** `MiniMonitorApp` (not a `_RowHost` stand-in) under
`run_test`. With `TMUX` unset, `on_mount` (`:568-572`) writes the
`Not inside tmux` bar and **returns before `_start_monitoring()`** — a real-app
boot with no tmux I/O, no timers and no in-flight `@work` worker at block exit
(the t1487 teardown hazard).

**Chrome is driven through the production code paths, never mounted by hand.**
The own-agent panel is built by calling the real `_maybe_build_own_agent_panel()`
with only `_find_own_window_snapshot` and `_is_marked` stubbed — that method is
where the new `panel.display = True` lives, so a test that mounted children
itself would prove nothing about the writer. Likewise the banners go through
`_set_shadow_stale_banner` / `_set_loop_banner`, and their text comes from the
real `format_shadow_stale_banner` rather than a short marker literal.

Assertions are **rendered geometry and composited text only** — never
`_shadow_stale_banner_text`, `display`, `visible`, or `region` alone, which are
exactly what let this survive:

1. `test_top_chrome_widgets_do_not_share_a_region` — populate all four, then for
   each DOM-adjacent pair assert `earlier.region.bottom <= later.region.y`.
   Assert on the **losers** (the first three), not on `#mini-own-agent`, which
   survives the fault by being last in DOM order. **Every one of the four must be
   present in the checked sequence** — the assertion must not silently skip a
   widget for being invisible, or the whole test degenerates when one is hidden.
2. `test_chrome_text_reaches_the_composited_frame` — the session-bar text, a
   distinctive substring of the real staleness banner, the loop banner, **and the
   own-agent panel's identity line** each appear in
   `app.screen._compositor.render_strips(app.screen.size)`. Compare against text
   with the wrap folded out (join rows and collapse whitespace): at 38 usable
   columns every one of these strings wraps, so a naive `in` check on a single
   row silently never matches.
3. `test_own_agent_panel_is_visible_and_flows_below_the_banners` — after the real
   `_maybe_build_own_agent_panel()`, `#mini-own-agent` has `region.height >= 1`,
   a region strictly below `#mini-loop-status`, and its identity text on screen.
   This is the guard that fails if the `panel.display = True` line is ever
   dropped — without it the suite would pass with the panel permanently hidden.
4. `test_not_inside_tmux_error_is_visible` — the `on_mount` error string reaches
   the frame (a message that is invisible today).
5. `test_empty_chrome_costs_no_rows` — steady state at `(40, 30)`: the three
   collapsible widgets have `region.height == 0`, and `#mini-pane-list.region`
   is `y=1, height=19` — **byte-identical to the pre-fix budget**, pinning the
   "no row regression" claim.
6. `test_live_chrome_never_overruns_the_docked_key_hints` — the long-content
   test. Worst-case chrome (real banner strings + built own panel) at `(40, 30)`,
   `(40, 24)`, `(40, 20)` and `(40, 16)`: assert
   `pane_list.region.bottom <= key_hints.region.y` at every size,
   `pane_list.region.height >= 1`, and all four chrome texts still on screen.
   Without step 3 this fails at `(40, 20)` and below.
7. `test_short_mode_engages_and_releases` — both directions, **both with the
   production own panel built**, so neither case is reachable only by skipping
   `_maybe_build_own_agent_panel`:
   - `(40, 22)` with both banners live → the `short` class is set and
     `#mini-key-hints.region.height == _SHORT_HINT_ROWS`;
   - `(40, 22)` with the own panel built and **no** banners → the class is
     **not** set and the hints keep all `_KEY_HINTS_ROWS` rows. This is the exact
     case a max-budget predicate gets wrong, so it is the discriminating cell.
   - clearing both banners at `(40, 22)` releases the class again (drive the
     transition in one app instance, not two, so a class stuck on is caught).
8. `test_short_mode_predicate_converges` — recompute `_refresh_short_mode` three
   times at `(40, 22)` with live chrome and assert the class and the measured
   chrome height are identical each pass. Pins the no-oscillation claim that
   justifies comparing against `_KEY_HINTS_ROWS` instead of the rendered height.
9. `test_key_hints_occupy_one_row_per_line` — pins `_KEY_HINTS_ROWS`
   (derived from `KEY_HINTS_TEXT`) against the rendered height at 40 columns, so
   a future hint line long enough to wrap invalidates the constant loudly
   instead of silently shifting the short-mode threshold.

The numbers are measured, not assumed — see the table in step 3(b) for the
own-panel / banner matrix, plus the pre-fix-parity steady state:

```
no chrome at all (nothing built, no banners)
(40,30): session y=0 h=1 · stale/loop/own h=0 · list y=1 h=19 · hints y=20 h=10
(40,13): list y=1 h=2
(40,12): list y=1 h=1   <- floor for test 5
```

### Post-phase (risk mitigations)

1. `[display_toggle_contract_guard]` Add
   `test_collapsible_chrome_returns_to_zero_rows_when_cleared` to
   `tests/test_minimonitor_top_chrome_render.py`: set
   `_set_shadow_stale_banner("STALEMARK")` and `_set_loop_banner("LOOPMARK")`,
   `await pilot.pause()`, assert both markers are in `render_strips()` and both
   regions have `height >= 1`; then set each back to `""`, pause again, and
   assert `region.height == 0` **and** the markers are gone from
   `render_strips()`. Pins both directions of the toggle, so the new
   "every collapsible-chrome write site must flip `display`" contract is
   executable rather than a comment.

2. `[negative_control_redock_stale_banner]` With the full guard green, run
   **three separate single-mutation injections**, reverting between each, and
   record each observed failure output in the Final Implementation Notes. A
   negative control that passes, or that fails at an assertion earlier than the
   one being probed, means the guard does not cover the fault it was written
   for.

   | injection | must fail by name |
   |---|---|
   | re-add **only** `dock: top;` to the `#mini-shadow-stale` rule | `test_top_chrome_widgets_do_not_share_a_region` (tripping on `#mini-shadow-stale` itself, the loser — not on an earlier widget) and `test_chrome_text_reaches_the_composited_frame` |
   | delete **only** the `panel.display = True` line in `_maybe_build_own_agent_panel` | `test_own_agent_panel_is_visible_and_flows_below_the_banners` |
   | delete **only** the `MiniMonitorApp.short #mini-key-hints` rule | `test_live_chrome_never_overruns_the_docked_key_hints` (at `(40, 20)`) and `test_short_mode_engages_and_releases` |

## Verification

1. `bash tests/run_all_python_tests.sh --test-dir tests` for the new file plus
   every test the Explore pass identified as touching this surface:
   `test_minimonitor_own_mark.py` (its `CompositedWidthTests` boots the real app
   at `(40,24)` and currently passes *because* `#mini-own-agent` wins the
   collision — the ★ row moves down after this change),
   `test_minimonitor_own_task_info.py`, `test_minimonitor_pick_by_number.py`,
   `test_minimonitor_shadow_pick.py`, `test_minimonitor_other_section.py`,
   `test_minimonitor_gate_phase_row.py`, `test_minimonitor_concern_action.py`,
   `test_minimonitor_auto_close_guard.py`, `test_monitor_session_divider.py`
   (its `_RuleHost` uses `mm.MiniMonitorApp.CSS` verbatim),
   `test_monitor_agent_marks.py`, `test_monitor_modal_space_dispatch.py`,
   `test_markup_colour_contract.py`.
   Read only the last line — `PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`.
2. `bash tests/test_multi_session_minimonitor.sh` (shell, stubs `query_one`).
3. Then the whole Python suite, since `monitor_shared` is imported widely.
4. Live confirmation in a real pane: `ait minimonitor` in a tmux window and
   `tmux -L ait capture-pane -p -t <pane>` — the session-bar line
   (`<session>  N agents`) must appear on row 0, which it does **nowhere**
   today, and the followed-agent panel must still render below it. This is the
   same independent ground truth `test_board_header_row_live.py` provides for
   t1278; no new live harness is added (headless `render_strips()` already
   discriminates here — proven above).
5. Live confirmation of the short-pane path: resize the tmux window so the
   companion pane is under ~20 rows while a shadow staleness banner is standing,
   and confirm via `capture-pane` that the agent list and the followed-agent
   panel are both still on screen and the hints have compacted to two lines.
6. Deferral closure: the `Upstream defects identified:` bullet is written in the
   canonical form above, and the follow-up task's `t<id>` is recorded in the
   Final Implementation Notes and resolves via `aitask_query_files.sh resolve`.
   See "Out of scope" above — this is a gate on closing t1499, not a nicety.

## Out of scope — deferred with an explicit tracking artifact

`TaskPickConfirmDialog` (`monitor_shared.py`) has the same bug class on the
bottom edge: `#pick-confirm-row` (`:1495`, `dock: bottom`, `height: auto`) and
`#task-detail-footer` (`:1501`, `dock: bottom`, `height: 1`) are siblings inside
`#task-detail-dialog` (`compose` `:1590-1631`), with the footer **last** in DOM
order — so the footer overpaints the confirm row's bottom row (unequal heights
overlap rather than coincide). Different screen, needs its own guard; per the
scope decision it is not fixed here.

**Deferral is only real if it is tracked, so this plan owns the artifact, not
just a note.** Concretely, during Step 8:

1. Write the defect under the Final Implementation Notes' canonical
   **`Upstream defects identified:`** bullet — that exact bullet, verbatim,
   because Step 8b parses it by name and anything written in a side bullet or an
   "out of scope" section is invisible to the follow-up offer:

   ```
   - `monitor_shared.py:1495-1501` — TaskPickConfirmDialog docks #pick-confirm-row
     and #task-detail-footer to the same bottom edge inside #task-detail-dialog;
     the footer is last in DOM order and overpaints the confirm row's last row
     (same class as t1499)
   ```

2. Accept Step 8b's follow-up offer so the task is actually created. **If the
   offer does not fire, or is declined, create it explicitly** rather than
   letting the defect close with this task:

   ```bash
   ./.aitask-scripts/aitask_create.sh --batch \
     --name pick_confirm_dialog_same_edge_bottom_dock \
     --type bug --priority medium --effort low \
     --labels tui,aitask_monitormini --commit
   ```

3. **Verification that the deferral survived:** record the resulting `t<id>` back
   into this plan's Final Implementation Notes and confirm the file exists
   (`./.aitask-scripts/aitask_query_files.sh resolve <id>` returns
   `TASK_FILE:`). Closing t1499 without a recorded ID means the deferral failed
   and the defect was silently dropped.

## Risk

### Code-health risk: low

- The `display` toggle in the setters is a new implicit contract: a future
  collapsible chrome widget whose write site forgets to flip `display` writes
  text that never appears — the same silent-failure shape being fixed here, in a
  new guise · severity: low (residual — the contract is made executable in both
  directions by inline post-phase `display_toggle_contract_guard`) ·
  → mitigation: inline post-phase display_toggle_contract_guard
- Four existing test modules assert on composited minimonitor rows or on
  `MiniMonitorApp.CSS` text and could shift when the chrome moves down
  · severity: low (residual — pinned green, with the `★` row index recorded,
  before any edit by inline pre-phase
  `characterize_composited_minimonitor_rows`) ·
  → mitigation: inline pre-phase characterize_composited_minimonitor_rows
- **New (post-inline reassessment).** Undocking lets the chrome grow, so the
  layout gains a second failure mode the old code could not have: flow content
  overrunning the bottom-docked hints. `_refresh_short_mode` must be scheduled
  from every site that changes chrome height, not just `on_resize` — a missed
  call site leaves the class stale rather than erroring, and reading
  `region.height` before layout silently yields 0 · severity: medium ·
  → mitigation: inline post-phase negative_control_redock_stale_banner (third
  injection) plus `test_short_mode_engages_and_releases` (both directions in one
  app instance) and `test_short_mode_predicate_converges`
- **New (post-inline reassessment).** The `max-height: 3` cap silently drops the
  parenthetical tail of the two longest staleness banners (the `analyzed …; round
  N block … older still` detail). The leading clause keeps the actionable signal
  and the picker still shows the full text, but this is a deliberate information
  trade, not a free one · severity: low · → mitigation: none (accepted)

### Goal-achievement risk: low

- The end state was measured against the real class at the pinned Textual
  version before planning, so the approach is proven rather than assumed. The
  residual risk is that a guard written from those measurements passes for the
  wrong reason (e.g. asserts on the surviving widget) · severity: low (residual
  — the fault is injected and the failing test ids and failing widget are pinned
  by inline post-phase `negative_control_redock_stale_banner`) ·
  → mitigation: inline post-phase negative_control_redock_stale_banner

### Planned mitigations
- timing: pre-phase | name: characterize_composited_minimonitor_rows | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — existing composited/CSS-text tests may shift | desc: run the five affected modules green on the unmodified tree and record CompositedWidthTests' current ★ row index
- timing: post-phase | name: display_toggle_contract_guard | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the display-toggle contract is implicit | desc: pin both directions of the collapse toggle (text appears with height>=1, cleared text leaves the frame at height 0)
- timing: post-phase | name: negative_control_redock_stale_banner | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the guard could pass for the wrong reason | desc: re-add dock:top to #mini-shadow-stale alone, confirm the two named tests fail on the loser widget, revert

## Final Implementation Notes

- **Actual work done:** Exactly the approved plan. `dock: top` removed from all
  four top-chrome rules in `.aitask-scripts/monitor/minimonitor_app.py`;
  `display: none` + `max-height` caps added to the three collapsible widgets,
  with the `display` flip added at each of the three production write sites;
  `_refresh_short_mode` / `_schedule_short_mode_refresh` added and scheduled
  from `on_resize` plus those three write sites; module constants `_TOP_CHROME`,
  `_KEY_HINTS_ROWS` (derived from `KEY_HINTS_TEXT`), `_SHORT_HINT_ROWS`,
  `_PANE_LIST_FLOOR_ROWS`. New guard `tests/test_minimonitor_top_chrome_render.py`
  (13 tests). `compose()` unchanged, as planned. Net: +138/−7 in the app,
  408 lines of new test.

- **Pre-phase `[characterize_composited_minimonitor_rows]`:** all five modules
  green on the unmodified tree (`own_mark` 26, `session_divider` 18,
  `markup_colour_contract` 25, `other_section` 25, `gate_phase_row` 37).
  Baseline recorded: `CompositedWidthTests` found its `★` line at **composited
  row index 1** at `size=(40,24)`, with `#mini-own-agent` at
  `Region(0, 0, 40, 3)` and the other three collapsed behind it at
  `Region(0, 0, 40, 1)`. After the fix the `★` line is at **row index 2** and
  `#mini-own-agent` is at `Region(0, 1, 40, 3)` — exactly the predicted one-row
  shift, with the session bar taking y=0.

- **Deviations from plan:**
  - `_refresh_short_mode` is scheduled through a new
    `_schedule_short_mode_refresh()` wrapper rather than a bare
    `self.call_after_refresh(...)` at each site. Forced by a real regression
    (see below), not a preference.
  - The plan's floor test `test_pane_list_keeps_a_row_at_the_minimum_pane_height`
    (pin 1 row at `(40,12)`, 0 at `(40,11)`) was replaced by
    `test_pane_list_keeps_a_row_at_every_pane_height`, a sweep over
    30/20/14/13/12/8/5/4. Short mode makes the old floor obsolete: the hints now
    yield, so the list keeps ≥1 row and never overruns all the way down to a
    4-row pane. Stating it as an invariant over the range is strictly stronger
    than the two magic heights.
  - Short-mode probes moved from `(40, 22)` to `(40, 20)` (`SHORT_PROBE_HEIGHT`).
    At height 22 the measured chrome is 9 rows, not the planned 11
    (`#mini-own-agent` renders 3, not its 4-row cap), so `9 + 10 + 3 = 22` is
    exactly *not* over budget and both the with-banners and without-banners
    cases agreed — a non-discriminating pair. At 20 the single variable
    "are the banners live" flips the outcome, which is what the pair must test.
  - Negative-control injection 1 needed a second variant. Re-docking **one**
    widget makes it the sole occupant of that edge, so nothing is occluded and
    only the geometry test fires; the plan predicted the text test would fire
    too. Re-docking **two** siblings reproduces the original defect shape and
    does fail both. Both variants are recorded below.

- **Issues encountered:**
  - **Regression, caught and fixed:** the first cut called
    `self.call_after_refresh(self._refresh_short_mode)` directly at the three
    write sites. Twelve existing tests across `test_minimonitor_own_mark.py`,
    `test_minimonitor_other_section.py` and `test_monitor_session_divider.py`
    drive those sites against an app built with `MiniMonitorApp.__new__` and a
    stubbed `query_one`, which has no message pump — every one failed with
    `AttributeError: 'MiniMonitorApp' object has no attribute '_closing'`.
    Fixed by routing all four schedule points through
    `_schedule_short_mode_refresh()`, which wraps the call in
    `contextlib.suppress(Exception)` — the same best-effort rationale the banner
    setters already document.
  - The live tmux fixture first hit minimonitor's single-instance guard
    ("A monitor is already running in this window"). Cause: the tmux gateway
    resolves its socket from `AITASKS_TMUX_SOCKET`, defaulting to `-L ait`, so
    the guard enumerated the **real** `ait` socket's panes rather than the
    throwaway one. Setting `AITASKS_TMUX_SOCKET=<socket>` for both the
    `new-session` and the launched command isolates it properly.
  - An empty `Static` with `height: auto` occupies **one** row, not zero. The
    pre-existing CSS comments claiming "empty text ⇒ 0 rows" were never true —
    the dock collision had been masking it. Without the `display` toggle the
    fix would have cost 3 permanent rows instead of 0.

- **Key decisions:**
  - **Undock + flow, not a container wrapper.** Matches the in-repo precedent
    for this exact bug class (t1278, `aitask_board.py:7980-7990`) and needs zero
    `compose()` churn, which keeps the five existing tests that iterate
    `compose()`'s top-level yields untouched.
  - **Fixed `#mini-loop-status` too**, though t1499's description named only
    three widgets. It is the fourth `dock: top` sibling and equally dead;
    leaving it would have half-fixed the root cause. Confirmed with the user.
  - **Short mode measures occupied chrome height, not a worst-case budget.**
    `_maybe_build_own_agent_panel` builds the panel once and leaves it displayed
    for the rest of the session, so a "is anything displayed?" predicate is true
    almost always and would compact the hints on any pane under 24 rows. The
    occupied-height form keeps full hints down to 18 rows in the common
    (no-banner) case.
  - **`max-height: 3` on the banners is an accepted information trade**: it
    clips the parenthetical tail of the two longest staleness messages
    (`analyzed …; round N block … older still`). The leading
    `⚠ shadow feedback is stale — …` clause carries the actionable signal and
    the concern picker still shows the full text.

- **Verification results:**
  - New guard: **13 passed**.
  - The 12 affected minimonitor/monitor modules: **499 passed**.
  - `bash tests/test_multi_session_minimonitor.sh`: **43/43 passed**.
  - Full suite: **`PYTHON SUITE: PASSED (runner=pytest, exit=0)`**.
  - **Live tmux, isolated socket, 40x30 pane** — fixed build, row 0 reads
    ` multi: 1s · 0a`. Positive control on the unmodified file at the same size:
    rows 0-4 all blank. This is the independent ground truth `run_test` cannot
    supply on its own.
  - **Post-phase `[negative_control_redock_stale_banner]`** — four single-mutation
    injections, reverted between each, re-run after the
    `_schedule_short_mode_refresh` refactor:

    | injection | observed |
    |---|---|
    | `dock: top` on `#mini-shadow-stale` alone | `test_top_chrome_widgets_do_not_share_a_region` FAILED — `#mini-session-bar Region(0,3,40,1)` vs `#mini-shadow-stale Region(0,0,40,3)`. Text test did **not** fire: a single docked widget is the sole occupant of its edge, so nothing is occluded. |
    | `dock: top` on `#mini-session-bar` **and** `#mini-shadow-stale` (the original defect shape) | `test_chrome_text_reaches_the_composited_frame` FAILED — "session bar never reached the screen"; `test_top_chrome_widgets_do_not_share_a_region` FAILED tripping on `#mini-session-bar Region(0,0,40,1)`, i.e. on the **loser**, not the surviving later-in-DOM widget; `test_live_chrome_never_overruns_the_docked_key_hints` FAILED. |
    | delete `panel.display = True` | `test_own_agent_panel_is_visible_and_flows_below_the_banners` FAILED (plus 6 others). |
    | delete the `MiniMonitorApp.short #mini-key-hints` rule | `test_live_chrome_never_overruns_the_docked_key_hints` FAILED — `pane list Region(0,9,38,1)` ran into `hints Region(0,6,38,10)` at height 20; `test_pane_list_keeps_a_row_at_every_pane_height` and `test_short_mode_engages_with_live_banners` FAILED. |

    Restored after each: **13 passed**.

- **Upstream defects identified:**
  - `monitor_shared.py:1495-1501` — TaskPickConfirmDialog docks #pick-confirm-row
    and #task-detail-footer to the same bottom edge inside #task-detail-dialog;
    the footer is last in DOM order and overpaints the confirm row's last row
    (same class as t1499)

- **Deferral closure (plan Verification step 6):** the upstream defect above was
  created as **t1563**
  (`aitasks/t1563_pick_confirm_dialog_same_edge_bottom_dock.md`), confirmed via
  `./.aitask-scripts/aitask_query_files.sh resolve 1563` →
  `TASK_FILE:aitasks/t1563_pick_confirm_dialog_same_edge_bottom_dock.md`. The
  task records that the overlap is inferred from CSS + DOM order and not yet
  observed on a composited frame, so confirming it is that task's first step.
