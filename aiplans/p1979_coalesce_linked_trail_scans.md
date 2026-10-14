---
Task: t1979_coalesce_linked_trail_scans.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1979 — Coalesce overlapping linked-trail scans

## Context

Review finding on t1957_4. Every accepted `L` press in By-Trail (board) and
`ait trails` starts a new `_trail_link_worker`
(`.aitask-scripts/board/board_trail_screen.py`, `action_trail_linked`). The
supersession stamp `_trail_link_gen` throws away an obsolete result only after
its `scan_linked_trails` has finished. Each scan runs up to 4 export
subprocesses (`lib/trail_links.py`), so N overlapping presses mean up to 4·N
exports, and only the newest answer can ever be shown.

Goal: bound the work and keep newest-request-wins exactly as it is. The newest
press's result is the one that shows. Tab switch, tab close, activation,
leaving By-Trail and a content change still drop a result.

Chosen option: **Coalesce** (at most one scan in flight plus one pending).
The other option, a semaphore in `trail_links`, would still queue N scans and
run every one of them in turn. Coalescing runs at most two.

## Implementation (single file: `.aitask-scripts/board/board_trail_screen.py`)

Both hosts share the mixin, so this one change covers the board and
`ait trails`. Neither host overrides these methods; `trails_app.py` and
`aitask_board.py` only gate `check_action`.

1. **State** (in the `# --- Linked trails (t1957_4) ---` init block, next to
   `_trail_link_gen`):
   ```python
   # At most one linked-trail scan runs at a time (t1979): a press while one
   # is in flight only records the newest request — its OWN snapshot — and
   # it runs when the in-flight scan lands. Held/repeated `L` presses would
   # otherwise multiply the export subprocesses for a result that is
   # superseded anyway.
   self._trail_link_running = False
   self._trail_link_pending: tuple | None = None
   ```

2. **`action_trail_linked`**: keep every guard, the snapshot
   (`origin`, `copy.deepcopy(origin.doc)`, `origin.error`), the gen bump and the
   "Searching…" notice as they are. Then:
   ```python
   if self._trail_link_running:
       self._trail_link_pending = (gen, origin, source)   # newest wins
       return
   self._start_trail_link_scan(gen, origin, source)
   ```
   Update the docstring with one sentence about coalescing.

3. **New `_start_trail_link_scan(gen, origin, source)`**: sets
   `_trail_link_running = True` and calls `_trail_link_worker(...)`.

4. **`_on_trail_links`**: the first thing it does, before any guard, is release
   the slot and start the pending request:
   ```python
   self._trail_link_running = False
   pending, self._trail_link_pending = self._trail_link_pending, None
   if pending is not None and pending[0] == self._trail_link_gen:
       self._start_trail_link_scan(*pending)
   ```
   - The pending request is checked against the current gen when it is about to
     start. Every way of retiring a request bumps `_trail_link_gen`: a newer
     press, `_drop_trail_link_scan` (tab switch, close, activation) and
     `_supersede_trail_workers` (entering or leaving By-Trail). So a pending
     request retired by any of them is dropped here, and no scan starts for it.
   - The landed result then goes through the existing guards. Its gen is older
     than the pending press's gen, so it is dropped without a notice, exactly as
     today.
   - A content change after the newest press is still caught when the pending
     scan lands (`origin.doc != source[0]` → "changed during" notice). A change
     *between* presses is not reported, because the pending request carries the
     latest press's snapshot.

**How the slot is always released:** `_trail_link_worker` calls
`_on_trail_links` from its `finally` block. That covers both a successful scan
and an exception, and the release is the first statement of `_on_trail_links`,
before any early return. So `_trail_link_running` cannot get stuck. A test pins
the exception path.

## Tests

Order: write the tests first and run them against the unchanged code (they must
fail there: 2+ calls, no pending). Then implement and run them again. Do not
use git stash or restore.

`tests/test_board_bytrail_view.py`, `LinkedTrailsTests`:
- `_drain`: change it to `for _ in range(3): await app.workers.wait_for_complete();
  await pilot.pause()`. A pending scan starts from the UI callback after the
  first worker completes, so a single wait can return while that second worker
  is still running.
- `test_presses_during_a_scan_coalesce_into_one_pending_scan`: gate 2 results
  (OLD, NEW). Press L on doc v1. Set `app._trail_doc` to v2 and press L, then to
  v3 and press L. Assert `len(gated.calls) == 1`. Release gate 0 and wait until
  there are 2 calls. Assert `calls[1][0] == v3` and that it is not the live
  object. Release, then check that the modal lists only NEW, the total is 2
  calls, there is no "changed during" note and `_trail_link_running` is False.
- `test_leaving_bytrail_drops_the_pending_scan`: press twice while gated, then
  `action_view_all`. Release. Expect 1 call, no modal and no notes.
- `test_a_failed_scan_still_runs_the_pending_one`: gate 0 raises
  `RuntimeError`. Press twice and release. The second scan runs, the NEW modal
  shows, the superseded failure is not reported, and the slot is released.

`tests/test_trails_app.py`, `LinkedTrailsTabTests`:
- Rewrite `test_two_searches_show_only_the_newest_in_either_order` as
  `test_overlapping_searches_coalesce_and_show_only_the_newest`. The old test
  asserted 2 concurrent calls, which is the behaviour being removed, and
  "newest lands first" can no longer happen. New test: three presses, 1 call.
  Release the first and wait for call 2. Release that one. Only NEW shows, total
  2 calls.
- `_tab_case(move, presses=1)`. Add
  `test_switching_tabs_drops_a_pending_search` and
  `test_closing_the_origin_tab_drops_a_pending_search` with `presses=3`, keeping
  the existing `len(gated.calls) == 1` / no modal / no notes asserts.
- `test_a_search_on_the_new_tab_replaces_the_retired_pending_one`: tests that
  after a request is retired, a request from a different origin can take its
  place. This added case comes from review. Gate 2 results (A-result "OLD trail",
  B-result "NEW trail").
  Press L twice on A, so 1 call is made and one request is pending. Then
  `_switch_trail_session(HANDLE_B)` and press L on B. Assert `len(gated.calls)
  == 1`, that the scan slot is still taken, and that the pending request's
  origin is B's session. Release A's gate and wait for call 2. Assert that
  `calls[1][0]` equals B's doc and is not the same object as it (B's snapshot,
  not A's). Release, then check that the only modal lists "NEW trail", the total
  is exactly 2 calls (no stale A scan started), there is no "changed during"
  note and the scan slot is free again.
- `_revision_case(change, *, expect_modal, press_after_change=False,
  presses=1)`, using the real `_on_trail_reload` path:
  - `test_a_reload_between_presses_scans_the_newest_snapshot`: press, apply a
    changed-members reload, press again, release. The modal shows,
    `calls[1][0]` equals the new doc, and there is no "changed during" note.
  - `test_a_reload_after_a_pending_press_drops_the_search`: press twice, then
    apply a changed-members reload, release. Expect the "changed during" notice
    and no modal.
  - Gates sized to the number of expected calls.

## Verification

- `python -m pytest tests/test_board_bytrail_view.py -k LinkedTrails` and
  `tests/test_trails_app.py -k LinkedTrailsTabTests` (fail before the fix, pass
  after).
- `bash tests/run_all_python_tests.sh`, reading only the last verdict line.

## Step 9

Post-implementation: commit the code and tests (`performance: … (t1979)`),
commit the plan through `./ait git`, then archive per task-workflow Step 9.

## Risk

### Code-health risk: low
- `_trail_link_running` could get stuck True if `_on_trail_links` were not
  reached, and then every later `L` would only queue and never scan.
  severity: low. The release is the first statement of the callback, and that
  callback is invoked from the worker's `finally`. → mitigation: none (covered
  by `test_a_failed_scan_still_runs_the_pending_one` in the plan)
- Changing the shared board `_drain` helper affects 23 call sites.
  severity: low. The new version is strictly more thorough (it only waits
  longer). → mitigation: none (full suite run)

### Goal-achievement risk: low
- A pending scan could use a stale snapshot. severity: low. The pending tuple
  is built at the latest press. → mitigation: none (covered by the
  snapshot-identity asserts in both test files)
