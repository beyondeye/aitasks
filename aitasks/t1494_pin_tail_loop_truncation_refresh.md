---
priority: low
effort: low
depends: []
issue_type: test
status: Ready
labels: [tui, ui]
gates: [risk_evaluated]
anchor: 1449
followup_kind: risk_mitigation
created_at: 2026-08-12 11:14
updated_at: 2026-08-12 11:14
---

## Origin

Risk-mitigation ("after") follow-up for t1489, created at Step 8d after implementation landed.

## Risk addressed

Code-health risk (severity: low), from `aiplans/archived/p1489_logview_stale_header_on_quiet_log.md`:

> The `_reload_from_start` refresh is only reachable in production through
> `_tail_loop`'s 0.2 s polling thread; test 3 drives `_reload_from_start`
> directly, so the thread wiring that calls it stays unpinned.

t1489 made every mutator of header-visible state call `_refresh_header()`
itself, including `_reload_from_start` — the method `_tail_loop` invokes via
`call_from_thread` once it sees the log file shrink. The test that covers it
(`LogViewQuietLogHeaderTests.test_a_truncated_log_updates_the_size_indicator`
in `tests/test_textual_markup_structure.py`) deliberately mounts with
`tail=False` and calls `_reload_from_start()` directly, so the polling thread
cannot race the manual rewind. That pins the *method* but not the *wiring*: if
the `size < self._last_pos` branch in `_tail_loop` were changed to call
something else, or the `call_from_thread` hop were dropped, every existing test
would still pass while a truncated live log kept a stale `[size: N]` on screen.

## Goal

Add one test that drives the real tail loop end to end:

- Seed a log file with bytes and mount `LogViewApp(path, tail=True)` so
  `on_mount` starts the polling thread.
- Assert the header shows the non-zero `[size: N]`.
- Truncate the file to zero bytes (`path.write_bytes(b"")`) — **without** any
  keypress and without touching `_last_pos` by hand.
- Wait out the poll (`_tail_loop` sleeps 0.2 s per iteration) and assert the
  header falls back to `[size: 0]`.

Notes for the implementer:

- Assert on rendered plain text via the module's existing `_rendered()` helper
  (`Content.from_markup(str(widget.content)).plain`), never `render().spans` —
  a span happily holds an unresolved tag, which is how this whole defect class
  hides. See the module docstring and t1453.
- Prefer polling for the expected value with a bounded deadline over a single
  fixed `sleep`, so the test is not flaky on a loaded box — but keep the total
  bound small (~2 s) and fail with the actual header text in the message.
- Negative control before landing it: revert `_reload_from_start`'s
  `self._refresh_header()` line and confirm the new test fails with a stale
  `[size: N]`; a passing negative control means the test is not measuring the
  wiring.
- Real-thread timing tests are the flakiest kind in this suite (see the serial
  carve-out for `tests/test_board_header_row_live.py` in CLAUDE.md). If the
  test proves unstable under the parallel lane, that is a signal about
  placement, not a reason to weaken the assertion.
