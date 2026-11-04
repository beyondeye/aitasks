---
Task: t2183_minimonitor_render_only_changed_cards.md
Base branch: main
Output branch: main
---

# t2183 — minimonitor: render only changed cards

## Context

t2034_1 measured a live minimonitor's CPU at about 80 % Textual (render ≈55 %,
dispatch ≈25 %) and scanning at ≈14 %. Per-instance CPU grows with the agent
count N. The cause: on every 3 s tick, `MiniMonitorApp._refresh_data` →
`_rebuild_pane_list` (`.aitask-scripts/monitor/minimonitor_app.py:3009`) runs
`remove_children()` + `mount_all()` over **every** card, even when nothing
changed. Each tick therefore pays for a full remount, a markup re-parse, a CSS
restyle, and a layout and compositor pass. Live, that is 38 × ≈3.1 % ≈ 1.2
cores. The shared status server (t2037) does not remove this cost.

**Goal:** per-tick render cost scales with *changed* cards. Scroll, focus and
pin preservation keep working: `_capture_list_scroll` / `_restore_list_scroll`,
and the bottom-pin and width-pin live tests.

### Findings from planning (read-only)

- **Monitor already has a fast path.** `monitor_app.py:1918`
  `_rebuild_pane_list` updates every card in place when the pane-id list is
  unchanged. The minimonitor has no such path.
- **Layout cost of `update`.** `Static.update(content, *, layout=True)`
  (Textual 8.2.7) re-visualizes the content and refreshes. With
  `layout=False` only the widget is repainted, with no screen re-arrange.
- **Height can change without a newline change.** The budgets clip each row to
  the **configured** `_target_width`, but the real pane can be narrower
  (budget block `:228-232`). `MiniPaneCard` is `height: auto` and `Static`
  wraps. A Textual experiment by a reviewer confirmed that `layout=False` kept
  a stale height of 1 where `layout=True` gave 2 for the same text. So an
  unchanged newline count does **not** prove an unchanged height. Also,
  `_target_width` is constant at runtime, so it cannot detect a resize.
- **Session bar updates every tick.** `_rebuild_session_bar` calls
  `bar.update(...)` (that is, `layout=True`) on every tick, even when the text
  is the same. `_refresh_own_live_state` already skips unchanged updates.
- **What changes per tick.** `IDLE/PROMPT/DONE <n>s` counts seconds up to
  999 s, so an idle card changes on every tick for about 16 minutes, then once
  a minute. `Active`, parked and frozen rows, titles and gate counts are
  stable. The phase row changes only when the phase changes.
- **Focus and the click race (t2201).** `_refresh_data` saves `saved_pane_id`
  at the top of the tick, before several awaits. A click during those awaits
  updates `_focused_pane_id` through `on_descendant_focus` (`:3213`). That
  handler only records `MiniPaneCard`s. The tick then restores the stale id.
  t2201 (Ready; depends on t2183 and t2037_3) owns the full fix. Its own text
  says: if the prerequisite work already fixes it, verify and record the
  outcome without redundant code. t2201's advisory note asks that the in-place
  path never re-focus a stale id, and that the full-rebuild path keep t2201's
  behaviour.
- **t2037_3 and protocol deltas.** t2037_3 (minimonitor subscribe, Ready) swaps
  the `TmuxMonitor` construction and does not touch the rebuild. Protocol
  deltas (p2034_3) cannot say whether a card's text changed: the text also
  depends on marks, the task cache, the gate ledger, compare mode, the
  completed set and the width. **Decision: diff on the rendered card text.**
  This is source-agnostic and works unchanged under the t2037 client. A note
  goes to t2037_3 at Step 8e.
- **Test landscape.**
  - About 15 modules build the app with `__new__` and a `_FakeContainer`
    (only `remove_children` / `mount_all`), and call `_rebuild_pane_list()`
    with no arguments.
  - `tests/test_minimonitor_scroll_preservation.py` (`_ListHost`,
    `_RefreshHost`) and `tests/test_minimonitor_bottom_pin.py` reproduce the
    t1539/t1653 bugs by re-ticking an **unchanged** pane set.
  - `tests/test_minimonitor_bottom_pin_live.py` boots two runs: current and
    the `AIT_T1653_LEGACY_PIN=1` control. Its harness,
    `tests/lib/minimonitor_live_harness.py` (`LiveHarnessApp(_RefreshHost)`),
    changes card heights on every tick.

## Method (measurement, shared by Step 1 and Step 8)

Re-create t2034_1's harness verbatim from the appendix of
`aiplans/archived/p2034/p2034_1_measure_monitor_scan_cost.md`: `bucket.py`,
`tickcount.py`, `cpurate.sh`, `run_spy.sh`, `watch.sh`, `fakeagent.sh`,
`scale.sh`. They go into `$S=<scratchpad>/t2183`. The only changes:

- the socket is `ait_t2183_scale`, with the `guard()` pattern `ait_t2183_*`;
- `S` points at the new directory;
- `fakeagent.sh` honours `FAKE_IDLE=1`: it prints 300 lines, then
  `sleep infinity`. The IDLE counter then changes on every tick, which is the
  worst case for the diff. `scale.sh` passes the variable through.

The same rules as t2034_1 apply:

- py-spy 0.4.3 in a throwaway venv, **`--gil`**;
- `AITASKS_TMUX_SOCKET` passed explicitly;
- the companion layout;
- the `/proc/<pid>/environ` and `tickcount` pre-checks;
- the liveness watch.

All runs are sequential:

- **CPU table:** `scale.sh servercost N 1` (two 60 s `cpurate` windows), for
  N ∈ {1, 4, 12} × {active, idle};
- **profile table:** `scale.sh profile N` (py-spy, 120 s), for N ∈ {1, 4, 12}
  active, plus N = 12 idle. Report the buckets and the coverage
  (GIL-held sample-seconds ÷ utime+stime) for each run.

## Implementation steps

0. **Before any other write:** acknowledge the t2201 note the user approved:
   `./.aitask-scripts/aitask_note.sh read 2183 --by t2183 --ids 2026-11-04T15:02:01Z.24c6b90cd39091510b90ba35 --mode explicit`.

1. **Baseline (before any code edit).** First confirm with
   `git status -- .aitask-scripts/monitor` that no other session has touched
   `monitor/`. Then run the Method on the unmodified tree.

   **Decision rule, on whole-process numbers.** Mounting queues Textual work
   that runs later from message-pump and compositor stacks, without
   `_rebuild_pane_list` as an ancestor. So the denominator is never the
   samples under `_rebuild_pane_list`. Compare, as shares of all GIL-held
   samples:
   - (a) `textual.render` + `textual.dispatch`, the whole-process buckets the
     diff can cut;
   - (b) the direct builder samples: inclusive `_agent_card_text` +
     `_other_card_text`, which the diff cannot cut, because text is still
     built every tick.

   Stop and report to the user before editing only if (b) ≥ (a) at N = 12.
   Otherwise continue, and record both numbers.

2. **Split entry building from mounting** (`minimonitor_app.py`).
   - Add `NamedTuple` `_ListEntry(kind, key, text, classes)`, where `kind` ∈
     {`card`, `divider`, `header`}. `key` is the `pane_id` for a card and the
     rendered text for a divider or header.
   - `_build_list_entries(self) -> list[_ListEntry]` holds today's filter,
     sort and group logic from `_rebuild_pane_list`: own-pane exclusion, the
     `P` filter, `pane_sort_key`, multi-mode dividers, the `other (N)` header.
     It calls `_agent_card_text` / `_other_card_text` as today, in the same
     order and producing the same text.
   - `_rebuild_pane_list(self, entries=None)` builds the entries when given
     `None`, then runs `remove_children()` + `mount_all(...)` as today, so the
     no-argument callers keep working. At the end it records
     `self._list_record = _ListRecord(keys, texts, widgets)`.
   - `__init__` sets the record to `None`. Every read uses
     `getattr(self, "_list_record", None)`, because the `__new__` stubs never
     run `__init__`.

3. **In-place planner:** `_plan_in_place_list_update(self, entries)`. It
   returns `None` when a full rebuild is needed, otherwise a list of
   `(card, text, layout)` updates, possibly empty.

   It returns `None` when:
   - `self._IN_PLACE_LIST_UPDATES` is false. This class attribute is `True`
     in production and documented as the test seam.
   - There is no record.
   - The `(kind, key)` sequence differs. This covers an agent added, removed
     or reordered, divider or `other (N)` changes, a `P` toggle, and a
     multi-session toggle.
   - Any recorded widget is not `w.is_attached and w.parent is container`.
     This catches an external removal, and keeps the `_FakeContainer` tests on
     the full path, because their widgets are never attached.

   For each card whose text differs from the record, `layout` is set by
   **`_card_height_stable(card, old, new)`**. It returns True only when all
   of these hold:
   - `card.content_size.width > 0`, so the card has been laid out;
   - the newline counts are equal;
   - both old and new **fit** that width: every line of
     `Content.from_markup(text).split("\n")` has
     `cell_length <= card.content_size.width`. This is the parse `Static`
     itself uses for a `str`. Confirm the API in Textual 8.2.7 before relying
     on it.

   `layout = not _card_height_stable(...)`. If the old text wrapped, or the
   new one will, height may change, so `layout=True` is used and the
   scroll-preservation path below runs. The cost is two markup parses for
   each *changed* card only.

4. **Rewire `_refresh_data`** (the block from `_capture_list_scroll()` to
   `call_after_refresh(self._restore_list_scroll, …)`, lines ~1866–1888).
   `saved_pane_id` is removed. **The selection is read at restore time, after
   every await of the tick:**

   ```python
   entries = self._build_list_entries()
   updates = self._plan_in_place_list_update(entries)
   if updates is not None and not any(lay for _, _, lay in updates):
       # No card is torn down and no geometry changes: no capture, lock or
       # restore. Focus was never lost, so a click made during this tick's
       # awaits stands. Restore only when NOTHING is focused (e.g. after a
       # blur), and then from the current intent.
       self._apply_list_updates(updates)
       if self.focused is None:
           self._restore_focus(self._focused_pane_id)
   else:
       # Unchanged t1539/t1653 sequence (capture → gen++ → lock →
       # fail-safe timer), then:
       if updates is None:
           await self._rebuild_pane_list(entries)
       else:
           self._apply_list_updates(updates)       # some layout=True
       self._restore_focus(self._focused_pane_id)  # current intent
       self.call_after_refresh(self._restore_list_scroll, gen, 0)
   ```

   - `_apply_list_updates` calls `card.update(text, layout=layout)` and
     refreshes `record.texts`.
   - On the height-change path no card is removed, so the restore re-focuses
     the card that is already focused. That is harmless, and `scroll_visible`
     is False as today.
   - **Coordination with t2201.** This adopts the "current intent at restore
     time" half of t2201's fix direction on both paths. It is the minimal
     change that keeps the new in-place path from reverting a click. Left to
     t2201, and recorded in a Step 8e note to it:
     - the deferred `card.focus()` vs a queued click (→ synchronous
       `set_focus`);
     - a click between `remove_children` and `mount_all`;
     - the card-0 "other agent" candidates.
   - Rewrite the stale docstring and comment statements so they describe the
     current behaviour: `MiniPaneList` (:684), `_capture_list_scroll` (:2158),
     `_agent_card_text`'s caller note, and the `_restore_focus` comment about
     `saved_pane_id`.

5. **Session bar.** Keep the last rendered string in
   `self._session_bar_text` (read with a `getattr` default), and call
   `bar.update` only when it changes. `bar.display = …` still runs every tick.

6. **Headless tests.**
   - `tests/test_minimonitor_scroll_preservation.py` `_ListHost`: set
     `_IN_PLACE_LIST_UPDATES = False`, with a comment. These cases, and the
     headless bottom-pin module that imports them, reproduce the t1539/t1653
     rebuild by re-ticking an unchanged set. They pin the full-rebuild path,
     which production still runs on every structural change, so their
     documented negative controls stay meaningful.
   - New `tests/test_minimonitor_incremental_list.py`. It uses a
     `_RefreshHost` subclass with the seam on, an overflowing list, and a
     controllable `_agent_card_text`. Read
     `aidocs/framework/testing_conventions.md` first, since `run_test`
     reaches workers. The cases:
     1. An unchanged tick keeps every card object (`id()`), makes no
        `remove_children` call and no card `update` (spy), and keeps a
        mid-list `scroll_y` and the focused card.
     2. A one-card change at the same height (wide pane, the text fits)
        updates only that card, with `layout=False`.
     3. A line-count change uses `layout=True`. The card's region height
        equals its new line count, and the mid-list anchor card keeps its
        on-screen row.
     4. **Narrow pane.** The app is narrower than `_target_width`, and the
        update keeps the newline count but goes from fitting to wrapping.
        Expect `layout=True`, and the card's region height grows to the
        wrapped height. Assert the wrap really occurs, so the case is not
        vacuous.
     5. A bottom-pinned list stays pinned when a card above grows in place.
     6. A full rebuild (new objects) happens for: a pane added or removed, a
        reorder, `P` toggled, multi-session toggled, and a recorded card
        removed externally.
     7. **Click during a suspended capture, on both paths.**
        `capture_all_async` blocks on an `asyncio.Event`. While the tick is
        suspended, click card B (`pilot.click`), then release the tick.
        Focus and `_focused_pane_id` must end on B:
        - (a) on an unchanged/in-place tick;
        - (b) on a tick whose pane set changed (full rebuild).

        Run each case red against today's code before the fix. Record the
        red output.
     8. An unchanged session-bar text makes no `bar.update` call.

7. **Live pin coverage of the production path** (concern 3).
   - `LiveHarnessApp` runs the **in-place path by default**
     (`_IN_PLACE_LIST_UPDATES = True`). Its per-tick height churn exercises
     `layout=True` in-place updates under a real pty.
   - Add `AIT_T2183_FULL_REBUILD=1`, which sets the seam False, to select the
     full path.
   - Add an in-place negative control, `AIT_T2183_NO_INPLACE_PIN=1`. It
     disables the *current* pin mechanism on that path: after each tick it
     clears `MiniPaneList._anchored`, the anchor that Textual's compositor
     re-pins from, which `_restore_list_scroll` relies on for a pinned list.
     It adds no compensating snapshot.
   - `tests/test_minimonitor_bottom_pin_live.py` boots three runs:

     | run | env | expectation |
     |---|---|---|
     | `current` (in-place, production) | — | pin holds (`test_5`) |
     | `inplace_control` | `AIT_T2183_NO_INPLACE_PIN=1` | reproduces the drift |
     | `legacy` (historical, full path) | `AIT_T1653_LEGACY_PIN=1` + `AIT_T2183_FULL_REBUILD=1` | reproduces the drift (`test_4`, unchanged) |

   - Extend the overflow, thumb-hit, comparable and scrolled assertions to all
     three runs, and add `test_4b` for the in-place control. Sockets stay
     per-run and per-pid. Update the module docstring: three runs, what each
     control removes, and why a control that removes only the app-side
     capture/restore would be vacuous.
   - Record each run's wall time. The module stays in the serial carve-out.
     CLAUDE.md's list is unchanged, since there is no new module.

8. **After measurement.** Re-run the Method on the edited tree. Record the
   before and after tables in Final Implementation Notes:
   - per-instance CPU at N = 1/4/12, active and idle;
   - buckets and coverage;
   - the shift in `textual.render` / `textual.dispatch` share;
   - the Step 1 decision-rule numbers.

### Post-phase (risk mitigations)

1. [incremental_list_negative_controls] Apply each mutation to
   `minimonitor_app.py` on its own, run
   `tests/test_minimonitor_incremental_list.py`, and revert it by hand with
   Edit. Never use `git restore`, because the worktree is shared and dirty.
   - (a) The planner returns `[]` instead of its updates. Tests 2 and 3 must
     fail.
   - (b) `_card_height_stable` checks only the newline count, with no fit
     check. Test 4 must fail.
   - (c) `layout` is always False. Test 3 must fail.
   - (d) The attachment check is removed. The external-removal case in test 6
     must fail.
   - (e) The in-place branch calls `_restore_focus` unconditionally with the
     top-of-tick id. Test 7a must fail.

   Record each mutation, the failing test names and the assertion text. A
   mutation that fails nothing means a test is missing: add it.
2. [live_pin_control_on_inplace_path] Run
   `python3 tests/test_minimonitor_bottom_pin_live.py` and confirm:
   - the `current` run passes on the in-place path;
   - `inplace_control` reproduces the drift;
   - `legacy` still reproduces it on the full path.

   If `inplace_control` does **not** reproduce the drift, the in-place pin is
   held by something other than the anchor. Find out what that is and target
   it with the control. **Do not** move the harness back to the full path.
   Stop and report if the cause cannot be found. Record all three runs.

## Verification

- `python3 tests/test_minimonitor_incremental_list.py` passes.
- The existing minimonitor/monitor modules pass: scroll_preservation,
  bottom_pin, focus_in_click, other_section, own_mark, frozen/parked filter,
  session_divider, pane_sort_order, markup_escape, shadow_status,
  auto_close_guard, row_budget, top_chrome_render, startup_input_latency.
- The live carve-out passes: `python3 tests/test_minimonitor_bottom_pin_live.py`
  (three runs) and `python3 tests/test_minimonitor_width_pin_live.py`.
- `bash tests/run_all_python_tests.sh` passes. Read the last line, and check
  `PIPESTATUS`.
- The before/after CPU tables are recorded at the same N, with py-spy
  coverage.
- Step 8e sends two notes:
  - **to t2201:** which half of its fix landed, which tests cover it, and
    what remains;
  - **to t2037_3:** the rendered-text diff is source-agnostic, and the
    `_refresh_data` sequence has changed.

## Step 9 reference

The work is on the current branch (`main`). Commit the code as
`performance: … (t2183)`. Commit the plan through
`./.aitask-scripts/aitask_task_commit.sh`. Archive with the standard Step 9
flow.

## Risk

### Code-health risk: medium
- `_refresh_data` gets a second list-update path beside the load-bearing t1539/t1653 scroll and focus sequence. A wrong "height unchanged" decision would skip capture/restore exactly when it is needed. The decision is made from the card's actual content width and a fit check on both texts, not from the configured width or newline counts. · severity: medium · → mitigation: inline post-phase incremental_list_negative_controls
- The live pin test changes from two runs to three, with a new env-driven control in the harness. A control that removes the wrong mechanism would make the comparison vacuous. · severity: medium · → mitigation: inline post-phase live_pin_control_on_inplace_path
- The focus contract changes on both paths: the selection is read at restore time. This takes part of t2201's fix direction, so the two tasks must not diverge. · severity: low · → mitigation: none (handled in plan: tests 7a/7b, and a Step 8e note to t2201)

### Goal-achievement risk: medium
- The savings depend on how much text changes per tick. The `IDLE <n>s` counters change on every tick for about 16 minutes, so in the worst case every card still re-renders, though without the remount. The idle-mode runs measure this rather than assume it. · severity: medium · → mitigation: none (handled in plan: Method idle-mode runs)
- Card text building might dominate the whole-process Textual cost. Step 1's whole-process decision rule stops the work before any code edit if it does. · severity: low · → mitigation: none (handled in plan: Step 1 decision rule)

### Planned mitigations
- timing: post-phase | name: incremental_list_negative_controls | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a wrong "height unchanged" or focus decision | desc: five single mutations of the planner, fit check, layout flag, attachment check and focus branch, each proven to fail a named new test
- timing: post-phase | name: live_pin_control_on_inplace_path | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the live pin test must exercise the production in-place path | desc: three live runs (current in-place, in-place control without the anchor, historical legacy full-path control); never fall back to the full path
