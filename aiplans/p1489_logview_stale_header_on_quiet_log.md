---
Task: t1489_logview_stale_header_on_quiet_log.md
Worktree: . (current-branch mode — no worktree)
Branch: main (current branch)
Base branch: main
Output branch: main
---

# t1489 — logview header goes stale on a quiet log

## Context

`ait`'s log viewer (`.aitask-scripts/logview/logview_app.py`) draws a one-line
status header: `File: … [size: N] [live|paused|static] [raw]`. Two of its three
state toggles own their redraw; one does not.

`action_toggle_raw` flips `raw_mode`, rewinds `_last_pos`, clears the log and
then calls `_read_and_append` — and that is its *only* header redraw.
`_read_and_append` updates `#header-info` on its **last** statement, after two
early returns (`not self.log_path.exists()` and `not data`). So on an empty or
quiet log — a freshly spawned agent that has not printed yet, exactly when the
user is staring at the header — pressing `r` flips the mode but the `[raw]`
indicator never appears. It shows up only when some *unrelated* action happens
to redraw, e.g. `action_toggle_pause`, which updates `#header-info` itself.
Reproduced against the real app in the task file: `[raw]` first renders on the
**second** keypress.

The same shape affects the truncation path: `_tail_loop` resets
`_last_pos = 0` and calls `_reload_from_start`, which delegates to
`_read_and_append` — so a log truncated to zero bytes leaves a stale
`[size: N]` on screen.

This is the third defect found in this file's header, and the previous two
(t1486) were markup bugs. The fix here is refresh coupling: make every method
that mutates header-visible state own its redraw, through a single helper, so
the call sites cannot drift again. t1486's own header tests currently seed a
non-empty temp log **specifically to route around this bug** (documented in the
`LogViewHeaderTests` docstring); that workaround becomes unnecessary.

## Approach

Introduce one `_refresh_header()` helper and apply a single rule: **every method
that mutates header-visible state calls it.** Header-visible state is
`_last_pos`, `paused`, `raw_mode` (`log_path` and `tail` are constructor-only).

| mutator | today | after |
|---|---|---|
| `_read_and_append` (`_last_pos`) | inline `query_one(...).update(...)` on its last line | `self._refresh_header()` — same position |
| `action_toggle_pause` (`paused`) | inline `query_one(...).update(...)` | `self._refresh_header()` |
| `action_toggle_raw` (`raw_mode`, `_last_pos`) | **nothing** — delegates to `_read_and_append` | `self._refresh_header()` after the re-read |
| `_reload_from_start` (called after `_tail_loop` zeroes `_last_pos`) | **nothing** — delegates | `self._refresh_header()` after the re-read |

`_read_and_append`'s refresh deliberately stays where it is (after the early
returns): on both early-return paths `_last_pos` is unchanged, so there is
nothing to redraw. What changes is that no caller *relies* on it any more.

## Implementation

### 1. `.aitask-scripts/logview/logview_app.py`

Add the helper next to `_header_text` (around line 79):

```python
def _refresh_header(self) -> None:
    """Redraw the status header.

    Every method that mutates header-visible state (`_last_pos`, `paused`,
    `raw_mode`) calls this itself. Do NOT delegate the redraw to
    `_read_and_append`: its header update is the last statement, after two
    early returns, so a caller that relies on it silently keeps a stale
    header on an empty, quiet or missing log (t1489).
    """
    self.query_one("#header-info", Static).update(self._header_text())
```

Then:

- `_read_and_append` (line 117): replace the inline
  `self.query_one("#header-info", Static).update(self._header_text())` with
  `self._refresh_header()`.
- `_reload_from_start` (line 134-136): add `self._refresh_header()` after the
  `self._read_and_append()` call.
- `action_toggle_pause` (line 140): replace the inline update with
  `self._refresh_header()`.
- `action_toggle_raw` (line 142-146): add `self._refresh_header()` after the
  `self._read_and_append()` call.

Net: one new method, two call sites converted, two call sites added.

### 2. `tests/test_textual_markup_structure.py`

Add a new class after `LogViewHeaderTests`, pinning the empty-log path the
existing class routes around:

```python
class LogViewQuietLogHeaderTests(unittest.TestCase):
    """A state toggle must redraw the header even with nothing to read.

    The fixture is deliberately EMPTY — the inverse of ``LogViewHeaderTests``.
    ``action_toggle_raw`` used to delegate its redraw to ``_read_and_append``,
    which returns early on an empty (or missing) file, so ``[raw]`` stayed
    invisible until some unrelated action happened to refresh (t1489).
    """
```

Tests in it (all via `app.run_test(size=(120, 24))`, asserting on
`_rendered(app.query_one("#header-info"))` — the module's existing helper, which
reads rendered plain text, never `render().spans`):

1. `test_raw_round_trips_on_an_empty_log` — empty fixture file, `tail=True`;
   `await pilot.press("r")` / `pause()`, assert `app.raw_mode` is True **and**
   `[raw]` is in the rendered header (the task's exact reproduction — the
   assertion that must fail before the fix); then a **second** `r` press and
   assert `app.raw_mode` is False **and** `[raw]` is *absent*. The off-half is a
   completeness pin, not a control: pre-fix the header never showed `[raw]` in
   the first place, so on its own it would pass vacuously. Test 2 is the
   control for the off-transition.
2. `test_raw_clears_when_the_log_goes_quiet_while_raw_is_on` — **the
   discriminating off-transition case.** Seed the fixture with bytes and mount
   with `tail=True`; press `r` and assert `[raw]` renders (this passes even
   pre-fix — `action_toggle_raw` rewinds `_last_pos`, so the whole file is
   re-read and `_read_and_append` reaches its refresh). Then truncate the log to
   zero bytes and press `r` again: `_read_and_append` now returns at `not data`,
   so **pre-fix the header keeps advertising `[raw]` with raw mode off** —
   stale and actively wrong, not merely late. Assert `app.raw_mode` is False and
   `[raw]` is absent. (The 0.2 s poll thread may or may not fire between the two
   presses; it cannot change the outcome — pre-fix its `_reload_from_start` also
   delegates to the same early return, post-fix every path refreshes.)
3. `test_raw_shows_when_the_log_file_is_missing` — path that does not exist;
   press `r`, assert `raw_mode` and `[raw]` present; press `r` again, assert
   `raw_mode` False and `[raw]` absent. Covers `_read_and_append`'s *other*
   early return in both directions.
4. `test_a_truncated_log_updates_the_size_indicator` — write bytes, mount,
   assert the header shows the non-zero size; then truncate the file to zero,
   set `app._last_pos = 0` and call `app._reload_from_start()` (the same call
   `_tail_loop` makes via `call_from_thread`), `pause()`, assert the header
   shows `[size: 0]`.

Also **retarget the `LogViewHeaderTests` docstring**: its current text asserts
that an empty fixture *cannot* show `[raw]`, which stops being true here. Keep
the byte-holding fixture (that class exercises the data path and `[live]` /
`[size:`), but rewrite the paragraph to say the bug it worked around was fixed
in t1489 and point at `LogViewQuietLogHeaderTests` for the empty-log case.

## Verification

```bash
# negative control FIRST — on unmodified logview_app.py the new class must fail
# on BOTH directions of the toggle, and pass after the fix:
#   test_raw_round_trips_on_an_empty_log            raw_mode True, "[raw]" absent
#   test_raw_clears_when_the_log_goes_quiet_...     raw_mode False, "[raw]" still present
python3 tests/test_textual_markup_structure.py

# no regression in the wider Python suite (last line is the verdict)
bash tests/run_all_python_tests.sh
```

Manual (optional, confirms the user-visible symptom end to end):

```bash
: > /tmp/quiet.log
python3 .aitask-scripts/logview/logview_app.py --path /tmp/quiet.log
# press r once -> the header must read "... [size: 0] [live] [raw]"
```

Step 9 (Post-Implementation) then runs as usual: `ait gates run 1489`
(`risk_evaluated`), merge approval, archival.

## Risk

### Code-health risk: low
- The `_reload_from_start` refresh is only reachable in production through
  `_tail_loop`'s 0.2 s polling thread; test 3 drives `_reload_from_start`
  directly, so the thread wiring that calls it stays unpinned · severity: low ·
  → mitigation: t1494

### Goal-achievement risk: low
- None identified.

### Planned mitigations
- timing: after | name: pin_tail_loop_truncation_refresh | type: test | priority: low | effort: low | inline_risk: low | added_complexity: medium | addresses: code-health — `_reload_from_start`'s refresh is reached in production only via `_tail_loop`'s polling thread, which no test drives | desc: Pin the truncation refresh through the real tail loop — mount with tail=True, truncate the log to zero, wait out the 0.2 s poll, assert the header shows `[size: 0]` | created: t1494

## Final Implementation Notes

- **Actual work done:** Exactly the planned change, in two files.
  `.aitask-scripts/logview/logview_app.py` gained `_refresh_header()`;
  `_read_and_append` and `action_toggle_pause` were converted from their inline
  `query_one("#header-info", Static).update(...)` calls to it, and
  `action_toggle_raw` and `_reload_from_start` — which previously owned no
  redraw at all — now call it after their re-read.
  `tests/test_textual_markup_structure.py` gained `LogViewQuietLogHeaderTests`
  (empty-log fixture, 4 tests), and `LogViewHeaderTests`' docstring was
  retargeted: its "the fixture must hold bytes because `[raw]` cannot appear on
  an empty file" rationale describes the bug this task removed.

- **Deviations from plan:** None. Test 1 was named
  `test_raw_round_trips_on_an_empty_log` and test 3
  `test_raw_round_trips_when_the_log_file_is_missing` (the plan's prose already
  specified the round-trip shape for both).

- **Issues encountered:** None. The negative control was run by writing
  `git show HEAD:<path>` over the working copy — not `git checkout`, which
  touches the index and can race a concurrent session — with the fixed file
  saved aside and copied back afterwards.

- **Key decisions:**
  - *Where the fix lives.* `_read_and_append` keeps its refresh in place, after
    the early returns, rather than moving it onto every exit path: on both
    early returns `_last_pos` is unchanged, so there is genuinely nothing to
    redraw there. What changed is that no caller *relies* on it. The invariant
    is stated in `_refresh_header`'s docstring so the next call site cannot
    re-introduce the drift by delegating.
  - *`_reload_from_start` included.* Beyond the task's literal ask, but the same
    root cause: `_tail_loop` zeroes `_last_pos` on truncation, then delegates,
    so a log truncated to zero left a stale `[size: N]`. One line, same rule.
  - *Two tests for the toggle, only one of them a control.* The on-transition
    (`[raw]` never appears) is the reported symptom. The off-transition needs
    `[raw]` on screen *first* to have anything to go stale, so the control
    seeds bytes, presses `r` (the full re-read reaches the old refresh), then
    truncates before the second press.

- **Verification:**
  - Negative control against unmodified `HEAD` source: **all 4 new tests fail.**
    The on-transition: `AssertionError: '[raw]' not found in 'File: … [size: 0]
    [live]' : raw mode is on but the header never redrew`. The off-transition:
    `AssertionError: '[raw]' unexpectedly found in 'File: … [size: 21] [live]
    [raw]' : raw mode is off but the header still advertises it` — the old code
    does not merely lag, it asserts the opposite of the truth. The truncation
    test: `'[size: 0]' not found in '… [size: 21] [static]'`.
  - With the fix: `python3 tests/test_textual_markup_structure.py` → 13 tests,
    `OK`.
  - `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED
    (runner=pytest, exit=0)`.

- **Upstream defects identified:** None
