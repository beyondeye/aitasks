---
Task: t822_14_applink_push_scheduler_resilience.md
Parent Task: aitasks/t822_new_ait_bridge_tui.md
Sibling Tasks: aitasks/t822/t822_14_applink_push_scheduler_resilience.md
Archived Sibling Plans: aiplans/archived/p822/p822_8_applink_snapshot_push_loop.md, aiplans/archived/p822/p822_9_applink_delta_engine.md, aiplans/archived/p822/p822_10_applink_append_fastpath.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t822_14 — applink push scheduler resilience

## Context

`t822_8` landed Stage 1 of the applink binary data plane: a per-connection
`PushScheduler` (`.aitask-scripts/applink/pusher.py`) that captures tmux pane
content each tick and pushes `keyframe`/`delta`/`append`/`dim` frames over the
WebSocket, with a back-pressure high-water guard. During the t822_8 **plan
review**, two code paths were flagged as untested and unplanned:

1. **Back-pressure under load** — the `content_transport.md` §Back-pressure spec
   defines "coalesce queued deltas → drop cursor → skip tick" when a client is
   slow. The existing `_run_once` tests cover idle (zero bytes on no change) but
   not the high-water back-pressure path.
2. **Abrupt connection loss mid-send** — if `ws.send()` raises mid-push (client
   disconnects abruptly), the exception must be handled cleanly and `_handle`'s
   `finally` must cancel the `PushScheduler` task without leaking.

This task (Step 1) **assesses whether the landed code is actually correct** for
both gaps, then (Steps 2–3) implements the agreed hardening. The baseline test
(`tests/test_applink_pusher.sh`) passed 43 checks before this task.

## Assessment of the landed code (task Step 1)

Read `pusher.py`, `server.py:_handle`, `content.py` (`Subscription`/`PaneState`),
the spec, and the existing test. Findings:

### Gap 1 — Back-pressure: code correct; coverage gap only

`_run_once` (pusher.py:102) guards with `_over_high_water()` and returns early,
**keeping the force set intact** (`sub.force` is only `.discard()`'d at the end
of a *successful* `_push_pane`). The landed architecture collapses the spec's
three-step ("coalesce → drop cursor → skip tick") into a single
**skip-tick-and-recapture** model — correct, not a deviation:

- **Coalesce** is *structural*: no internal send queue; each tick captures fresh
  state, so multiple mutations collapse to one frame on the next un-pressured
  tick. Nothing queued, nothing to coalesce.
- **Drop cursor** is *moot*: the design emits no standalone `cursor` (0x04)
  frames (cursor is folded into keyframes/deltas; standalone cursor deferred).
  No cursor frames to drop.

Verdict: no bug; behavior correct but untested → add a test.

### Gap 2 — Abrupt disconnect mid-send: teardown correct; latent state-mutation gap

- **Push side:** `_send` (pusher.py:238) wraps `ws.send` in try/except → on any
  exception sets `_stopped = True` and swallows it. No exception propagates out
  of `_run_once`/`_loop`.
- **Read side:** `_handle`'s `async for raw in ws` raises → `except Exception:
  pass` → `finally` pops the pusher from `self._pushers` and `await
  pusher.stop()` (cancel + await under `contextlib.suppress`) — deterministic
  teardown, no leak.
- **Latent gap (fixed in this task):** because `_send` swallows, `_push_pane`
  ran to its tail and advanced `PaneState` + `sub.force.discard(pane_id)` **even
  after a failed send** — a forced keyframe whose send failed was dropped from
  `force`. Not a live bug only because "failed send ⇒ `_stopped` ⇒ teardown"
  made the stale state unreachable. The user chose to fix this rather than rely
  on teardown timing.

## Implementation (task Step 3)

### Production hardening — `.aitask-scripts/applink/pusher.py`

Two `_stopped` guards (no new state, no signature change, no success-path
behavior change):
- `_push_pane`: an `if self._stopped: return` **before** the tail-mutation block,
  so a failed send leaves `force`/`PaneState` untouched (forced keyframe survives
  for a future resend).
- `_run_once`: an `if self._stopped: return` at the top of the pane loop, so a
  failure on one pane stops the pass instead of hammering the dead socket.

### Tests — `tests/test_applink_pusher.sh`

New fakes: `FakeTransport` (controllable `get_write_buffer_size`), `ConnClosed`
(plain Exception subclass), `RaisingWS` (send always raises), `HandleWS` (async
iterator yielding one frame then raising; send raises), `FakeRouter` (seeds a
one-pane subscription, no reply). Loop exception handler installed at the top of
`main()` to assert nothing leaks.

- **Case A — back-pressure:** over-high-water tick sends zero bytes and preserves
  the forced pane in `force`; after the buffer drains, two interim content
  changes coalesce to exactly one keyframe carrying the latest content; force
  cleared after the successful send.
- **Case B1 — disconnect (PushScheduler):** a raising `send` is swallowed,
  `_run_once` returns without raising, `_stopped` becomes True, nothing recorded
  as sent; the **hardening** keeps the pane in `force` and `PaneState`
  un-advanced; lifecycle `stop()` after a failed loop pass leaves `_task is None`.
- **Case B2 — disconnect (`AppLinkServer._handle`):** a real server built via
  `AppLinkServer.__new__` (no live `TmuxMonitor`) with fake router/monitor;
  driving the real `_handle` with `HandleWS` asserts the `finally` pops the
  pusher from `_pushers`, cancels its task (`_task is None`, no leak), stops it,
  and removes the connection from `_conns`/`_live`.
- **Whole-suite:** the loop exception handler captured nothing (no "Task
  exception was never retrieved").

## Verification

- `bash tests/test_applink_pusher.sh` → PASS (62 checks, was 43).
- Hardening proves itself: the "force preserved after a failed send" assertion
  fails if the `_push_pane` `_stopped` guard is removed (verified, then restored).
- `bash tests/test_applink_content.sh` → PASS (78); `tests/test_applink_router.sh`
  → PASS (95); `tests/test_applink_smoke.sh` → PASS (1/1).
- `import pusher` → no import/syntax error.

## Risk

### Code-health risk: low
- Production change is a ~2-line `_stopped` early-return guard in `pusher.py`
  (`_push_pane` tail + `_run_once` loop). No new state, no signature change, no
  success-path behavior change; covered by the new "force preserved after a
  failed send" test. · severity: low
- Remaining changes confined to one test file, reusing existing fakes/helpers. ·
  severity: low

### Goal-achievement risk: low
- The task's named labels ("coalesce", "drop-cursor") are partly moot under the
  landed architecture (coalesce structural; no standalone cursor frames). ·
  severity: low · → mitigation: AC interpretation made explicit here and in the
  Final Implementation Notes (no-silent-AC-deviation); tests cover the real
  testable behaviors.

## Step 9 (Post-Implementation)

Profile `fast`, current branch (no worktree). Code (`pusher.py` + test) via
regular `git` (`chore: ... (t822_14)`); plan via `./ait git`. Push via
`./ait git push`. Archive via `./.aitask-scripts/aitask_archive.sh 822_14`.

## Final Implementation Notes

- **Actual work done:** Assessed both t822_8 plan-review gaps against the landed
  code, then implemented per the approved plan.
  - `pusher.py`: added two `_stopped` early-return guards — one before the
    `_push_pane` tail-mutation block (preserves `force`/`PaneState` after a
    swallowed send failure) and one at the top of the `_run_once` pane loop
    (stop cleanly instead of hammering a dead socket).
  - `tests/test_applink_pusher.sh`: +19 checks (43 → 62). New fakes
    (`FakeTransport`, `ConnClosed`, `RaisingWS`, `HandleWS`, `FakeRouter`), a
    loop exception handler, and three cases: back-pressure skip-tick/coalesce
    (A), abrupt-disconnect at the `PushScheduler` level incl. the hardening (B1),
    and abrupt-disconnect through the **real** `AppLinkServer._handle` finally
    via `AppLinkServer.__new__` (B2).
- **AC interpretation (no silent deviation):** the spec's literal "coalesce →
  drop cursor → skip tick" is realized in the landed code as
  skip-tick-and-recapture — coalesce is structural (no send queue) and
  drop-cursor is moot (no standalone cursor frames). Gap 1 was a coverage gap,
  not a bug.
- **Deviations from plan:** none. The back-pressure coalesce-content assertion
  reuses the existing in-test `truth()` helper rather than hardcoding the span
  encoding (more robust); the B2 test uses `AppLinkServer.__new__` to drive the
  real `_handle` without constructing a live `TmuxMonitor`.
- **Issues encountered:** none. Confirmed the B1 hardening assertion fails with
  the `_push_pane` guard removed, then restored the guard.
- **Key decisions:** Gap 2 fixed (not just tested) per user request — the
  post-send-failure `force`/state mutation is now structurally prevented rather
  than relying on the "failed send ⇒ teardown" invariant. Used the existing
  `_stopped` flag (no new state) to keep the change ~2 lines.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** The `PushScheduler` correctly preserves `force`
  and `PaneState` across a failed send — siblings adding new frame types in
  `_push_pane` must keep their state mutations **after** the `_stopped` tail
  guard so they inherit the same resend-safety. Driving `AppLinkServer._handle`
  in a unit test without tmux is done via `AppLinkServer.__new__` + fake
  `_router`/`_monitor` (see B2) — reusable for future server-lifecycle tests.
