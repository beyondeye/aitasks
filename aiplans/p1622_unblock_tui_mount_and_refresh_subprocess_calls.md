---
Task: t1622_unblock_tui_mount_and_refresh_subprocess_calls.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1622 — Unblock TUI mount and refresh subprocess calls

## Context

t1598 fixed a ~10 s startup input stall in `ait minimonitor` (the tick-1 marks
purge awaited inline on the App message pump). While enumerating blocking calls
on the mount and refresh paths it found four more sites and deliberately left
all four alone. Two of them are real latency bugs of the same family — **a
synchronous subprocess on a Textual path** — and are what this task fixes:

1. `monitor/minimonitor_app.py:1026` — `subprocess.run(["tmux", …], timeout=5)`
   inside `on_mount`. On a wedged tmux server this holds the entire mount, and
   therefore the first paint and the first input dispatch, for up to five
   seconds. t1598 skipped it because it probes the **ambient** tmux server
   before `self._monitor` exists, so routing it through the default gateway
   client would query the `-L ait` socket instead.
2. `monitor/monitor_app.py:1552` — `_rebuild_session_bar` calls
   `get_desync_summary`, which spawns a fresh Python interpreter (2 s cap,
   30 s TTL cache) synchronously on the full monitor's refresh path. Minimonitor
   dodged this in t1598 by gating the call on `_session_bar_enabled` (its bar
   defaults to hidden), but the full monitor **always** shows its bar, so the
   string is genuinely needed and the call has to become async instead.

A third site rides along because leaving it out would make the outcome untrue
for a supported configuration: `minimonitor_app.py:1704` calls the same
synchronous `get_desync_summary`, gated on `_session_bar_enabled`. That gate is
what t1598 shipped instead of a fix, and it defaults to `False` — but
`tmux.minimonitor.session_bar: true` is a supported setting, and with it on,
minimonitor's refresh path can wait the full 2 s cap on a cache miss. Once
Part B builds the async reader, porting that call is three lines (**B3**).

Outcome: neither TUI's mount or refresh path holds the event loop on a
subprocess again — including with minimonitor's session bar enabled.

## Explicitly out of scope

Recorded here so the deviation is visible rather than silent:

- **`lib/stale_lock.sh:acquire` bounded guard wait** and the **hand-rolled
  dead-pid fixture in `tests/test_agent_marks_concurrency.sh:~126`** — the task
  lists these as *recorded judgement calls*, not work items: t1598 considered
  and rejected both, with reasons, and they are written down so the reasoning is
  not lost. Nothing here touches them.
- **`lib/tui_switcher.py:_fetch_desync_summary`** — a separate, pre-existing
  reimplementation of the same probe for the switcher overlay. It runs in the
  switcher's own worker, not on a monitor path. Untouched.
- **`TmuxClient.run_async`'s own cancellation gap** (`lib/tmux_exec.py:218`) —
  it catches `asyncio.TimeoutError` but not `CancelledError`, so a cancelled
  gateway call can orphan a `tmux` child exactly as B1 fixes for the desync
  helper. Pre-existing, affects every gateway caller, and widening this task to
  the shared gateway is a bigger blast radius than it warrants. **Tracked as
  t1628** (`bug`, `followup_kind: upstream_defect`, `anchor: 1598`), created
  during Step 8 review — a residual noted only in prose is not tracking, and
  A2's seed worker is a newly cancellable caller of exactly this path.

---

## Part A — minimonitor mount probe (`minimonitor_app.py`)

**Approach: dispatch the probe as a worker instead of awaiting it inline.**

The task suggests either lowering the timeout to 2 s or dropping the probe
entirely. Lowering it leaves a 2 s mount blocker; dropping it leaves
`_own_window_{id,index,name}` unset until the **end** of the first refresh (that
refresh does a full multi-pane tmux capture first), and three keypress handlers
read those fields — `_find_sibling_pane_id`, `action_switch_to_monitor`,
`_find_own_window_snapshot`. Dispatching the same query as a worker removes the
mount block completely *and* answers sooner than the first tick would.

### A1. New coroutine, beside `_update_own_window_info` (~line 1359)

```python
    async def _seed_own_window_info(self) -> None:
        """Populate `_own_window_{id,index,name}` off the mount path (t1622).

        The mount-time sibling of `_update_own_window_info`, and deliberately
        NOT a call into it: that one routes through `self._monitor`, which does
        not exist yet when this is dispatched, and whose client is pinned to the
        dedicated `-L ait` socket (t953). These three fields describe THIS pane
        on the server we are attached to, so the query must follow ambient
        `$TMUX` resolution — which is exactly what `TmuxClient(socket_args=[])`
        is: the gateway with no `-L` flag, building the same argv the raw
        `subprocess.run` did.

        **`socket_args=[]` is load-bearing, not tidiness.** A bare
        `TmuxClient()` reads `tmux_socket_args()` and pins the call to `-L ait`;
        against a pane on any other server that returns rc=1 and all three
        fields stay `None` — a silent degradation (refusals from `m` / `k`,
        auto-close permanently disabled) with no error anywhere. Pinned by
        `test_the_seed_queries_the_ambient_server_for_its_own_pane`.

        **Seeds, never overwrites.** The refresh tick re-derives all three every
        interval and this worker can land after it (a slow tmux answer, a
        `renumber-windows` in between). Writing only a field that is still
        `None` makes the two writers order-independent: the tick always owns the
        current value, and this only fills what has not been answered yet.

        Timeout 2 s, matching `_update_own_window_info`. The old 5 s was the
        blocking call's own budget; there is no reason for a seed to wait longer
        than the tick that supersedes it.
        """
        own_pane = os.environ.get("TMUX_PANE", "")
        if not own_pane:
            return
        rc, stdout = await TmuxClient(socket_args=[]).run_async(
            ["display-message", "-p", "-t", own_pane,
             "#{window_id}\t#{window_index}\t#{window_name}"],
            timeout=2,
        )
        if rc != 0 or not stdout.strip():
            return
        parts = stdout.strip().split("\t")
        if len(parts) >= 1 and self._own_window_id is None:
            self._own_window_id = parts[0]
        if len(parts) >= 2 and self._own_window_index is None:
            self._own_window_index = parts[1]
        if len(parts) >= 3 and self._own_window_name is None:
            self._own_window_name = parts[2]
```

`TmuxClient.run_async` (`lib/tmux_exec.py:201`) already gives the whole
contract: `(rc, stdout)`, `(-1, "")` on `FileNotFoundError` / `OSError` /
timeout, and kill-and-reap of the child on timeout. Nothing new is written.

It also carries the cancellation gap listed under "out of scope": cancelling
this seed worker at app exit leaves its `tmux display-message` child unreaped.
That is a sub-second, self-terminating child rather than the 2 s Python
interpreter B1 fixes, which is why it rides along with the shared-gateway
follow-up instead of being special-cased here — but it is inherited, not absent.

### A2. `on_mount` (~lines 1022–1041) — replace the `try/subprocess.run/except`

```python
        # Detect own window ID, index, and name for auto-close, auto-selection,
        # and the "switch to full monitor" handoff. DISPATCHED, not awaited
        # (t1622): this was a synchronous `subprocess.run(..., timeout=5)`, so a
        # wedged tmux server held the whole mount — first paint and first input
        # with it. `run_worker` is `asyncio.create_task`, the only dispatch that
        # genuinely escapes the App message pump (see `_start_monitoring`).
        # Dispatched BEFORE `_start_monitoring()` so the fields land as early as
        # tmux can answer rather than at the end of the first refresh.
        self.run_worker(
            self._seed_own_window_info(),
            name="own_window_seed",
            group="own-window-seed",
            exclusive=False,
            exit_on_error=False,
        )
```

### A3. Import

Add `from tmux_exec import TmuxClient  # noqa: E402` to the local-import block
(`lib/` is already on `sys.path` at line 27). The module-level
`_detect_tmux_session()` keeps its own `subprocess.run` — it runs in `main()`
before the App exists, so it is not on a Textual path.

---

## Part B — full monitor's desync summary

### B1. `monitor/desync_summary.py` — grow to a three-reader surface

One shared `_cache`, three readers with explicitly different blocking
contracts:

- `get_desync_summary` — unchanged sync fetcher (still used by
  `minimonitor_app.py`).
- **`get_desync_summary_async(project_root, *, compact=False)`** — new. Same
  TTL-cache logic, `await`s `_fetch_async`.
- **`get_desync_summary_cached(project_root, *, compact=False)`** — new,
  never spawns. Returns the last computed string for this root/variant, or `""`.

`_fetch_async` mirrors `_fetch` using `asyncio.create_subprocess_exec` +
`asyncio.wait_for`, and returns `""` on `FileNotFoundError` / `OSError` /
timeout / non-zero exit. Both fetchers take their cap from **one** new
`_TIMEOUT_SECONDS = 2` constant — `_fetch` currently hardcodes `2` inline.
New imports: `asyncio`, `contextlib`.

**Cancellation is a second exit, not a variant of the timeout.** `wait_for`
cancels the inner `communicate()` and re-raises `CancelledError` **without**
touching the child, and Textual cancels the refresh worker when the app exits —
so a plain `except asyncio.TimeoutError` leaks a live Python interpreter past
the TUI it belonged to. Both exits share one reaper:

```python
async def _terminate(proc) -> None:
    """SIGKILL and reap. Called from BOTH the timeout and the cancel path."""
    with contextlib.suppress(ProcessLookupError):
        proc.kill()
    with contextlib.suppress(Exception):
        await proc.wait()
```

```python
    try:
        stdout_bytes, _ = await asyncio.wait_for(
            proc.communicate(), timeout=_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        await _terminate(proc)
        return ""
    except asyncio.CancelledError:
        # App shutdown cancels the refresh worker mid-flight. Kill BEFORE the
        # re-raise and never swallow the CancelledError: `kill()` is synchronous
        # so the signal lands even if the reaping `await` is cancelled in turn,
        # and by then the child is already dying.
        await _terminate(proc)
        raise
```

`get_desync_summary_cached` **ignores the TTL on purpose**, and its docstring
says why: the TTL decides when to *re-fetch*, which only the fetching readers
can do. Expiring the value here as well would blank a still-true desync warning
the instant the user pressed a key, and repaint it one tick later. The
refreshing caller keeps the entry within one TTL of the truth. A cached entry
recorded under the other `variant` is not reusable and returns `""`.

Update the module docstring to name the three readers and the rule: **any
Textual path uses the async or the cached reader; the sync one is for callers
that own their own thread.**

### B2. `monitor/monitor_app.py`

- Line 61: replace the sync import with the two new readers. Dropping
  `get_desync_summary` from this module's namespace is the structural half of
  the fix — the blocking version is no longer reachable from here by name.
- `_rebuild_session_bar` (line 1526) gains a `desync: str | None = None`
  keyword, defaulted in the callee so the existing no-arg call sites keep
  working. Replace the inline fetch (lines 1551–1554) with:

  ```python
        # Pre-fetched by `_refresh_data` (t1622). `None` means this call brought
        # none — the keypress-driven rebuild in `action_toggle_auto_switch` —
        # so read the cache instead of spawning: the summary costs a fresh
        # Python interpreter and this is a synchronous handler.
        if desync is None:
            try:
                desync = _get_desync_summary_cached(Path.cwd(), compact=False)
            except Exception:
                desync = ""
  ```

  The `try/except Exception` is kept deliberately: it preserves the exact
  failure containment the replaced code had.
- `_refresh_data` (~line 1058) pre-fetches immediately before the rebuild:

  ```python
            # Off the render path (t1622): on a cache miss the sync reader ran a
            # fresh Python interpreter inline inside `_rebuild_session_bar`.
            # Awaited here because `_refresh_data` is already a worker task —
            # this suspends the tick, not the App message pump. The `except`
            # keeps a probe failure a blank string rather than a dead tick, as
            # before.
            try:
                desync = await _get_desync_summary_async(Path.cwd(), compact=False)
            except Exception:
                desync = ""
            self._rebuild_session_bar(attached_session, desync=desync)
  ```

`action_toggle_auto_switch` (line 2770) needs no edit — its no-arg call now
lands on the cached path automatically.

### B3. `monitor/minimonitor_app.py` — port the gated call

The same three edits, one gate narrower. `_rebuild_session_bar` (line 1674)
takes `desync: str | None = None` and falls back to
`_get_desync_summary_cached(..., compact=True)`; `_refresh_data` (~line 1277)
pre-fetches **inside the existing `_session_bar_enabled` condition** — the gate
stays, it is still right not to compute a string nobody renders, and moving the
fetch off the render path is what makes the enabled case free too:

```python
            desync = ""
            if self._session_bar_enabled:
                try:
                    desync = await _get_desync_summary_async(Path.cwd(), compact=True)
                except Exception:
                    desync = ""
            self._rebuild_session_bar(desync=desync)
```

The import at line 73 swaps to the async + cached pair, so — as in `monitor_app`
— the blocking reader is no longer reachable by name from either TUI. Rewrite
the `# Gated on the FLAG …` comment at line 1694: the gate now saves the work,
not a stall. Line 1277 is the sole in-source caller; the suites that call
`_rebuild_session_bar()` directly land on the cached path and get `""`, which is
effectively what they already got.

---

## Tests

**No test added or touched here spawns, attaches to, or kills a real tmux
server.** Part A's tests patch `mm.TmuxClient` wholesale, so no `tmux` process
is ever created; the desync tests spawn a Python stub script and reap only that
one child, by the pid it reports. Nothing sends a signal to a pid it did not
create, so the tmux session this work is being done in is never a target.

### `tests/test_minimonitor_startup_input_latency.py` (+5, and extend the header table)

This file already owns the "first refresh must not run on the App pump" story
and its positive-control table; the mount probe is the same story one step
earlier. Tests 1–4 need `TMUX` / `TMUX_PANE` set for the run (the module pops
them at import so `on_mount` takes the not-inside-tmux early return) and a fake
patched over `mm.TmuxClient` — the same patch-the-module-symbol shape the
existing test uses for `mm.TmuxMonitor`. Test 5 parses source and needs
neither.

1. `test_the_mount_window_probe_is_dispatched_as_a_worker` — structural pin.
   Spy `app.run_worker`, drive the real `on_mount`, assert `own_window_seed` is
   among the dispatched names.
2. `test_mount_returns_while_the_window_probe_is_still_blocked` — behavioral.
   With the stalling fake installed, `on_mount()` must return, and a keypress
   must be dispatched inside `INPUT_BUDGET_S`, **while the probe's gate is still
   closed**. Wait on the fake's `entered` event first, and release the gate in a
   `finally` (a hanging regression test is worse than none — the existing suite
   learned this the hard way).
3. `test_the_seed_never_overwrites_a_field_the_tick_already_set` — pin **both**
   directions: pre-set `_own_window_id`, run the coroutine against a fake
   returning different values, assert the pre-set field is unchanged and the two
   `None` fields are filled.
4. `test_the_seed_queries_the_ambient_server_for_its_own_pane` — the socket and
   target contract, which nothing above covers. The fake records its
   **constructor kwargs** and its `run_async` arguments, and asserts on the
   **resolved argv** rather than the kwargs alone (`["tmux", *socket_args,
   *args]`), so `socket_args=None` — which silently resolves to `-L ait` — fails
   just as loudly as passing it explicitly:
   - no `-L` anywhere in the argv, and `AIT_DEDICATED_SOCKET` ("ait") absent;
   - the command is `display-message -p -t <TMUX_PANE> #{window_id}\t
     #{window_index}\t#{window_name}`, with the target read from the env at call
     time (set a distinctive `TMUX_PANE` and assert *that* value appears);
   - `timeout == 2`.
5. `test_on_mount_issues_no_synchronous_subprocess` — the structural guard
   `test_no_raw_tmux.sh` cannot provide (see the note below). Parse
   `minimonitor_app.py` with `ast`, locate the `on_mount` `FunctionDef` in the
   `MiniMonitorApp` class, and assert no `Call` in its body resolves to
   `subprocess.run` / `subprocess.Popen` / `subprocess.check_output`. `ast`, not
   grep: a grep for `subprocess.run` matches the comment that explains why it is
   gone. Scoped to this one function on purpose — `_detect_tmux_session` legitimately
   keeps its synchronous call.

Also update the file's allowlist reason in `tests/test_no_raw_tmux.sh:54` —
it currently reads `# B/ambient _detect probe + self display-message`, and the
"self display-message" half is precisely what A2 removes. It becomes
`# B/ambient _detect probe (main(), pre-App)`.

Positive controls to add to the header table: reverting A2 to `subprocess.run`
fails (2) — the fake is never consulted, so `entered.wait()` times out — and
fails (5) directly, by name; dropping the `is None` guards fails (3); a bare
`TmuxClient()` fails (4).

### `tests/test_monitor_refresh_no_sync_tmux.py` (+2)

Its `_FakeRefreshMonitor` already drives `_refresh_data` end-to-end.

6. `test_the_session_bar_desync_string_is_prefetched_asynchronously` — patch
   `monitor_app._get_desync_summary_async` to an async fn returning a sentinel
   and recording its call; patch `desync_summary._fetch` to raise
   (`AssertionError("spawned on the refresh path")`); run `_refresh_data`;
   assert the sentinel is in the bar text and the sync fetcher never ran.
7. `test_the_keypress_rebuild_reads_the_cache_and_never_spawns` — seed
   `desync_summary._cache[str(Path.cwd())] = (time.monotonic(), sentinel,
   "full")`, patch `desync_summary._fetch` **and** `_fetch_async` to raise, call
   `action_toggle_auto_switch()`, assert the sentinel reached the bar. Restore
   the cache in `addCleanup` — it is module state shared with other tests.

### `tests/test_desync_summary_cache.py` (new)

Unit contract for the module itself, with no TUI in the way. Clear `_cache` in
`setUp`/`tearDown`.

8. `get_desync_summary_cached` returns `""` on an empty cache.
9. `get_desync_summary_async` populates the cache and a second call inside the
   TTL reuses it without re-spawning (patch `_fetch_async` and count calls).
10. `get_desync_summary_cached` returns the entry for a matching `variant` and
   `""` for the other one.
11. `_fetch_async` returns `""` and reaps the child when the helper outlives
   `_TIMEOUT_SECONDS` — drive it against a stub helper script that sleeps and
   writes its pid to a temp file, with `_TIMEOUT_SECONDS` and `_HELPER` patched.
   Assert the return is `""` **and** that the recorded pid is gone (bounded
   poll on `os.kill(pid, 0)` raising `ProcessLookupError`); "returned empty" on
   its own does not prove the child died.
12. `test_a_cancelled_fetch_kills_its_child_and_reraises` — the second exit.
    Run `_fetch_async` as a task against the same stub helper, wait for the pid
    file to appear (so cancellation lands with a real child in flight, not
    before the spawn), `task.cancel()`, assert `CancelledError` propagates —
    `assertRaises(asyncio.CancelledError)` on the await, so a swallowed
    cancellation fails — and that the pid is gone within a bounded poll.
    Positive control: drop the `except asyncio.CancelledError` clause and this
    test must fail on the surviving child, not on the exception.

### `tests/test_minimonitor_top_chrome_render.py` (B3 coverage)

13. `test_the_enabled_session_bar_desync_is_prefetched_not_spawned` — this file
    already builds a minimonitor with `_session_bar_enabled` in both states
    (see its `True` / `False` fixture at lines 203–225). Patch
    `desync_summary._fetch` to raise, run `_refresh_data` with the bar enabled,
    and assert the pre-fetched sentinel reaches the bar — i.e. the enabled
    configuration no longer spawns from the render path. Pair it with the
    disabled case asserting `_get_desync_summary_async` is not awaited at all,
    so the gate is pinned in both directions.

### Post-phase (risk mitigations)

Runs after Parts A and B and their tests are in place, before the verification
sweep. Both were confirmed as inline phases rather than spawned tasks.

1. `[pin_own_window_consumer_refusals]` Add a test class to
   `tests/test_minimonitor_startup_input_latency.py` covering the three
   keypress consumers of `_own_window_{id,index,name}` while all three are
   still `None` — the state Part A makes genuinely reachable:
   `_find_own_window_snapshot()` returns `None`; `_find_sibling_pane_id()`
   returns `None` and notifies (never returns a pane id — a wrong sibling here
   is how t1382's shadow-pane hazard resurfaces); `action_switch_to_monitor()`
   returns without issuing any tmux call. Drive the real methods with a fake
   monitor that records calls, and assert on the *refusal*, not just the
   absence of a crash.
2. `[fix_sibling_pane_refusal_message]` In `_find_sibling_pane_id`
   (`minimonitor_app.py:~2238`), split the conflated refusal: keep
   `"Not inside tmux"` for a missing `TMUX_PANE`, and report
   `"Own window not detected yet"` when `_own_window_id` is simply not seeded
   yet — the wording `action_switch_to_monitor` already uses for the same
   state. Extend step 1's test to assert the message, so the two refusal
   reasons cannot re-merge.

## Verification

```bash
# The two directly affected suites plus the new one
python3 tests/test_minimonitor_startup_input_latency.py
python3 tests/test_monitor_refresh_no_sync_tmux.py
python3 tests/test_desync_summary_cache.py

# Allowlist-comment edit still parses. NOTE: this script does NOT guard Part A —
# it allowlists minimonitor_app.py wholesale, so a revert to
# `subprocess.run(["tmux", ...])` in on_mount would pass it unchanged. Test 5 is
# the guard for that; this run only confirms nothing else regressed.
bash tests/test_no_raw_tmux.sh

# Neighbours that touch the changed fields / the session bar
python3 tests/test_minimonitor_auto_close_guard.py
python3 tests/test_minimonitor_top_chrome_render.py
python3 tests/test_minimonitor_session_bar_config.py
python3 tests/test_monitor_completed_status.py
python3 tests/test_markup_colour_contract.py
bash tests/test_multi_session_minimonitor.sh

# Whole Python suite (read ONLY the last line for the verdict)
bash tests/run_all_python_tests.sh
```

Live check (the thing the fixtures cannot prove): run `ait minimonitor` beside
an agent and `ait monitor` in another window — both must paint and accept input
immediately, minimonitor's `m` / `k` must still resolve the sibling pane, and
the monitor's session bar must still show `desync: …` when the data branch is
behind.

## Risk

### Code-health risk: medium

- Field-availability timing changes: `_own_window_{id,index,name}` are no longer
  set synchronously at mount, so a keypress landing in the window before the
  seed worker answers gets a "not detected yet" refusal from
  `action_switch_to_monitor` / `_find_sibling_pane_id`. · severity: medium ·
  → mitigation: inline post-phase pin_own_window_consumer_refusals,
  inline post-phase fix_sibling_pane_refusal_message
- The seed worker and the per-tick `_update_own_window_info` write the same
  three fields, so a slow seed landing after a `renumber-windows` could
  overwrite a fresher value. · severity: low · → mitigation: none needed — the
  seed's `is None` guards make the two writers order-independent, pinned in both
  directions by test 3.
- `desync_summary` grows from one public reader to three over a shared cache; a
  later caller on a Textual path could reach for the blocking one. · severity:
  medium · → mitigation: none needed — `get_desync_summary` is dropped from
  `monitor_app.py`'s namespace, test 6 fails if the refresh path spawns, and the
  module docstring states the rule.
- `_check_auto_close` is safety-critical (t1446: a machine-wide tmux stall once
  made every minimonitor quit at once) and reads `_own_window_id`. · severity:
  low · → mitigation: none needed — it is guarded on that field being non-`None`
  *and* grace-gated to 5 s past mount, so a late seed makes it return early, not
  quit.
- B3 extends the change to a second live TUI's refresh path rather than only the
  one the task names, so the blast radius is four source files, not three.
  · severity: low · → mitigation: none needed — it is the same three-line edit
  against the same new reader, the `_session_bar_enabled` gate is preserved
  unchanged, and test 13 pins the gate in both directions.
- `_fetch_async`'s correctness now depends on a reaper running inside a
  `CancelledError` handler, where a further await can itself be cancelled.
  · severity: low · → mitigation: none needed — `proc.kill()` is synchronous, so
  the signal lands before any await can be interrupted; the reap is
  best-effort on top. Test 12 pins both the re-raise and the dead child.
- `TmuxClient.run_async` keeps the identical cancellation gap, so the same
  orphan class survives for every gateway caller — and A2's seed worker is a new
  caller of it that Textual cancels at app exit. · severity: medium ·
  → mitigation: **t1628** (created during Step 8 review). This task fixes the
  desync helper only; the gateway instance is durably tracked rather than left
  as prose.

### Goal-achievement risk: low

- `get_desync_summary_cached` can serve a stale string on the keypress path.
  · severity: low · → mitigation: none needed — accepted residual, documented in
  the docstring. The refresh tick re-fetches on TTL expiry, so the bar is at
  most one TTL plus one tick behind, and the alternative (blanking on keypress)
  is strictly worse.

### Planned mitigations
- timing: post-phase | name: pin_own_window_consumer_refusals | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (own-window fields no longer set synchronously at mount) | desc: regression test pinning that all three keypress consumers of `_own_window_*` refuse visibly, never crash and never resolve a wrong pane, while the fields are still None
- timing: post-phase | name: fix_sibling_pane_refusal_message | type: bug | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (user-visible half) | desc: `_find_sibling_pane_id` reports "Not inside tmux" for a merely-unseeded own window; split it from the genuine no-TMUX_PANE case and use `action_switch_to_monitor`'s existing wording

**Levels reassessed against the augmented plan** (per `risk-evaluation.md`'s
reassessment note): both inline phases are bounded and independently verifiable,
so they lower risk 1's severity without changing the blast radius or the
dual-writer surface. Code-health stays **medium**; goal-achievement stays
**low**.

---

## Implementation notes

All parts landed as planned. Deviations and findings worth carrying forward:

- **Part A / A1.** `TmuxClient.run_async` is used exactly as designed. The
  docstring's ambient-socket rationale is pinned by
  `test_the_seed_queries_the_ambient_server_for_its_own_pane`, which asserts on
  the **resolved argv** and additionally pops `AITASKS_TMUX_SOCKET` first — the
  first draft passed under an environment where the default already resolves to
  no flag, i.e. it could not have failed. The precondition assertion is what
  makes it falsifiable.
- **B3 / tests.** `tests/test_minimonitor_top_chrome_render.py` does **not**
  scrub `TMUX` at import (unlike the other two suites), so the new class scrubs
  it in `setUp`. Without that, `run_test`'s own `on_mount` took the in-tmux path,
  built a real `TmuxMonitor` (and a live `tmux -C attach`) and left
  `_refresh_inflight` set, so the assertions read an untouched bar. Same trap
  reordered the env setup in the two `MountWindowProbeTests` cases.
- **Test 7 fixture.** Seeding the desync cache with a *fresh* entry made the test
  non-discriminating: the blocking `get_desync_summary` serves a fresh entry too,
  so the regression passed. The entry is now deliberately TTL-expired, which is
  the only state that separates the cached-only reader from the blocking one.
- **Post-phase mitigations.** Both applied:
  `pin_own_window_consumer_refusals` → `OwnWindowNotYetSeededTests` (5 tests);
  `fix_sibling_pane_refusal_message` → `_find_sibling_pane_id` now reports
  "Own window not detected yet" separately from "Not inside tmux", pinned in both
  directions.

**Positive controls executed** (each mutation confirmed to fail the named test,
then reverted): `on_mount` back to `subprocess.run`; a bare `TmuxClient()`; the
`is None` seed guards dropped; the two sibling refusals re-merged; the desync
pre-fetch not passed to `_rebuild_session_bar`; the bar builder back on the
blocking reader; `_fetch_async`'s `except asyncio.CancelledError` removed.

**Live verification.** Booted both TUIs against the real ambient tmux server
inside this session: minimonitor mount+boot 11 ms with the seed resolving this
pane's window correctly (`@125 / 2 / agent-pick-1622`); full monitor refresh
23 ms with the session bar rendered and the desync cache populated by the async
reader.

**Suite:** `PYTHON SUITE: PASSED (runner=pytest, exit=0)` — 5365 passed,
2 skipped, plus the 5 serial live modules.

## Post-Review Changes

### Change Request 1 (2026-08-26 09:40)
- **Requested by user:** `tests/test_desync_summary_cache.py` created scratch
  directories with `tempfile.mkdtemp()` and registered no cleanup, stranding
  several per run in `/tmp`. Asked to use `TemporaryDirectory` / cleanup
  callbacks while keeping the post-test child-liveness assertions.
- **Verified:** CONFIRMED, and worse than "several" — three call sites
  (`_CacheIsolated.setUp`, `_stub_helper`, and both pid-file sites) × 10 tests.
  Measured: **15 stranded `/tmp` entries per run**.
- **Changes made:** Introduced one `_CacheIsolated._tmpdir()` helper returning a
  `tempfile.TemporaryDirectory` registered via `addCleanup`, and routed all four
  call sites through it. `addCleanup` fires *after* the test body, so every
  child-liveness assertion still runs against a live pid file. Re-measured: **0
  stranded entries**. Fixed in place rather than deferred — it is a leak in a
  file authored by this task, and committing a known leak in order to file a
  follow-up would be the worse trade.

### Change Request 2 (2026-08-26 17:35)
- **Requested by user:** The plan documents `TmuxClient.run_async`'s
  `CancelledError` gap (`lib/tmux_exec.py:218`) as a residual, but creates no
  follow-up task — so the exposure this task *newly widened* (the mount seed at
  `minimonitor_app.py:1405` is a `run_worker` task Textual cancels at app exit)
  is not durably tracked.
- **Verified:** CONFIRMED. `run_async` catches only `asyncio.TimeoutError`;
  `wait_for` cancels the inner `communicate()` and re-raises without touching the
  child. A prose residual is not tracking.
- **Changes made:** Created **t1628** — `bug`, medium/low,
  `followup_kind: upstream_defect`, `anchor: 1598` (same topic group as t1598 /
  t1622), `gates: [risk_evaluated]` — carrying the defect location, the widened
  path, the two-exit fix shape, and a verification recipe pointing at this task's
  `FetchAsyncChildLifecycleTests` as the proven pattern (plus the "never signal a
  pid you did not create / do not spawn a real tmux server" constraint). The
  plan's out-of-scope entry and its `## Risk` bullet now name t1628 instead of
  deferring to "flagged at Step 8d".
- **Not fixed here, deliberately:** the user's stated disposition was
  *follow-up*, and the gateway is shared by every async caller — a blast radius
  this task's review did not cover.
