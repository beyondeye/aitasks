---
Task: t2270_fix_frozenagent_mark_move_pilot_press_budget.md
Base branch: main
Output branch: main
---

# t2270 — time the mark-move property, not the pilot (+ two vacuous siblings)

## Context

`tests/test_frozenagent_app.py::LargeCaptureTests::test_selection_and_search_do_not_re_render`
times ten `pilot.press("shift+down")` calls plus `pilot.pause()` against a 2.0 s
budget. In Textual 8.2.7 each `pilot.press` runs `wait_for_idle(0)` twice (each up to
1 s on a busy process). So the budget mostly measures the harness, not the
incremental repaint it guards (same mechanism as t2267 / t1660).

**Reproduced during planning (scratch probes, nothing committed):**

| run | the test as it stands | new measurement (send_message + observed effect incl. paint) |
|---|---|---|
| fixed code | pass (~1.9 s wall) | 0.19 s |
| `textual._wait.SLEEP_IDLE = -1` (never idle) | **FAIL: 21.1 s not less than 2.0** | 0.23 s |
| mutant: full `_render_log` per mark move | — | 6.3–7.9 s |

**Additional finding (folded in at the user's choice).** The capture mounts scrolled
to the bottom. `_extend_selection` snaps the cursor into view (line 19999), and
`shift+down` clamps there. So after the first press, the remaining presses are
no-ops: the marked set is unchanged and `_repaint_marks` returns early. That affects
three tests in the class:
- the timed test really times only one repaint;
- `test_a_match_moving_inside_the_selection_still_repaints` **passes against the
  exact set-only short-circuit it names**. Mutant: `key = (frozenset(marked), None)`.
  Its matches (lines 2, 4) are not inside the {19999} selection, so the set changes
  and the short-circuit never fires;
- `test_marks_are_lifted_cleanly` **passes against a no-restore mutant**. It checks
  lines 0–5, which are never marked, and it compares only `.text`, which a mark
  does not change.

Only `tests/test_frozenagent_app.py` changes. No production code changes.

## Implementation (all in `tests/test_frozenagent_app.py`, class `LargeCaptureTests`)

1. **Add three helpers to `LargeCaptureTests`.** Function-level imports, matching
   the file's existing style: `time`, `textual.events`, `CaptureLog`.
   - `_send_key(app, key)`: build `events.Key(key, key if len(key) == 1 else None)`,
     call `set_sender(app)`, then `app._driver.send_message(event)`. This is the
     exact call `App._press_keys` makes, minus the idle sampling. Same technique as
     `key_latency` in `tests/test_scratchpad_app.py:298` and `_press_and_observe`
     in `tests/test_minimonitor_startup_input_latency.py:205`. The docstring cites
     t1660 / t2267 and why `pilot.press` is not used.
   - `async _await_painted(app, done, what, timeout=10.0)`: poll with
     `asyncio.sleep(0.005)` until `done()` holds **and** `log._line_cache` is
     non-empty. Use `self.fail(f"timed out waiting: {what}")` past the deadline
     (liveness only, never a budget). Why the cache condition: `_repaint_marks`
     clears `_line_cache` in the same synchronous handler that makes `done()`
     true, and only a compositor paint fills it again. So the timed span covers
     painting the visible rows, as `pilot.press` used to, without the idle waits.
   - `async _move_marks(app, moves)`: for `i` in `1..moves`, call `_send_key`
     with `"shift+down"`, then `_await_painted` on
     `app._sel_end == i and app._marked == set(range(0, i + 1))`. `_marked` is
     the set that is actually painted.
   - Also a small `_count_renders(app)` that installs the existing counting
     wrapper around `app._render_log` and returns the counter dict. This lifts
     the wrapper out of the timed test so the control below can reuse it.

2. **Rewrite `test_selection_and_search_do_not_re_render`:**
   - `await pilot.pause()`, then `app.action_scroll_top()` and
     `await pilot.pause()`, all **outside** the timed span. Starting at line 0
     means each of the ten moves grows the range by one line and causes a real
     repaint. Add a comment explaining that from the bottom the moves clamp and
     are no-ops.
   - `renders = self._count_renders(app)`.
   - Start timing with `t0 = time.perf_counter()`, then:
     - `await self._move_marks(app, 10)`;
     - set `_search_term = "line 19000"` and call `action_search_next()`;
     - `await self._await_painted(app, lambda: app._match_line == 19000 and 19000 in app._marked, "search hit painted")`;
     - `elapsed = time.perf_counter() - t0`.
   - Asserts: `renders["n"] == 0` (unchanged), and `elapsed < 2.0`. The 2.0 s
     budget stays, now about 10× above the measured property (~0.2 s) and about
     3× below the regression (≥6.3 s). Update the comment with those numbers and
     reword the message to "10 mark moves and a search …".

3. **Add the counted mutation control** `test_control_re_render_per_move_is_counted`:
   - Same setup (scroll to the top, `_count_renders`).
   - Wrap the instance's `_extend_selection` so it calls the real method and then
     `app._render_log()`, the counted instance attribute. That is exactly the
     t1705_6 regression the class docstring describes.
   - `await self._move_marks(app, 2)`. Two moves keep the control at ~1.5 s,
     since one full re-render costs ~0.7 s.
   - Assert `renders["n"] == 2`. This proves the timing-free render-count guard
     sees the regression the budget guards.
   - The timed side's teeth are verified out of band, not in the suite (see
     Verification). An in-suite "mutant is slower than X" assertion would depend
     on machine speed.

4. **Fix `test_a_match_moving_inside_the_selection_still_repaints`:**
   - After the first `pilot.pause()`, call `app.action_scroll_top()` and
     `await pilot.pause()`. Then the six `shift+down` presses select lines 0–6,
     and both matches ("line 2 ", "line 4 ") land **inside** the selection, as
     the test name says.
   - Keep `pilot.press` here: the test is not timed.
   - Add a precondition assert that both match lines are within
     `app._selection_bounds()`. Without it, the test could silently go vacuous
     again.

5. **Fix `test_marks_are_lifted_cleanly`:**
   - Scroll to the top first, the same way. The three presses then mark lines
     0–3 inside the compared window 0–5.
   - Compare `(seg.text, str(seg.style))` per segment, as `style_of` does, not
     only `.text`, because a mark changes styles, not text.
   - Add a precondition assert that the marked lines' styles differ from
     `before` while marked. That shows the check can fail.

## Verification

- `~/.aitask/venv/bin/python -m pytest tests/test_frozenagent_app.py -q` (also
  `python -m unittest tests.test_frozenagent_app`) — all pass.
- Never-idle injection: run the timed test with `textual._wait.SLEEP_IDLE = -1`
  (scratch runner). It must pass. It failed at 21.1 s before.
- Timed mutant (scratch, out of band): full `_render_log` per mark move. The
  rewritten timed test must FAIL on the budget.
- Set-only mutant `key = (frozenset(marked), None)`: the match test must FAIL.
- No-restore mutant (`original = None`): the lifted-cleanly test must FAIL.
- Each mutant is applied in a scratch runner (monkeypatch / exec of patched
  source), never by editing the tracked file.
- Then Step 9 (Post-Implementation): commit, archive.

## Risk

### Code-health risk: low
- The helpers reach private Textual/RichLog internals (`App._driver.send_message`, `RichLog._line_cache`) that a Textual upgrade could rename. This is the same private surface the file and the t1660/t2267 helpers already use, so it is no new coupling · severity: low · → mitigation: none (existing pattern)

### Goal-achievement risk: low
- The paint-observation condition could be met by something other than the post-move paint and under-measure. This is bounded: the cache is cleared synchronously by the same handler that makes `done()` true, so a non-empty cache afterwards implies a later paint. The timed mutant's ≥6 s result confirms the measurement still sees re-render cost · severity: low · → mitigation: none (addressed in plan)
- The timed budget's teeth are proven only out of band, not in the suite · severity: low · → mitigation: none (the counted control is in the suite; the timed mutant run is recorded in Final Implementation Notes)
