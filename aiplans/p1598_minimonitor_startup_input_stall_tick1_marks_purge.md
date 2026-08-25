---
Task: t1598_minimonitor_startup_input_stall_tick1_marks_purge.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1598 — Minimonitor startup input stall: tick-1 marks purge on the App pump

## Context

When `ait minimonitor` spawns beside a freshly launched code agent, the TUI is
**unresponsive to input for ~10 seconds** after boot. The agent list renders and
a card is highlighted, but clicks and keypresses do nothing. It never recurs on
later ticks.

Three things compose, and only the first is the trigger:

1. **`monitor_shared.py:352` seeds `_marks_purge_due_at = 0.0`** — the comment
   states the intent: *"0.0 ⇒ the first refresh tick after mount materializes a
   purge."* So `_maybe_purge_marks` (`:625`) fires on tick 1 and awaits a
   subprocess at `:647`.
2. **That subprocess can burn a full lock timeout** on a permanently wedged
   `agent_marks` mutex — `PURGE_LOCK_TIMEOUT=10` (`aitask_agent_marks.sh:58`).
   The wedge is real and was observed live: a dead-pid lock dir plus an empty
   `.gc` reclaim guard, which `stale_lock.sh` deliberately never auto-breaks.
3. **The structural amplifier** — `minimonitor_app.py:1163` dispatches the first
   tick with `self.call_later(self._refresh_data)`. In Textual 8.2.7 that posts
   an `events.Callback` to the **App's own** queue and `MessagePump.on_callback`
   awaits it **inline in the App's message loop** — the same serialized queue
   `App.on_event` dispatches key and mouse events from. Ticks 2+ come from
   `set_interval`, whose callback runs in its own task (`textual/timer.py:91`),
   which is exactly why the symptom is startup-only.

Rendered, focused, and dead to input.

The intended outcome: a freshly booted minimonitor dispatches a keypress within a
small bounded budget **even with the marks lock wedged**, the purge still runs
(deferred, not deleted), a wedged lock recovers without manual intervention, and
`ait monitor` — which carries the identical pattern — receives the same fixes.

## Corrections to the task file's own claims

Recorded here because the plan's edits depend on them:

- **`_stale_lock_maybe_reclaim` does not exist.** The reclaim function is
  `_stale_lock_reclaim_under_gc` (`.aitask-scripts/lib/stale_lock.sh:201`), called
  from the single site `:287`. The task file's line numbers for that file are stale;
  the `mkdir "$gc"` gate it describes is real, at `:251`.
- **The reported 10.267 s `aitask_agent_marks.sh list` is not incidental.**
  `:120` makes the read-only `list` verb take the **write** lock at
  `PURGE_LOCK_TIMEOUT`, contradicting the script's own header (`:12-14`,
  "Readers … read the JSON directly with no lock"), the sibling
  `aitask_shadow_rejected.sh:42`, and `monitor_shared.py:344`.
- **`stale_lock_acquire` has no bounded guard wait.** `:251` is a single-shot
  `mkdir`; a momentarily-held guard costs a whole retry from the budget. Both
  `stale_lock_release` (`:410`) and `stale_lock_guarded_section` (`:373`) wait
  40 × 0.05 s.
- **Two blocking mount-path calls the task did not list:** a raw
  `subprocess.run(["tmux", …], timeout=5)` at `minimonitor_app.py:1008` that
  bypasses the tmux gateway entirely, and `TmuxControlBackend.start()` at
  2.0 + 5.0 s (`monitor_core.py:1236`, `:1248`).
- **`discover_window_panes` has no `_async` sibling** (`monitor_core.py:2078`) —
  one must be written. Every other gateway minimonitor needs already has one.
- **`monitor_app.py`'s `_get_desync_summary` is not wasted** the way
  minimonitor's is: the full monitor's session bar is always displayed.

## Decisions taken

- **Scope: one task, all seven workstreams** (user decision). The `.gc` guard
  reclaim ships here rather than as a separate task, despite inverting a
  documented invariant.
- **Markerless guard reclaim: scoped opt-in, off by default** (user decision).
  Registry / gate / child locks pass a 600 s markerless window; `merge_lock.sh`
  passes nothing. The acceptance criterion is therefore met for the reported
  (registry) case and deliberately **not** for the merge lock, which keeps its
  `force-release` / manual ladder. Dead-marker reclaim is on everywhere.
- **tmux safety:** implementation proceeds from inside the user's main aitasks
  tmux, on the condition that every live test isolates via
  `tests/lib/tmux_isolation.sh` `require_isolated_tmux` **and** an isolated
  `AITASKS_AGENT_MARKS_FILE` (`aitask_agent_marks.sh:47`, whose `MARKS_LOCK_DIR`
  at `:51` follows the override). This satisfies
  `aidocs/framework/tui_conventions.md:685`.

## Further corrections found during design

- **`set_timer(0, …)` does NOT escape the App pump** — this contradicts the task
  file's Suggested direction #2. `MessagePump.set_timer`
  (`textual/message_pump.py:406`) wraps the callback in
  `partial(self.call_next, …)`; `call_next` (`:507-519`) appends an
  `events.Callback` to `_next_callbacks`, drained by `_flush_next_callbacks`
  (`:695-704`) **inline in `_dispatch_message`** — and *ahead* of already-queued
  input rather than behind it. `call_after_refresh` (`:451-465`) escapes the App
  pump but lands on the **Screen** pump (`screen.py:1274`), which is where keys
  bubble and the compositor lives. Only `run_worker` — `asyncio.create_task`
  (`textual/worker.py:401`) — is a genuine escape.
  `set_interval` differs from `set_timer` precisely because it passes the
  callback **unwrapped** (`:418-447`), which is the real reason ticks 2+ don't
  stall input.
- **`run_worker(coro)` is already off every pump**, so `_connect_control_client`
  is not a *dispatch* problem — its body is synchronous, so it blocks the **loop
  itself**, which freezes painting too, not just input.
- **`thread=True` is the wrong seam** for `_connect_control_client`:
  `Worker._run_threaded` (`textual/worker.py:285-326`) detects a coroutine and
  runs `asyncio.run()` **inside the executor thread** — a second event loop —
  while the coroutine calls `self.log(...)` into Textual.
- **`minimonitor_app.py:1008` is already allowlisted** in
  `tests/test_no_raw_tmux.sh` and matches the sanctioned ambient-`$TMUX` class in
  `aidocs/framework/tmux_gateway.md:90-98`. It is deliberately raw: it probes the
  **ambient** server before `self._monitor` exists, so routing it through the
  gateway would query the wrong socket. Not a chokepoint violation — out of scope,
  recorded as a follow-up.
- **Two refresh-path sync-tmux sites the task file missed:**
  `refresh_shadow_phase_stamp` (`monitor_core.py:3182`) is reached on **both**
  apps' refresh paths — minimonitor via `_maybe_offer_concerns` →
  `_restamp_shadow_phase` (`minimonitor_app.py:4029`), monitor from inside the
  *synchronous* card renderer (`monitor_app.py:1643`); and
  `_root_for_snap` (`minimonitor_app.py:1388`) calls the sync mapping and is
  render-reachable via `_own_header_session` (`:1423`). The monitor's identical
  `_root_for_snap` (`monitor_app.py:939`) is only reached from keypress actions,
  which is why the existing poison-pill test never caught it.
- **The `0.0` seed is currently untested.** `tests/test_monitor_agent_marks*.py`
  build the app with `cls.__new__` and set `_marks_purge_due_at = 0.0`
  explicitly, so the seed itself has no pin — it needs one.

## Implementation

Ordered so that each step is independently green. **Step 4 must follow Step 3**:
with the first refresh in a worker, a surviving synchronous `tmux_run` would
block the whole loop instead of just the pump — worse than today.

### Pre-phase (risk mitigations)

1. `[characterize_lock_baseline]` **Before touching `stale_lock.sh`**, run
   `tests/test_stale_lock.sh`, `tests/test_registry_lock.sh`,
   `tests/test_merge_lock_broker.sh`, `tests/test_merge_lock_concurrency.sh` and
   `tests/test_agent_marks_concurrency.sh`, and record each file's PASS/FAIL
   summary line verbatim in the plan's Final Implementation Notes. Protocol G is
   designed so these suites keep passing — the existing leaked-guard assertions
   (`test_stale_lock.sh:174-198`, `test_registry_lock.sh` cases 9/9b/10/11/12) use
   **markerless, non-opted-in** fixtures and stay true, with only their comments
   sharpened. That is a claim about a load-bearing mutex, so it must be *measured*,
   not asserted: a green baseline turns any later red into a real signal instead of
   an argument about whether it was expected.
2. `[autoclose_parity_test_first]` **Before porting `_check_auto_close`**, write
   T4 — the parameterized `(observed, panes)` suite run twice, sync and async,
   over `test_minimonitor_auto_close_guard.py`'s existing fixtures — and confirm
   the async half **fails** (`discover_window_panes_async` does not exist yet).
   Only then write the sibling in `monitor_core.py`. This path kills panes, and
   reading `observed=False` as "empty" is what caused the 2026-08-06 mass-quit;
   the port must be written against a red test, not validated after the fact.

### Step 1 — Purge off tick 1 (shared; fixes the reported symptom outright)

`.aitask-scripts/monitor/monitor_shared.py`:

- Beside `_MARKS_PURGE_INTERVAL` (`:302`), add
  `_MARKS_PURGE_STARTUP_GRACE = 60.0` with a comment recording why: 60 s is
  20 refresh ticks past mount (cadence 3 s, auto-close mount grace 5 s), above
  `_MARKS_CMD_TIMEOUT = 20.0` (`:307`) so a maximally-stalled first attempt
  cannot straddle the window, and 10 % of `_MARKS_PURGE_INTERVAL` so the growth
  bound is materially unchanged.
- `:351-352`: seed `self._marks_purge_due_at = time.monotonic() + _MARKS_PURGE_STARTUP_GRACE`.

`_MARKS_PURGE_INTERVAL` is untouched; `:636` and `:652` are unchanged. Lands once
for both apps (`_init_agent_marks` called from `minimonitor_app.py:966`,
`monitor_app.py:644`).

### Step 2 — Control client genuinely off the loop (`monitor_core` only)

`monitor_core.py:1539` and `:1553`: wrap the blocking bodies in
`await asyncio.to_thread(backend.start)` / `(backend.stop)`.

Fixed in the core rather than at the call sites because there are **five** call
sites and one is not a worker at all: `await self._monitor.close_control_client()`
runs directly in `on_unmount` (`minimonitor_app.py:1168-1179`). It also makes the
`:1541-1543` docstring true instead of an admission. Leave the internal
`stop()` on `start()`'s failure path (`:1257`) where it is.

**The `to_thread` hop introduces a lifecycle race that does not exist today, and
must be closed in the same edit.** Verified: `start_control_client` assigns
`self._backend` only **after** `backend.start()` returns (`:1546-1548`), and
`close_control_client` acts only `if self._backend is not None` (`:1554`). Today
the body is synchronous, so there is no interleaving point. Once `start` is
awaited, `on_unmount` can land in the gap, find `self._backend is None`, no-op —
and the completed start then installs a **live `tmux -C attach` backend and its
thread on an already-closed app**, leaking both.

Close it with a generation guard on `TmuxMonitor` (`_backend_gen`, seeded in
`__init__`):

- `close_control_client` **bumps `_backend_gen` first**, then swaps
  `self._backend` out and stops it — so it invalidates an in-flight start even
  when there is nothing installed yet.
- `start_control_client` snapshots the generation **before** the await and, after
  it, installs the backend only if the generation is unchanged; otherwise it
  stops the backend it just started and returns `False`.

The bump must happen on **every** re-entry, not only unmount — `_start_monitoring`
reaches it via `_teardown_prior_monitoring` → `_close_prev`, which is exactly the
re-entry a second `start` would otherwise race.

Test (T6b): stub `TmuxControlBackend.start` to block on an `threading.Event`,
call `start_control_client()` as a task, `await close_control_client()` while it
is blocked, release, then assert `has_control_client()` is `False`, that the
just-started backend received `stop()`, and that `threading.enumerate()` lists no
surviving `tmux-control-loop` thread. Negative control: without the generation
guard the same sequence leaves `has_control_client()` `True`.

### Step 3 — Port minimonitor's refresh path to the async gateway

- `monitor_core.py`: extract `_parse_window_panes(rc, stdout)` holding the
  `(observed, panes)` decision, then express **both** `discover_window_panes`
  (`:2078`) and a new `discover_window_panes_async` through it. Extracted, not
  duplicated, precisely because `observed=False` means UNVERIFIABLE, never EMPTY
  (`:2086-2098`) — the distinction behind the 2026-08-06 mass-quit incident.
  Share the `-F` format string as one module constant.
- `minimonitor_app.py:1201` → `await get_session_to_project_mapping_async()`
  (sibling at `monitor_core.py:1807`; `monitor_app.py:978` is the precedent).
- `minimonitor_app.py:1306` `_update_own_window_info` → `async def` +
  `tmux_run_async`; awaited at `:1219`. Style reference: `monitor_app.py:1567`.
- `minimonitor_app.py:1269` `_check_auto_close` → `async def` +
  `discover_window_panes_async`; awaited at `:1223`.
- Point `_root_for_snap` (`minimonitor_app.py:1388`) at the already-populated
  `self._session_root_map` — fed the **async** mapping every tick by
  `_set_session_root_map` (`monitor_shared.py:364`) — keeping the
  `self._project_root` fallback. Removes the last sync mapping call from the
  render path at zero cost; same "reuse the last tick's map" contract
  `_completed_pane_ids` already documents (`monitor_shared.py:354-358`).
- Add `refresh_shadow_phase_stamp_async` (`monitor_core.py:3153`), keeping the
  sync one for `tmux_monitor.py:59` and sharing the args construction.
  minimonitor: `_restamp_shadow_phase` (`:2996`) → `async def`, awaited at `:4029`.
  monitor: do **not** make the card renderer async — collect
  `(shadow_pane_id, signal)` into `self._pending_shadow_stamps` and flush after
  `_rebuild_pane_list()` (`monitor_app.py:1048`). Best-effort semantics unchanged.

Test collaborators that must move in the same commit (they break loudly —
awaiting `None`): `tests/test_minimonitor_scroll_preservation.py:359-366,393-394`,
`tests/test_minimonitor_own_mark.py:559`,
`tests/test_minimonitor_auto_close_guard.py:113-133,326-340`,
`tests/test_monitor_modal_space_dispatch.py:95`.

### Step 4 — First refresh off the App pump (both apps)

- `minimonitor_app.py:1163` and `monitor_app.py:820`: replace
  `self.call_later(self._refresh_data)` with
  `run_worker(self._refresh_data(), name="first_refresh", group="refresh-init", exclusive=False, exit_on_error=False)`,
  dispatched **before** the `set_interval`. Carry a comment naming why
  `set_timer` / `call_after_refresh` are not alternatives.
- Move the trailing maintenance out of the render callback: replace
  `minimonitor_app.py:1263` + `:1267` and `monitor_app.py:1072` with one
  `self._dispatch_refresh_maintenance()` — a named **sync seam** so tests stub
  the dispatch rather than letting a real worker outlive `run_test`
  (`aidocs/framework/testing_conventions.md:57-59`). It runs
  `_maybe_offer_concerns` then `_maybe_purge_marks` in a worker under a
  `_maintenance_inflight` guard (seeded beside `_marks_purge_inflight`,
  `monitor_shared.py:353`), with `exit_on_error=False`.
- Add a `_refresh_inflight` guard at the top of both `_refresh_data` bodies. The
  first refresh can now overlap the first interval tick and the ~12 keypress-driven
  `call_later(self._refresh_data)` sites. `capture_all_async`'s generation guard
  covers the capture half but not the DOM rebuild; a skipped overlapping refresh
  is at most one 3 s cadence late, which beats two concurrent
  `remove_children`/`mount_all` passes.

  **The reset is `try` / `finally`, mandatory — a bare set-and-clear would make
  the TUI permanently stop refreshing after one failure.** Every `await` on this
  path can raise (`capture_all_async`, the gateway calls, and Textual's own
  `remove_children` / `mount_all`), `asyncio.CancelledError` propagates through
  on app shutdown, and `_refresh_data` additionally has **two early `return`s
  before any work** (`minimonitor_app.py:1185` `self._monitor is None`, `:1196`
  `snaps is None`) which would strand the flag on the ordinary path, not just the
  exceptional one. Set the flag, then wrap the entire remaining body:

  ```python
  if self._refresh_inflight:
      return
  self._refresh_inflight = True
  try:
      ...            # whole existing body, early returns included
  finally:
      self._refresh_inflight = False
  ```

  The same discipline applies to `_maintenance_inflight` above (its `finally`
  is already in the sketch) and matches the existing `_marks_purge_inflight`
  contract, whose docstring at `monitor_shared.py:630-631` says the flag "is
  cleared in a `finally` so a crashed or hung wrapper cannot wedge the
  scheduler" — the identical hazard, one level up.

  Test (T2b): inject a `_refresh_data` failure (patch `capture_all_async` to
  raise once), await it and swallow, then drive a **second** `_refresh_data` and
  assert it actually performs work — the pane list rebuilds. Negative control:
  with the reset moved out of `finally`, the second refresh is a silent no-op.
  Cover cancellation too: cancel a refresh mid-`await` and assert the next one
  still runs.

### Step 5 — `_get_desync_summary` below the gate

`minimonitor_app.py:1632`: gate the fetch on `self._session_bar_enabled` (not on
`bar.display`, which is set later at `:1649`). Keep the `:1645-1649` every-tick
write so a future runtime toggle still works. Single call site confirmed
(`:1225`). The not-inside-tmux banner (`:986-995`) returns before
`_start_monitoring`, so it cannot regress.

`monitor_app.py:1518` always shows its bar, so the gate does not apply; making
that one async is recorded as a follow-up, not done here.

### Step 6 — `.gc` guard auto-reclaim (`stale_lock.sh`) — Protocol G

**Both shapes the task names are unsafe.** Age-only (shape a) cannot protect
`_fr_guarded` (`aitask_merge_task.sh:384-437`), which holds the guard across
`git merge --abort` (`:408`) and `git reset --hard HEAD` (`:421`) — verified,
unbounded by user data, so no window dominates it. And the identity-plus-`mv`
variant is unsafe for a subtler reason: **`mv` resolves by path, not by
instance.** A contender that judged instance I1 stale and then stalled will
happily rename away instance I2 — a live, legitimately-held guard — after
another process reclaimed and re-published in between.

**The primitive asymmetry is the whole design:**

| op | succeeds when | instance-safe |
|---|---|---|
| `mkdir P` | `P` absent | yes — single winner |
| `mv P Q` | `P` exists, **any contents** | **no — resolves by path** |
| `rmdir P` | `P` exists **and is empty** | yes, if a live instance is never empty |
| `rmdir P/x.<nonce>` | that exact instance exists | yes — names an instance |

Protocol G keeps every destructive step in the last two rows.

**`$gc` keeps its exact current lifecycle** — one atomic `mkdir` to claim,
`rmdir` to free, **absent when free**. The only addition is that the holder
immediately publishes an identity marker *directory* inside it:

```
<lock_dir>.gc/                    the mutex — unchanged, absent when free
<lock_dir>.gc/h.<pid>.<nonce>/    the holder record — instance-unique name
```

The marker is **identity, not ownership** — that distinction is what stops the
recursion which kills the nested-claim family. Four states:

| `$gc` | policy |
|---|---|
| absent | free — `mkdir` it |
| marker, pid **alive** (or EPERM) | **never touched, at any duration** — liveness, never age |
| marker, pid **provably dead** | reclaim: `rmdir "$gc/<marker>"` (instance-keyed), then `rmdir "$gc"` |
| **no marker** | old/foreign code, or a two-syscall transient — **off by default**, see the opt-in below |
| >1 marker | protocol violation — fail closed, warn |

`<pid>` is `${BASHPID:-$$}`. New invariant 7: **the guard is never held across a
process boundary** in any path in this tree, so `kill -0` is authoritative for it
and the `STALE_LOCK_IDENTITY_PID` / `_STALE_LOCK_LIVENESS_FN` seams (which exist
because the *lock dir's* holder may outlive `$$`) must **not** apply to it.

Release becomes three-valued:

```
rmdir "$gc/$marker" || return 2      # our claim is gone: we hold nothing, touch NOTHING
rmdir "$gc"         || { mkdir "$gc/$marker" 2>/dev/null; return 1; }   # genuinely retained
return 0
```

`rmdir`'s status stays authoritative for the reason at `:167-174` **plus a
stronger one**: a successful `rmdir "$gc"` can only have removed an *empty*
`$gc`, and after our own marker removal the only empty `$gc` at that path is
ours. Re-publishing the marker on the retained path is new and cheap — it turns
today's permanent "retained guard" wedge into one that self-heals once our
process exits.

**Why this closes the review's concern structurally, not probabilistically:** A
reads `h.<deadA>.<nonceX>` and stalls; B disarms it, re-`mkdir`s `$gc`, publishes
`h.<B>.<nonceY>`, enters `git reset --hard`. A resumes and runs
`rmdir "$gc/h.<deadA>.<nonceX>"` → **ENOENT**. Nonces are never reused, so A
returns "state changed" and **never reaches `rmdir "$gc"`**. B is untouched.
Two markerless stealers are cut the same way: the loser's `rmdir "$gc"` hits a
non-empty directory (ENOTEMPTY) and refuses.

#### Marker classification — every unexpected state is fail-closed, by rule

`_stale_lock_gc_find_marker` must **classify**, not merely glob. Measured on
this box, the naive shape misclassifies:

- a **dangling symlink** named `h.<pid>.<nonce>` is invisible to `[[ -e ]]`, so
  the guard reads as **markerless** and takes the age path — stopped only by
  `rmdir`'s incidental `ENOTEMPTY` (verified: `rmdir: Directory not empty`);
- a marker that is a **plain file** is visible to `-e` but `rmdir` fails
  `Not a directory` (verified) — again incidental.

Relying on an accidental `rmdir` failure for a safety property is precisely what
breaks when someone later "optimises" the markerless path. Define the rules
explicitly instead; **only the last row may ever reach the age branch**:

| state of `$gc` | classification | policy |
|---|---|---|
| an `h.*` entry that is not a **directory** (file, symlink, dangling symlink) | malformed | fail closed, distinct warn |
| an `h.*` name not matching `h.<digits>.<nonce>` | malformed | fail closed, distinct warn |
| >1 `h.*` entry | protocol violation | fail closed, distinct warn |
| exactly one valid marker dir | identified | liveness decides — never age |
| **any non-`h.*` entry present** | foreign content | fail closed — **do not** markerless-reclaim |
| genuinely empty | markerless | age branch, opt-in only |

Enumerate with `[[ -e "$m" || -L "$m" ]]` so a dangling symlink is **seen** and
classified malformed rather than silently skipped; require `[[ -d "$m" && ! -L "$m" ]]`
for a valid marker. Fail-closed here costs at most a manual cure on a state
nothing in this tree produces; misclassifying costs a stolen live guard.

#### The markerless case — scoped opt-in, off by default

**New code cannot distinguish an old-code holder three seconds into
`git reset --hard` from a guard leaked two days ago.** A markerless `$gc` carries
exactly one bit — its mtime. There is no probe and no negotiation with a binary
that shipped before the marker existed. This is stated plainly rather than
papered over.

But the hazard is not "old code" — it is *code that holds the guard across an
operation bounded by user data*, and that set is **statically enumerable**:
`stale_lock_guarded_section` has **exactly one production caller in the tree**
(`aitask_merge_task.sh:489`, verified by grep), operating on exactly one lock
dir. Every other guard section in every shipped version is a fixed handful of
file ops — five to six orders of magnitude below any usable window.

So markerless reclaim becomes a **5th positional argument** to
`stale_lock_acquire` carrying the window; unset/0 = never:

- `registry_lock.sh:108`, `aitask_gate.sh:130`, `aitask_create.sh:341` pass
  `600` — none can reach a long guard section in any version;
- **`merge_lock.sh:187` passes nothing**, with a header delta recording why. That
  comment is the enforcement point: anyone adding a long guarded section
  elsewhere must contradict it in writing.
- `stale_lock_release` and `stale_lock_guarded_section` pass nothing either — they
  get dead-marker reclaim only, so force-release stays the human ladder it was
  designed to be.

A **positional argument, not an env var**: a process-global would leak the opt-in
onto the merge lock in any process sourcing both adapters, and `_STALE_LOCK_WINDOW`
(`:60`) is already non-exported precisely so a child cannot inherit policy.

**Rolling upgrade, in the dangerous direction — safe, and testable.** Old code's
release is a bare `rmdir "$gc"` (verified at `:175-177`); against a
marker-carrying guard it fails **ENOTEMPTY**, and every old path then fails
closed *loudly*: acquire unwinds its own lock and warns (`:271-272`), release
warns (`:430`) and `registry_lock.sh:131` reports "not fully released". Old code
also cannot acquire while we hold (`mkdir` EEXIST) — and, crucially, **is not
permanently wedged**, because `$gc` is still absent when free. That last property
is exactly what a permanently-present container would destroy.

#### Other changes

- New `_STALE_LOCK_GC_WINDOW_DEFAULT=600` (not exported, same shape as `:60`).
- New `_stale_lock_gc_marker_name` (no `date` fork — this runs every acquire
  iteration), `_stale_lock_gc_find_marker` (nullglob-agnostic),
  `_stale_lock_gc_probe`, `_stale_lock_gc_take`.
- **`_stale_lock_gc_take` replaces the bare `mkdir "$gc"` at all THREE sites**,
  not only acquire: `:251` (`stale_lock_acquire`), `:373`
  (`stale_lock_guarded_section`) and `:410` (`stale_lock_release`). The latter two
  pass an **empty** window, so they get dead-marker reclaim but never the
  markerless path — force-release stays the human ladder it was designed to be.
  Missing either site would leave a wedge that un-sticks acquire while release
  still exhausts its 40 × 0.05 s wait and strands an owned lock (pinned by T7b).
- `stale_lock_acquire`: `:251` → `_stale_lock_gc_take`; rc 2 ("state changed")
  counts the attempt and skips the sleep, mirroring `reclaimed=0` at `:287`.
  On release rc 2 at `:262`, warn and **do not unwind** — mutating the lock dir
  outside a guard we do not hold is precisely what `:167-174` forbids.
- `_STALE_LOCK_GUARD_MARKER` beside `_STALE_LOCK_GUARD_ACTIVE` (`:332`), threaded
  into `_stale_lock_guard_on_signal` (`:345`) and the post-fn release
  (`:389-395`) — load-bearing for `tests/test_merge_lock_broker.sh:396`, which
  must now assert the **marker** is gone as well as `$gc`. A signal handler that
  drops the guard but leaves the marker turns `rmdir "$gc"` into `ENOTEMPTY`; the
  residue is dead-marker-reclaimable so it self-heals, but it must be tested
  rather than assumed.
- **Retry-budget floors 2 → 3** at `registry_lock.sh:105-107` and
  `merge_lock.sh:184`: two reclaims (guard, then lock dir) can now precede the
  acquiring `mkdir`, and the comment at `:103-104` already states that reasoning
  for one.
- All pinned warns preserved verbatim (`:161, 211, 220, 233, 271, 272, 279, 283,
  346, 349, 376, 391, 413, 427, 430`); new strings avoid `Removing stale`,
  `Reclaiming` and `retained`.

**What this does NOT buy:** PID reuse and cross-PID-namespace holders leave a
guard permanently unreclaimable (inherited from invariant 3; optionally closed
later by adding a `/proc` starttime component to the marker name). A new-code
process killed in the one-syscall gap between marker removal and `rmdir "$gc"`
leaks a markerless guard. The merge lock keeps its manual ladder by design.

### Step 7 — `aitask_agent_marks.sh`: `list` must not take the write lock

`:120` makes the read-only `list` take the **write** lock at
`PURGE_LOCK_TIMEOUT`. `_cli_list` (`lib/agent_marks.py:491-496`) is `load()` +
`print` — a pure read with no read-modify-write to serialize, and writes land via
`os.replace`, so a reader always sees one whole generation. Drop the
`marks_lock_or_busy` call; update the header (`:12-14`), the verb list (`:29`)
and the exit-code note (`:31-34`) to record that `3` is unreachable for `list`.

No production consumer is affected: the TUIs read through
`agent_marks.MarksView()` (`monitor_shared.py:350`), never the wrapper, and
`_run_marks_cmd` is only ever called with `toggle` and `purge --observed`.

**This is a symptom fix and must not substitute for Step 6** — with the guard
still wedged, `toggle` stalls 2 s and `purge` 10 s and both fail. Say so in the
commit message.

### Post-phase (risk mitigations)

1. `[guard_contract_doc_sweep]` After the documentation sweep below, add an
   **executable** guard — a small `tests/test_guard_contract_doc_drift.sh`
   following `tests/test_serial_carveout_doc_drift.sh`'s shape — over
   `.aitask-scripts/`, `.claude/skills/`, `.agents/skills/`, `.opencode/skills/`,
   `aidocs/` and `tests/golden/`. A sweep that is merely performed drifts on the
   next edit to any of the nine rendered copies; one that is asserted does not.

   **Ban only the superseded UNIVERSAL claims** — statements now false for every
   guard:
   - "never automatically stolen" / "never auto-broken" (a **dead-marker** guard
     now is; the surviving true form is "never stolen from a *live* holder"),
   - "guard dirs are always empty" / "nothing ever writes into them",
   - "No age/PID heuristics on the guard",
   - a bare `rmdir '<…>.gc'` given as **the complete** cure — it now fails
     `ENOTEMPTY`; the cure is the two-argument
     `rmdir '<dir>.gc'/h.* '<dir>.gc'`.

   **Do NOT ban "never `rm -rf`".** Protocol G's cure is still `rmdir`-only, so
   that warning remains true and load-bearing — `rmdir` is structurally incapable
   of destroying a lock's contents, which is exactly why the docs say it.

   **Explicitly permit scoped residual language.** R1 (PID reuse) and R4 (a hung
   live holder) still require manual recovery and that must stay documented and
   truthful — so the guard must not match phrases like "the cure is manual",
   which remain correct *for those cases*. Banning it would either fail on
   correct docs or pressure a future editor into deleting a real limitation.
   The discriminator is universality, not the word "manual": a sentence scoped
   by "when the holder's pid was recycled" is fine; an unscoped "the cure is
   manual" is not. Where a mechanical regex cannot separate the two, prefer
   letting the phrase through — a false negative costs a stale sentence, a false
   positive costs a true one.

   Assert the **hit count**, not just a clean exit: `grep … || echo OK` exits 0
   on no match *and* on a mistyped path, so the guard would pass while checking
   nothing. Pin the searched root set too, and give the test a positive control
   — a fixture line containing a banned universal claim that the matcher must
   flag — so a broken pattern cannot read as "clean".

## Documentation sweep (same change)

The guard's contract is published in more places than the task file lists:

- `stale_lock.sh:18-21` (invariant 2), `:36-47` (limitations — add R2),
  `:152-177` (both removal helpers; `:172-174` "guard dirs are always empty" is
  now **false**), `:302-331` (`guarded_section` doc — `:329-331`'s "the cure is
  `rmdir` (never rm -rf)" inverts on both counts), `:138-150`.
- `registry_lock.sh:58-66` ("The cure is manual"), plus prose at `:21, 54, 140`;
  `merge_lock.sh:13, 130, 234`.
- `aidocs/framework/shell_conventions.md:85-93` — "a wedged `.gc` guard is the one
  manual-recovery case", the strongest claim in the docs.
- `.claude/skills/task-workflow/merge-broker.md:114-119, 588-590` is the
  **source**; there are **nine** rendered copies, not three — verified:
  `.claude/skills/task-workflow-{default,fast,remote}-/`,
  `.agents/skills/task-workflow-{default,fast,remote}-codex-/`,
  `.opencode/skills/task-workflow-{default,fast,remote}-/`. Edit the source,
  re-render each profile, regenerate
  `tests/golden/procs/task-workflow/merge-broker-default.md`, then run
  `tests/test_skill_render_task_workflow.sh`, `tests/test_skill_rerender.sh`,
  `tests/test_skill_parity_runtime_vs_rendered.sh`,
  `./.aitask-scripts/aitask_skill_verify.sh`.
- `aitask_merge_task.sh:91, 103, 342, 472` — four hint strings, three saying
  `rmdir`.

**Protocol G leaves most of this surface untouched** — `stale_lock_describe`'s
`-e` test (`:146`), `FREE_GUARD_PRESENT`, `_VERDICTS_STATUS`, and all six
`assert_dir_not_exists … .gc` assertions (`test_stale_lock.sh:69`,
`test_registry_lock.sh:174,176`, `test_gate_lock_single_winner.sh:126`,
`test_registry_lock_single_winner.sh:123`, `test_merge_lock_broker.sh:396`) stay
correct, because `$gc` is still absent when free. The genuine breakages are the
**manual-cure text** at `stale_lock.sh:147` and `:331`, `registry_lock.sh:63`,
`aitask_merge_task.sh:426`, and `merge-broker.md:118`/`:589` — plus the
**retry-budget floors** (`registry_lock.sh:105-107`, `merge_lock.sh:184`, 2 → 3).

**Keep the `FREE_GUARD_PRESENT` verdict token** (`aitask_merge_task.sh:325-326`,
`:503`; `merge-broker.md:105`). It still describes reality — only its prose
changes — and renaming it would churn `_VERDICTS_STATUS`, the vocabulary block
parsed by `tests/test_merge_broker_rendered_verdicts.sh`, the table, the branch
heading, all nine rendered copies and the golden, for zero semantic gain.

`monitor_shared.py:344-345` and `aidocs/framework/shadow_agent.md:503-505` are
**no-ops** — verify, don't touch.

## Verification

Run from a shell **outside** the main aitasks tmux is not required, since every
live test isolates; but each of these must pass:

```bash
bash tests/test_stale_lock.sh
bash tests/test_registry_lock.sh
bash tests/test_agent_marks_concurrency.sh
bash tests/test_merge_lock_broker.sh
bash tests/test_merge_lock_concurrency.sh
bash tests/test_no_raw_tmux.sh
bash tests/test_serial_carveout_doc_drift.sh
./.aitask-scripts/aitask_skill_verify.sh
shellcheck .aitask-scripts/lib/stale_lock.sh .aitask-scripts/aitask_agent_marks.sh
bash tests/run_all_python_tests.sh --test-dir tests   # read the LAST line only
```

### Tests to add or change

| id | what | negative control |
|---|---|---|
| T1 | The `0.0` seed is gone: real `MiniMonitorApp`/`MonitorApp` `__init__` leaves `_marks_purge_due_at >= t0 + grace`; assert `_MARKS_PURGE_INTERVAL == 600.0` and `grace < interval` as an executable "deferred, not deleted" pin. **The seed is currently untested** — the existing suites `__new__` the app and set `0.0` by hand. | existing `PurgeSchedulingTests` (`test_monitor_agent_marks_action.py:389`) already proves a purge *does* fire when due — cite it, don't duplicate |
| T2 | **The AC-bearing test.** New `tests/test_minimonitor_startup_input_latency.py`: boot a real `MiniMonitorApp` under `run_test`, stall the first refresh on an `asyncio.Event` (loop stays free, so this isolates the *pump* property that a loop-lag probe provably cannot see), then `asyncio.wait_for(press-and-observe, timeout=1.0)`. On the fix the key dispatches in single-digit ms; on the defect the gate can only be released by the test, so failure is a hard `TimeoutError` — the AC's "well under 1 s" as a real assertion with a deterministic failure mode. Never `pilot.pause()` (its `wait_for_idle(0)` has a ≥20 ms synthetic floor); record an unbound-key floor sample as in `test_board_movement.py:756`. | docstring records two hand-run positive controls: reverting `:1163` to `call_later` **and** to `set_timer(0, …)` must both fail by timeout — the second is what pins the `set_timer` finding against a future "simplification" |
| T2b | `_refresh_inflight` survives a failure: patch `capture_all_async` to raise once, swallow, then drive a second `_refresh_data` and assert it actually rebuilds. Plus a cancelled-mid-`await` variant. | move the reset out of `finally` — the second refresh must become a silent permanent no-op |
| T6b | `close_control_client()` during a blocked `backend.start()` leaves nothing installed: assert `has_control_client()` is `False`, the started backend got `stop()`, and no `tmux-control-loop` thread survives. | without the generation guard the same sequence leaves `has_control_client()` `True` |
| T3 | Extend `tests/test_monitor_refresh_no_sync_tmux.py`'s poison-pill fake to `MiniMonitorApp` (it never instantiates it today — the reason the sync round-trips survived there). Add the minimonitor-only collaborators; push `_mount_time` back 60 s so `_check_auto_close` actually runs. | a variant fake **missing** `discover_window_panes_async` must trip the pill *naming the sync method* — confirm the pill fires rather than trusting it would |
| T4 | `(observed, panes)` parity for `discover_window_panes_async` over `test_minimonitor_auto_close_guard.py`'s existing fixtures, as a parameterized base run twice (sync + async) so they cannot diverge. **The most important test here** — `observed=False` must stay UNVERIFIABLE, never EMPTY. | the existing `WITHOUT_OWN` / `(-1,"")` / `(1,"")` rows are the controls |
| T5 | `_get_desync_summary` not called when `_session_bar_enabled` is `False` (raising stub). | with the flag `True` it **is** called and its string reaches the bar text |
| T6 | `start_control_client` leaves the loop free: `backend.start` monkeypatched to `time.sleep(0.5)`, a concurrent 0.05 s ticker must advance ≥5 times. | pre-fix shape (direct `backend.start()`) yields a ticker count of 1 |
| T7 | `stale_lock.sh` — **the existing leaked-guard block at `:174-198` keeps its assertions**: its fixture is markerless and it calls `stale_lock_acquire` with four args, so the opt-in is off, and `assert_dir_exists`/`assert_not_contains "Removing stale"` now pin *"the core does not markerless-reclaim by default"* — the property the scoping rests on. Only the section comment changes. **New:** identity is published under the guard (park via the documented `STALE_LOCK_PUBLISH_FN` seam at `:261` — no shimming); dead-marker guard reclaimed with a **fresh** mtime (age irrelevant); markerless + backdated + opted-in succeeds. | **(a)** a live-marker guard, backdated, with the window explicitly ON → still never displaced (this is the `_fr_guarded` case made executable); **(b)** fresh markerless + window ON → refused; **(c)** backdated markerless with **no** 5th arg → refused, proving the opt-in is load-bearing |
| T7b | **Release and `guarded_section`, not just acquire** — `_stale_lock_gc_take` replaces the bare `mkdir` at **three** sites (`:251` acquire, `:373` guarded_section, `:410` release), so acquire-only coverage would let the core protocol pass while release still times out. (a) A dead-marker guard blocks `stale_lock_release` of a lock this shell **legitimately owns**: assert the guard is reclaimed, the release succeeds, the lock dir is gone, and no marker survives — today this path would exhaust its 40×0.05 s wait and return 1, stranding an owned lock. (b) Same for `stale_lock_guarded_section`: the section is actually **entered** and its fn runs. (c) **Signal-cleanup path** — `_stale_lock_guard_on_signal` (`:345`) must release **both** the marker and the guard; extend `tests/test_merge_lock_broker.sh:396` to assert the marker is gone too, not only `$gc`. | a **live**-marker guard must still block release (pinned warn `guard '<gc>' busy — lock '<lock>' NOT released`, `:413`) and still block `guarded_section` (`:376`) — the existing `:188-198` block is this control |
| T7c | **Marker classification is fail-closed by rule, not by accident** — one case per malformed row: `h.*` as a plain file, as a **dangling symlink** (the one that reads as markerless under a naive `-e` glob), a name like `h.abc.def`, two markers, and a non-`h.*` entry beside a valid marker. Each must refuse with its distinct warn and leave `$gc` byte-identical. | the genuinely-empty guard in the same fixture set **is** reclaimed when opted in — proving the classifier discriminates rather than refusing everything |
| T8 | Forced interleaving of the instance-keyed disarm: contender A parks **one-shot** inside `_stale_lock_pid_alive` holding a verdict on `h.<dead>.<nonceX>`; meanwhile a full disarm → `rmdir` → `mkdir` → publish `h.$$.<nonceY>` cycle completes. Unpark. Assert the fresh guard survives and its marker is **byte-identical** (`assert_eq`, not `!=`). Adapter-level: new `registry_lock.sh` case reproducing the exact production wedge end to end. | **mandatory** fixture-only `naive_gc_reclaim()` implementing the rejected `mv`-based path-keyed steal at the same seam — it **must destroy** the fresh live guard. If it does not, the construction discriminates nothing (the standard set by `test_registry_lock.sh:279-343`) |
| T8b | **Rolling-upgrade coexistence** — required, since the design claims it. Old code as fixture functions copied verbatim from the shipped primitives (`old_gc_take(){ mkdir "$1"; }`, `old_gc_release(){ rmdir "$1"; }`): (a) while new code holds, old `mkdir` fails and old `rmdir` fails **ENOTEMPTY** with the marker byte-identical; (b) after new code steals a markerless old guard, old `rmdir` returns **nonzero** — it discovers the theft rather than destroying our guard. | (c) old code holding a **fresh** markerless guard is not touched even with the window ON |
| T8c | **Structural guard for the invariant that licenses the scoping**: assert by grep that `stale_lock_guarded_section` has exactly one production caller (`aitask_merge_task.sh`), following the repo's existing drift-check idiom. If someone later adds a long guarded section to an opted-in lock, this fails — which is the only thing standing between the scoping argument and silent invalidation. | a fixture adding a second caller must make it fail |
| T9 | `tests/test_agent_marks_concurrency.sh` — **the ship gap**: it has no leaked-guard case at all, which is why this reached a user. Add wedge recovery (dead-pid lock + backdated markerless guard → `toggle` exits 0) with a **wall-clock bound** (`< 5 s`) that pins the reported 10.267 s as a test failure. Source `tests/lib/proc_fixtures.sh` (it currently sources only `asserts.sh`) and use `dead_pid_fixture`. Add a `list`-under-held-lock case for Step 7. | fresh guard → `LOCK_BUSY`, exit 3, store byte-identical |

**Live-boot test (`test_minimonitor_startup_*_live.py`): deliberately deferred.**
T2 fails deterministically on exactly the structural defect, in under a second,
with no tmux server. A live variant would cost a 45 s serial budget plus a
permanent two-file coordinated edit (`tests/run_all_python_tests.sh:94-95` **and**
the `serial-carve-out` marker block in `CLAUDE.md`, enforced by
`tests/test_serial_carveout_doc_drift.sh`). Recorded as a follow-up, not silently
omitted. Note for whoever picks it up: `dead_pid_fixture` is the **wrong** fixture
for wedging a lock — a dead holder is reclaimed and would not stall at all; a
live `sleep 120 &` holder is the sound shape.

## Risk

### Code-health risk: high
- The `.gc` steal protocol is subtle concurrent shell in a **load-bearing global
  mutex** shared by gate-ledger appends, child-task creation, the project
  registry, agent marks, shadow rejections, attachment locks and the merge
  broker. A defect does not degrade gracefully — worst case is two holders of one
  application lock, i.e. exactly the corruption the library exists to prevent.
  The bare-`rmdir` correctness argument at `:167-177` must be **re-derived**, not
  patched around. · severity: high (residual — baseline captured by inline
  pre-phase characterize_lock_baseline; the protocol itself is proven by T8's
  forced interleaving and its mandatory naive negative control) ·
  → mitigation: inline pre-phase characterize_lock_baseline
- Making `_check_auto_close` async moves a code path that **kills panes** onto a
  new concurrency regime, and its `(observed, panes)` contract already caused the
  2026-08-06 mass-quit incident when `unverifiable` was read as `empty`. ·
  severity: medium (residual — the port is written against a red parity suite by
  inline pre-phase autoclose_parity_test_first) ·
  → mitigation: inline pre-phase autoclose_parity_test_first
- Six doc sites plus the `merge-broker.md` Jinja source, its nine rendered
  mirrors and two golden suites publish the manual cure. A partial sweep leaves
  the framework telling users to run `rmdir '<lock>.gc'`, which now fails
  `ENOTEMPTY` against a marker-carrying guard. Protocol G shrinks this materially
  — `FREE_GUARD_PRESENT`, `stale_lock_describe`'s `-e` test and all six
  `assert_dir_not_exists … .gc` assertions are **unchanged**, and the new cure is
  still `rmdir`-only, so "never `rm -rf`" survives intact. · severity: low
  (residual — completeness asserted by inline post-phase
  guard_contract_doc_sweep) ·
  → mitigation: inline post-phase guard_contract_doc_sweep
- The new `_refresh_inflight` guard changes behaviour at ~12 keypress-driven
  refresh sites: a post-action refresh that lands mid-tick becomes a no-op rather
  than interleaving, so it can be up to one 3 s cadence late. · severity: low ·
  → mitigation: none

### Goal-achievement risk: medium
- The acceptance criterion asks that a wedged lock recover **without manual
  intervention**. Protocol G delivers that for **dead-marker guards everywhere by
  default**, and for **markerless guards only at opted-in lock dirs** — which
  includes the registry lock where the reported wedge actually occurred, and
  deliberately excludes the merge lock. Still manual: PID reuse, a
  cross-PID-namespace holder, and a hung live holder. The AC is met for the
  reported case, not universally, and the plan says so rather than implying
  otherwise. · severity: medium · → mitigation: none (documented residual)
- T2 proves the *pump* property with a synthetic stall; it does not prove a real
  boot is fast. · severity: low · → mitigation: live_boot_input_latency_test

### Planned mitigations
- timing: pre-phase | name: characterize_lock_baseline | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the `.gc` steal protocol in a load-bearing global mutex | desc: Record a verbatim PASS/FAIL baseline of the five lock suites before editing stale_lock.sh, so each deliberately-inverted assertion in T7/T8/T9 is provably intentional.
- timing: pre-phase | name: autoclose_parity_test_first | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — making the pane-killing `_check_auto_close` async | desc: Write the sync+async (observed, panes) parity suite and confirm the async half fails BEFORE writing discover_window_panes_async, so the port is developed against a red test.
- timing: post-phase | name: guard_contract_doc_sweep | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — nine rendered skill copies plus a golden publish the old guard contract | desc: Add an executable drift guard over scripts, all skill trees, aidocs and goldens that fails on the superseded UNIVERSAL claims only (never auto-broken / always empty / no heuristics / rmdir prescribed as the cure), explicitly permitting scoped R1+R4 manual-recovery language; assert the hit count and ship a positive control.
- timing: after | name: live_boot_input_latency_test | type: test | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement — T2 proves the pump property, not that a real boot is fast | desc: Live minimonitor boot in an isolated tmux pane against an isolated wedged AITASKS_AGENT_MARKS_FILE, asserting a key takes effect under budget; needs the coordinated SERIAL_CARVE_OUT + CLAUDE.md edit enforced by test_serial_carveout_doc_drift.sh.

## Deferred follow-ups (record on the task, do not silently drop)

1. Live wedged-lock boot test for minimonitor — **no longer a prose bullet**: it
   is the confirmed spawned mitigation `live_boot_input_latency_test`, created as
   an "after" task at Step 8d.
2. `minimonitor_app.py:1008` — the allowlisted ambient `subprocess.run(timeout=5)`
   in `on_mount`. Not a chokepoint violation; a real up-to-5 s startup blocker on
   a wedged tmux, but on the other side of a documented policy boundary.
3. `get_desync_summary_async` for the monitor's always-visible bar
   (`monitor_app.py:1518`).
4. Bounded guard wait in `stale_lock_acquire`, with the adapters'
   attempts-per-second constants re-derived in the same change.


## Final Implementation Notes

### Pre-phase 1 — `characterize_lock_baseline` (captured 2026-08-25, before any edit)

Verbatim summary lines from the five lock suites, on `main` at `6e91f5d28`,
**before** `stale_lock.sh` was touched:

| suite | result | exit |
|---|---|---|
| `tests/test_stale_lock.sh` | `Results: 79/79 passed, 0 failed` / `All tests PASSED` | 0 |
| `tests/test_registry_lock.sh` | `Tests: 51  Passed: 51  Failed: 0` | 0 |
| `tests/test_merge_lock_broker.sh` | `Results: 95/95 passed, 0 failed` / `All tests PASSED` | 0 |
| `tests/test_merge_lock_concurrency.sh` | `Results: 30/30 passed, 0 failed` / `All tests PASSED` | 0 |
| `tests/test_agent_marks_concurrency.sh` | `Results: 21/21 passed, 0 failed` / `All tests PASSED` | 0 |

All green. Protocol G predicts every one of these stays green — the existing
leaked-guard assertions use markerless, non-opted-in fixtures. Any red below is
therefore a real signal, not an expected inversion.
