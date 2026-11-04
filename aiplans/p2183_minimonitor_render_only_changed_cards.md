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
   - **Review fix:** `test_3c` counts only `inplace_layout` ticks as in-place
     evidence (at least `MIN_SAMPLES // 2` in the `current` and
     `inplace_control` runs). `test_4b` takes the control's drift only from
     `inplace_layout` samples, so a run whose only drift came from rebuild ticks
     no longer passes. Checked against synthetic traces: the reviewer's
     counterexample (no `inplace_layout` ticks, drift on one rebuild tick)
     fails both tests; drift on rebuild ticks only fails `test_4b`; drift on
     `inplace_layout` ticks passes.
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

## Implementation log

### Step 1 — baseline (2026-11-04 18:37–19:05, omg16, load 8.4–14.2)

Unmodified `minimonitor_app.py` for t2183. The file did carry t2175_5's
uncommitted sitrep-key hunks (bindings, mixin), which add no per-tick work. Its
sha256 prefix was `00be6165a6c4` for every run. HEAD moved
604277980 → b35ee6bb9 mid-series (t2200: `aitask_codeagent.sh` only). All 10
runs passed PRECHECK (one session `t2183scale`, exactly N agents, socket
`ait_t2183_scale`) and stayed alive. py-spy 0.4.3 `--gil` was re-probed on
CPython 3.14.9 with `burst_waits.py`: burn_a:burn_b = 330:156 ≈ 68:32 (70:30
expected).

**Steady per-instance CPU** (`servercost N 1`, two 60 s `cpurate` windows, %
of one core):

| N | active w1 / w2 | idle w1 / w2 |
|---|---|---|
| 1 | 0.25 / 0.27 | 0.27 / 0.23 |
| 4 | 0.82 / 0.83 | 0.83 / 0.83 |
| 12 | 1.55 / 1.43 | 1.60 / 1.50 |

**Profiles** (`profile N`, 100 Hz `--gil`, 120 s including startup; % of
GIL-held non-idle samples):

| run | samples | coverage | producer | app | textual.render | textual.dispatch | render+dispatch |
|---|---|---|---|---|---|---|---|
| active N=1 | 52 | 43 % (0.52 s / 1.22 s) | 15.4 | 21.2 | 11.5 | 42.3 | 53.8 |
| active N=4 | 133 | 68 % (1.33 s / 1.97 s) | 15.0 | 15.0 | 33.1 | 36.1 | 69.2 |
| active N=12 | 219 | 79 % (2.19 s / 2.78 s) | 17.8 | 13.7 | 38.4 | 28.8 | 67.2 |
| idle N=12 | 174 | 69 % (1.74 s / 2.54 s) | 17.8 | 13.2 | 40.2 | 28.2 | 68.4 |

**Decision rule (N = 12):**
- (a) render + dispatch: 67.2 % active, 68.4 % idle;
- (b) builder-inclusive (`_agent_card_text` + `_other_card_text`): 6.4 %
  active, 3.5 % idle.

(b) < (a), so **continue**. For comparison, only 11.9 % (active) and 9.3 %
(idle) of samples have `_rebuild_pane_list` as an ancestor. The deferred Textual
work runs outside it, as the review predicted.

### Step 6 — red runs before the fix

`ClickDuringTickTests` on today's code fails both cases:
- `test_click_during_suspended_capture_survives_in_place_tick`:
  `AssertionError: '%0' != '%1' : the tick reverted the recorded selection`;
- `test_click_during_suspended_capture_survives_full_rebuild`: same assertion.

In both, the precondition `landed` passed: the click focused `%1` before the
tick resumed.

### Deviation

The planner compares each new text with `card.content` (`Static.content`, the
text last set), not with a texts record. The headless `_regrow_cards` helper and
the live harness's out-of-band churn update cards directly, so a separate record
would go stale.

### Steps 2–5 — implementation (`minimonitor_app.py`)

**Shared-file gate.** t2175_5 had uncommitted hunks in this file, so no edit
was made until the user reported that it had landed. The gate was then
re-checked:
- `git diff --quiet HEAD` and `--cached` were both clean;
- all four t2175_5 marker hunks were present in `HEAD:` (52b8b65dc).

Every write ran under a sha256 chain: the file's sha must equal the last
accepted value before writing, and the new sha is accepted afterwards.

**Edits:**
- Module level:
  - `_ListEntry` and `_ListRecord`;
  - `_fits_width` (`Content.from_markup`, the parse `Static` itself uses);
  - `card_height_stable(old, new, width)`: same newline count AND both texts
    fit the actual width. An unlaid-out card, non-`str` content or a parse
    error gives False.
- `MiniMonitorApp`:
  - the `_IN_PLACE_LIST_UPDATES = True` seam;
  - `__init__` state (`_list_record`, `_session_bar_text`);
  - `_build_list_entries` (today's filter/sort/group logic, now emitting
    entries);
  - `_rebuild_pane_list(entries=None)`, which records what it mounted;
  - `_plan_in_place_list_update`;
  - `_card_height_stable(card, …)`, which reads `card.content_size.width`;
  - `_apply_list_updates`.
- `_refresh_data`:
  - the top-of-tick `saved_pane_id` snapshot is removed;
  - an unchanged or same-height tick skips capture/lock/restore, and
    restores focus only when nothing is focused;
  - a geometry-changing tick (an in-place `layout=True` update or a rebuild)
    runs the unchanged t1539/t1653 sequence;
  - both paths restore `self._focused_pane_id`, read after every await.
- Session bar: `bar.update` only when the text changed.
- Comments describe the current behaviour: the `MiniPaneList` docstring, the
  `_agent_card_text` caller note, and the `_restore_focus` comment.

### Step 6 — headless tests

`tests/test_minimonitor_incremental_list.py`: 14 tests, all green. Three
first-draft fixture faults were found and fixed, each a fixture fault rather
than a product fault:
- the anchor row assumed y=6, but multi mode puts a session divider at y=0;
- `_multi_session` already defaults to True, so assigning True was a no-op.
  The test now flips it, and points `_session` at `s1`, because single-session
  mode projects to the app's own session;
- card identity used `id()`, which CPython reuses for the new cards after a
  rebuild frees the old ones. The tests now hold the objects and compare with
  `is`.

Existing modules, all green:
- minimonitor: scroll_preservation 33, bottom_pin 8, focus_in_click 7,
  other_section 25, own_mark 26, row_budget 16, top_chrome_render 28,
  startup_input_latency 18, auto_close_guard 28, own_header_session 28,
  pick_next_characterization 19, pick_by_number 143, concern_action 255;
- monitor: frozen_filter 73, parked_filter 29, session_divider 23,
  pane_sort_order 39, markup_escape 10, shadow_status 19, completed_status 29,
  agent_marks 24, modal_space_dispatch 7, focus_switch 3, shadow_pick 54,
  client_agnostic 30, parked_capture 24, agent_marks_action 28,
  pick_launch_sites 35, monitor_concern_action 95;
- other: shadow_phase_restamp 10, brainstorm_session_tab 16, and
  `test_multi_session_minimonitor.sh` 42/42.

### Post-phase 1 — `incremental_list_negative_controls` (run, file restored to the accepted sha)

| mutant | failing tests | assertion |
|---|---|---|
| (a) planner returns `[]` | same_height_change, line_count_change, narrow_pane_wrap, bottom_pinned_grows | `[] != [('%3', False)]`, `[] != [('%1', True)]`, `[] != [('%3', True)]`, `content did not grow` |
| (b) no fit check | narrow_pane_wrap_change_uses_layout | `[('%3', False)] != [('%3', True)]` |
| (c) `layout=False` always | line_count_change, narrow_pane_wrap, bottom_pinned_grows | `[('%1', False)] != [('%1', True)]`, … |
| (d) no attachment check | externally_removed_card_forces_a_full_rebuild | cards survived a structural change |
| (e) in-place branch restores the top-of-tick snapshot | click_during_suspended_capture_survives_in_place_tick | `'%0' != '%1'` |

### Step 7 / post-phase 2 — `live_pin_control_on_inplace_path`

`tests/test_minimonitor_bottom_pin_live.py`: 8/8 OK, at 11.7 s per run. A
second, recording pass of the three variants (settled samples after the
release) gave:

| run | routes | gaps (max − scroll) |
|---|---|---|
| current (in place, production) | 14 `inplace_layout`, 3 `rebuild` | 0 on all 17 |
| inplace_control (no anchor) | 14 `inplace_layout`, 3 `rebuild` | `inplace_layout` ticks: 15, 0, 0, 15, 0, 30, 0, 15, 30, 24, 73, 56, 132, 64 |
| legacy (full path + pre-fix replica) | 17 `rebuild` | 0 ×10, then 24, 73, 56, 132, 64, 100, 66 |

The in-place control drifts on in-place ticks, so the anchor is what holds the
production path. No fallback to the full path was needed.
`tests/test_minimonitor_width_pin_live.py`: 2/2 OK.

### Full suite (`bash tests/run_all_python_tests.sh`, pytest lane, 9 m 32 s)

Verdict line: `PYTHON SUITE: FAILED (runner=pytest, exit=1)`, with 11 failed,
10735 passed, 6 skipped and 1 error. Every failure traces to t2037_1's
in-flight, **untracked** status-server files
(`.aitask-scripts/monitor/status_server.py`,
`tests/test_monitor_status_server{,_live}.py`; p2037_1 names them 13 times):
- `status_server.py:52` imports `SESSION_CONFIG_KEYS` from `monitor_core`,
  which the working tree does not define yet. As a result
  `test_monitor_status_server.py` errors at collection, and the 7
  `test_monitor_status_server_live.py` cases fail;
- `test_no_zero_collection` (2) and `test_collection_parity` (1) report that
  same module;
- `test_metadata_writer_inventory` reports `status_server.py` as an
  unclassified writer.

None of the failures involve `minimonitor_app.py` or a t2183 test.

### Step 8 — after measurement (2026-11-04 19:49–20:18, same harness, load 5.7–8.5)

Edited `minimonitor_app.py` (sha256 prefix `5544543eb9be`, equal to the
accepted chain value, for every run) at HEAD 52b8b65dc. All 10 runs passed
PRECHECK and stayed alive.

**Steady per-instance CPU, % of one core** (mean of the two 60 s windows; the
raw windows are in brackets):

| N | active before → after | idle before → after |
|---|---|---|
| 1 | 0.26 [0.25/0.27] → 0.18 [0.18/0.18] (−31 %) | 0.25 [0.27/0.23] → 0.18 [0.18/0.18] (−28 %) |
| 4 | 0.83 [0.82/0.83] → 0.28 [0.30/0.25] (−67 %) | 0.83 [0.83/0.83] → 0.40 [0.37/0.42] (−52 %) |
| 12 | 1.49 [1.55/1.43] → 0.49 [0.50/0.48] (−67 %) | 1.55 [1.60/1.50] → 0.79 [0.82/0.75] (−49 %) |

**Profiles after** (100 Hz `--gil`, 120 s including startup; % of GIL-held
non-idle samples, with the before value in brackets):

| run | samples | coverage | producer | app | textual.render | textual.dispatch | render+dispatch samples |
|---|---|---|---|---|---|---|---|
| active N=1 | 55 [52] | 48 % (0.55 s / 1.15 s) | 9.1 [15.4] | 25.5 [21.2] | 10.9 [11.5] | 40.0 [42.3] | 28 [28] |
| active N=4 | 64 [133] | 52 % (0.64 s / 1.22 s) | 23.4 [15.0] | 23.4 [15.0] | 12.5 [33.1] | 35.9 [36.1] | 31 [92] |
| active N=12 | 80 [219] | 51 % (0.80 s / 1.56 s) | 40.0 [17.8] | 23.8 [13.7] | 12.5 [38.4] | 18.8 [28.8] | 25 [147] |
| idle N=12 | 137 [174] | 71 % (1.37 s / 1.93 s) | 27.7 [17.8] | 20.4 [13.2] | 27.7 [40.2] | 21.9 [28.2] | 68 [119] |

**Reading.**
- At N = 12 active, Textual render+dispatch fell from 147 to 25 GIL-held
  samples (−83 %).
- Per-instance CPU growth with N mostly flattens for active agents: +0.10 %
  of a core from N=1 to N=12, against +1.23 % before. The producer
  (`tickcount`: 0.37 % of a core at N = 12, unchanged) is now the largest
  bucket.
- The idle worst case still roughly halves. There, every card's
  `IDLE <n>s` counter changes on every tick, so every card is updated in
  place, but with `layout=False` and no remount.
- Coverage is lower after the change (≈50 %) because GIL-released syscall
  time is a larger share of a smaller total. This is the caveat t2034_1
  stated, so the shares above are indicative only.

**Confounds, stated rather than corrected:**
- Host load was lower during the after series (5.7–8.5 against 8.4–14.2).
- The producer cost (`tickcount` precheck, in % of a core) was comparable
  between the two series: active N=12 0.385 → 0.369, idle N=12 0.400 →
  0.356. So the machine did similar producer work per tick, but this does not
  remove the load difference.
- One host, one evening. The figures bound what was measured here and are not
  a fleet-wide claim.

## Final Implementation Notes

- **Actual work done:** as planned.
  - Each minimonitor tick builds `_ListEntry`s, and
    `_plan_in_place_list_update` chooses nothing, in-place updates of changed
    cards, or the full rebuild.
  - `layout=False` is used only when `card_height_stable` proves the height
    cannot change: same newline count, and both texts fit the card's actual
    content width.
  - Scroll capture/restore runs only when geometry can change.
  - Focus is restored from `_focused_pane_id` read after every await, never
    from a top-of-tick snapshot.
  - The session bar is re-rendered only when its text changes.
  - Measured result at N = 12: per-instance CPU −67 % (active) and −49 %
    (idle, the worst case). Textual render+dispatch samples 147 → 25
    (active). Tables are in the Step 8 log above.
- **Deviations from plan:**
  1. The planner diffs against `card.content` (`Static.content`) instead of
     a recorded texts list. The headless `_regrow_cards` helper and the live
     harness update cards directly, so a separate record would go stale.
  2. There is no `_focus_is_on` helper: the in-place branch restores only when
     `self.focused is None`, which is what the revised plan's code block says.
  3. The live-test review fix: `test_3c` and `test_4b` count only
     `inplace_layout` ticks. Checked against synthetic traces.
- **Issues encountered:**
  - t2175_5 held uncommitted hunks in `minimonitor_app.py`. All other work was
    done first, and the file was edited only after the handover was verified
    (clean vs HEAD, its hunks in HEAD 52b8b65dc), with every write under a
    sha256 chain.
  - Three first-draft fixture faults in the new module (divider offset,
    `_multi_session` default plus the single-session projection, `id()` reuse
    after a rebuild) were fixed in the fixtures.
  - The full suite is red only from t2037_1's untracked `status_server.py`
    (missing `SESSION_CONFIG_KEYS`).
- **Key decisions:**
  - Diff on the rendered text, not on protocol deltas. This is
    source-agnostic, so t2037_3's `MonitorClient` needs no extra plumbing.
  - The `_IN_PLACE_LIST_UPDATES` class seam pins the t1539/t1653 headless
    modules to the full path. The live harness runs the production path with
    its own anchor-removal control, and keeps the historical control on the
    full path.
  - This task adopts the "current intent at restore time" half of t2201's fix
    direction. The deferred `card.focus()` race, a click between
    `remove_children` and `mount_all`, and the card-0 cases stay with t2201.
- **Upstream defects identified:** None.
