---
Task: t1988_isolate_trail_jump_workers_from_exclusive_cancel.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1988 — Isolate the trail screen's thread workers from exclusive default-group cancels

## Context

t1979 found that Textual's `exclusive=True` workers in the **default** group
(`aitask_board.py` `_run_sync`, which the auto-refresh timer also starts, plus
the mixin's own `run_dialog_command`) call `cancel_group(node, "default")`.
Textual's `Worker.cancel()` cancels the asyncio task. If that happens before the
task's first step, `_run` never calls `run_in_executor`, so the thread body
never runs and its `finally` never runs either. Once the body is running, a
cancel can't stop it. I checked this in the installed Textual
(`worker.py` `_start`/`_run`/`cancel`, `worker_manager.py` `add_worker`).
t1979 fixed the linked-trail scan by putting it in `group="trail_link"`.

The jump workers rely on their callbacks the same way. `_on_linked_trail_chosen`
sets `_trail_jump_busy`, and only the UI callbacks of
`_trail_jump_prepare_worker` / `_trail_jump_finish_worker` clear it. One
exclusive default-group worker in the same tick strands the flag, and every
later linked-trail jump is refused with "A jump is already in progress".

### Audit of the other default-group thread workers in `board_trail_screen.py`

Each of these sets state before it starts and resets it only in its callback.
None of the bodies has a `finally`, so a cancel before start skips the callback:

| worker | state set before start | if cancelled before start |
|---|---|---|
| `_trail_baseline_worker` (~1843) | `_trail_launch_pending = True` | **Permanent latch.** The confirmed agent launch never happens, and `R` stays disabled (`check_action` on both the board and `trails_app.py:804`) until restart |
| `_trail_watch_worker` (~1703) | `_trail_watch_busy = True` | **Latched until the tick ceiling** (90 × 20s). Every tick returns early, so the finished refresh is never picked up |
| `_trail_reload_worker` (~1625) | `reload_gen`/`drift_gen` bumped, `drift = None` | Content not reloaded and drift never restarted. The subtitle shows "⟳ checking freshness…" until the next reload |
| `_trail_drift_worker` (~1573) | `drift = None` | Same as reload: "checking freshness…" until the next reload |
| `_trail_xdep_worker` (~1544) | `xdep_inflight = refs` | Refs stay "being checked" until the next probe |
| `_trail_discovery_worker` (~1314) | pushes a `LoadingOverlay` | The overlay is never popped. Probably unreachable today: the overlay is pushed first, in the same handler, and the auto-refresh tick is modal-gated. It costs one line to remove the question anyway |

Fix: one change for all of them. Each worker gets a dedicated non-default group.
None of them is exclusive, and no code calls `cancel_group` on them (I grepped).
The only change in behaviour is that an exclusive default-group worker can no
longer cancel them before they start. That cancel was never intended (t1979's
finding). `run_dialog_command` stays `exclusive=True` in the default group:
it is the canceller, and moving it would change what it cancels (memory: t1929).

Out of scope, follow-up: `aitask_board.py` has its own default-group thread
workers (`_do_archive`, `_do_delete`, `_do_rename_task`, `_do_git_commit_tasks`).
The same mechanism could silently drop a confirmed archive, delete, rename or
commit. I haven't reproduced it, and no task in the backlog covers it. I'll offer
it as a follow-up task in Step 8 rather than widen this bug fix.

## Implementation

### 1. `.aitask-scripts/board/board_trail_screen.py`: named groups

- Generalise the comment above `_trail_link_worker` (≈ line 1098) so it states
  the rule once for the mixin. Every non-exclusive worker here runs in its own
  group. The reason: `exclusive` default-group workers (`_run_sync`,
  `run_dialog_command`) cancel every worker in that group, and a worker cancelled
  before it starts never runs its body or its `finally`. Keep the t1979
  reference and add t1988.
- Decorator changes, each with a one-line comment naming the state it would
  strand:
  - `_trail_jump_prepare_worker`, `_trail_jump_finish_worker` →
    `@work(thread=True, group="trail_jump")`. The two phases are sequential
    under `_trail_jump_busy`, so they can share a group. Comment: "a cancel
    before start would leave `_trail_jump_busy` set".
  - `_trail_baseline_worker` → `group="trail_launch"` (`_trail_launch_pending`)
  - `_trail_watch_worker` → `group="trail_watch"` (`_trail_watch_busy`)
  - `_trail_reload_worker` → `group="trail_reload"`
  - `_trail_drift_worker` → `group="trail_drift"`
  - `_trail_xdep_worker` → `group="trail_xdep"` (`xdep_inflight`)
  - `_trail_discovery_worker` → `group="trail_discovery"` (its overlay)

### 2. `tests/test_board_bytrail_view.py`: regression tests

These follow the pattern of t1979's
`test_an_exclusive_default_group_worker_cannot_strand_the_scan` (≈ line 5558):
start the worker, then `app.run_worker(lambda: None, thread=True,
exclusive=True)` in the **same tick**.

- **`LinkedTrailsTests.test_an_exclusive_default_group_worker_cannot_strand_the_jump`**
  has one `subTest` per phase, using `_jump_patches`, `NoteRecorder` and
  `_drain`:
  - *prepare*: `prepare` returns `TrailJump(link, session="ysess",
    launch=True)` (nothing to confirm) and `finish` records its argument. Call
    `app._on_linked_trail_chosen(link)` followed directly by the exclusive
    worker, then `_drain`. Assert `finished == [jump]`, that `_trail_jump_busy`
    is False, and that there is no "already in progress" notice.
  - *finish*: set `app._trail_jump_busy = True`, call
    `app._on_trail_jump_prepared(jump)` (no confirm, so it starts the finish
    worker synchronously) followed directly by the exclusive worker, then
    `_drain`. Assert `finished == [jump]` and that `_trail_jump_busy` is False.
- **`ThreadWorkerTests.test_an_exclusive_default_group_worker_cannot_strand_the_watch`**:
  enter synthetic By-Trail, stub `_reload_active_trail`, patch
  `board_trail_screen._trail_versions` to return `["v2"]`, then
  `_install_trail_watch("art:trail-test", ["v1"])`. Call `_trail_watch_tick()`
  followed directly by the exclusive worker. Wait (the existing `_wait`) for the
  reload. Assert it happened and that `_trail_watch_busy` is False.
- **`ThreadWorkerTests.test_an_exclusive_default_group_worker_cannot_strand_the_launch`**:
  stub `_reload_active_trail` and patch `_trail_versions` to return `["v1"]`.
  Call `app._with_trail_baseline("art:trail-test", lambda b:
  app._finish_trail_launch(b, "art:trail-test", lambda: launches.append(b)))`
  followed directly by the exclusive worker, then wait. Assert
  `launches == [["v1"]]` and that `_trail_launch_pending` is False. Then
  `_stop_trail_watch()` so the installed timer doesn't outlive the test.
- **New `TrailWorkerGroupTests(unittest.TestCase)`**, a structural guard for
  the reload, drift, xdep and discovery workers and any future worker. It parses
  `board_trail_screen.py` with `ast`. For every function decorated with
  `work(...)` (or a bare `@work`) that is **not** `exclusive=True`, it asserts a
  string `group=` keyword other than `"default"`, and the failure message names
  the offending functions. A vacuity check asserts that the scanned set contains
  all nine known worker names (`_trail_link_worker`, the two jump workers,
  discovery, xdep, drift, reload, watch, baseline), so a decorator-form change
  can't make the scan pass with nothing in it.

### 3. Red proofs (isolated mutants, never in the shared tree)

Extract `git archive HEAD` of `.aitask-scripts/` + `tests/` into the scratchpad
and overlay the two edited files. In that copy, apply one mutation at a time:
- drop `group=` from the prepare worker: the *prepare* subtest must fail
  (busy stays True, nothing finished)
- drop it from the finish worker: the *finish* subtest must fail
- drop it from the watch worker: the watch test must fail
- drop it from the baseline worker: the launch test must fail
- drop it from the reload worker: the AST guard must fail and name
  `_trail_reload_worker`

Each mutant should fail **only** its own test. Record the outcomes in the Final
Implementation Notes.

## Verification

- `python3 -m pytest tests/test_board_bytrail_view.py -q`, or
  `bash tests/run_all_python_tests.sh --test-dir …` if needed. The whole file
  must pass, including t1979's scan test and the existing jump, watch and
  launch tests.
- `python3 -m pytest tests/test_trails_app.py -q`. `TrailsApp` uses the same
  mixin, so its linked-trail and launch tests must stay green.
- Red proofs as in §3.

## Step 9 (Post-Implementation)

Current-branch mode: commit code (`bug: … (t1988)`), commit plan via
`aitask_task_commit.sh`, archive via the Step 9 flow.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** As planned. `board_trail_screen.py`: the eight
  default-group thread workers got dedicated groups — `trail_jump` (prepare +
  finish), `trail_discovery`, `trail_xdep`, `trail_drift`, `trail_reload`,
  `trail_watch`, `trail_launch` (baseline). The `_trail_link_worker` comment now
  states the rule once for the mixin; each site has a one-line comment naming
  the state a pre-start cancel would strand. `run_dialog_command` stays
  `exclusive=True` in the default group (the canceller). Tests in
  `tests/test_board_bytrail_view.py`: `LinkedTrailsTests.test_an_exclusive_default_group_worker_cannot_strand_the_jump`
  (subTests `prepare` / `finish`), `ThreadWorkerTests.test_an_exclusive_default_group_worker_cannot_strand_the_watch`,
  `ThreadWorkerTests.test_an_exclusive_default_group_worker_cannot_strand_the_launch`,
  and the AST guard `TrailWorkerGroupTests.test_non_exclusive_workers_run_outside_the_default_group`
  (with a vacuity check over the nine known worker names).
- **Deviations from plan:** None.
- **Issues encountered:** The jump mutants surface as an ERROR, not a FAIL:
  `_drain`'s `app.workers.wait_for_complete()` raises
  `textual.worker.WorkerCancelled` for the cancelled victim before the
  `_trail_jump_busy` assertion is reached. That signal is the defect itself
  (only the victim worker is cancelled — the exclusive `lambda: None` is not),
  so the shared `_drain` helper was left unchanged. A first unittest-based
  mutant run grepped only `^FAIL:` and so looked green for the jump mutants;
  re-checked with `ERROR:` included (below).
- **Red proofs** (isolated copy: `git archive HEAD .aitask-scripts tests seed`
  extracted to the scratchpad, the two edited files overlaid, one mutant at a
  time = drop `group=` from one decorator; the shared tree was never mutated,
  and the copy was byte-compared back to the working tree afterwards):
  - prepare worker → `ERROR: …cannot_strand_the_jump (phase='prepare')`
    `WorkerCancelled`; the `finish` subtest passes; AST guard names
    `['_trail_jump_prepare_worker']`.
  - finish worker → `ERROR: …cannot_strand_the_jump (phase='finish')`
    `WorkerCancelled`; the `prepare` subtest passes; AST guard names
    `['_trail_jump_finish_worker']`.
  - watch worker → `FAIL …cannot_strand_the_watch` — `AssertionError: [] is not
    true : the poll never reported`; AST guard fails.
  - baseline worker → `FAIL …cannot_strand_the_launch` — `AssertionError: [] is
    not true : the confirmed launch never ran`; AST guard fails.
  - reload worker → only the AST guard fails, naming `['_trail_reload_worker']`.
  - vacuity: `@work` → `@textual_work` on the xdep worker → AST guard fails with
    `scan missed workers: {'_trail_xdep_worker'}`.
  - restored copy: 5 passed.
- **Verification:** `pytest tests/test_board_bytrail_view.py tests/test_trails_app.py -n 4 --dist loadfile`
  → `287 passed in 156.11s`, exit 0.
- **Key decisions:** Per-family group names (not one shared `trail` group), so a
  future exclusive worker added to one family cannot cancel another. The four
  display-only workers (reload, drift, xdep, discovery) are pinned by the AST
  guard rather than four more real-App tests; the three latching families get
  behavioural tests.
- **Upstream defects identified:**
  - `.aitask-scripts/board/aitask_board.py:6600,6756,6920,6971 — _do_archive / _do_delete / _do_rename_task / _do_git_commit_tasks run as @work(thread=True) in Textual's default group; an exclusive default-group worker (_run_sync from the auto-refresh timer, run_dialog_command, run_aitask_pick, run_codeagent_operation) started before one of them begins cancels it, and the confirmed archive/delete/rename/commit silently never runs (same mechanism as t1979/t1988; not reproduced)`
