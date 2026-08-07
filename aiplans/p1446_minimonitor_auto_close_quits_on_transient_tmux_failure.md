---
Task: t1446_minimonitor_auto_close_quits_on_transient_tmux_failure.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1446 — minimonitor auto-close must not fire on an unverifiable tmux observation

## Context

On 2026-08-06 21:46:15–16, during a machine-wide stall, **every** `ait minimonitor`
companion pane across three tmux sessions exited voluntarily while the coding agents
they were watching kept running. No python process appears among the kernel's OOM
victims — they quit themselves.

The mechanism is a fail-open on an unverifiable signal, in three hops:

1. `lib/tmux_exec.py:163-179` — `TmuxClient.run` returns `(-1, "")` on timeout /
   `OSError` (default timeout 5 s).
2. `monitor/monitor_core.py:1752-1765` — `discover_window_panes` collapses **any**
   `rc != 0` into `[]`. A timed-out query and a genuinely empty window become the
   same value. (`tmux_run` itself already documents a tri-state `rc`: `0` success,
   `1` tmux error, `-1` transport failure — `monitor_core.py:1386-1389`. That
   distinction is thrown away here.)
3. `monitor/minimonitor_app.py:511-519` — `_check_auto_close` reads `[]` as "no other
   panes remain in my window" and calls `self.exit()`. The only guard is a 5 s
   post-mount grace (`:484`), which does nothing for a long-lived process.

A stall pushes the 5 s timeout over the edge in every minimonitor at once, so they
all quit within the same second. `_check_auto_close` exists **only** in minimonitor —
it is the sole discriminator between the panes that died and the `ait monitor` /
`ait board` panes of the same age that survived.

The intended outcome: auto-close fires only on a **positively observed** "I am the
only pane left in this window", and never on an observation the process could not
make.

## Audit of the conflation surface (AC #2)

`discover_window_panes` has exactly **one** production caller and **one** test stub
in the whole repo:

| Site | Today | Disposition |
|---|---|---|
| `minimonitor_app.py:515` (`_check_auto_close`) | fatal — `[]` → `self.exit()` | fixed here |
| `tests/test_monitor_modal_space_dispatch.py:93` (`_FakeMonitor` stub) | harmless (that fake's `capture_all_async` returns `None`, so the tick returns early at `minimonitor_app.py:457` and never reaches the check) | updated to the new shape |

The correct shape already exists twice in this codebase and is what the fix follows:
`monitor_core.find_shadow_pane_status` (`:398-417`) returns an explicit `(ok, value)`
pair precisely so a failed query cannot gate a spawn, and
`minimonitor_app._find_sibling_pane_id` (`:1089-1101`) — 400 lines from the bug —
already distinguishes "tmux list-panes failed" from "no other pane in this window".

**Out of scope, recorded for follow-up (not fixed here):**
- `monitor_core.get_pane_option` (`:1410-1425`) returns `""` on `rc != 0`;
  `compute_shadow_staleness` (`:538-540`) reads that as "shadow has not analyzed
  anything yet: nothing to warn about" — a tmux failure suppresses a staleness
  warning. Same class, different function.
- `discover_window_panes` is a **sync** `tmux_run` on the async refresh path, so the
  same 5 s stall blocks Textual's event loop. `tests/test_monitor_refresh_no_sync_tmux.py`
  encodes the "no sync tmux on the refresh loop" invariant (t1111_3) but does not
  reach this call. **Tracked, not merely described:** it is recorded as the `after`
  mitigation `async_window_pane_discovery` in `### Planned mitigations` below, which
  Step 8d **creates as a real follow-up task** in this same session and links back
  into t1446's `risk_mitigation_tasks` frontmatter. It blocks nothing, so this task
  still lands on its own.

  **Re-verified against the implemented code (post-implementation review):** the
  call is still `self.tmux_run([...])` at `monitor_core.py:1779` with no `timeout=`
  argument, i.e. the 5.0 s default, reached from the async `_refresh_data` via the
  sync `self._check_auto_close()` at `minimonitor_app.py:499`. So a stalled tmux can
  still freeze the minimonitor UI for up to 5 s per tick — it just can no longer
  *close* it, which is what t1446's acceptance criteria require. Disposition
  unchanged: informational, out of scope here, and delivered by
  `async_window_pane_discovery`. **Creation must be confirmed at Step 8d** — the
  `timing: after` line below is its input, and the run is complete only once that
  line carries a `created: t<id>` witness and the id appears in the task's
  `risk_mitigation_tasks`.

## Design decisions

**Return shape: `(observed, panes)` pair, not `list | None`.** With `| None`, a future
caller writing the natural `if not panes: exit()` re-creates this exact bug — `None`
is falsy. A 2-tuple cannot be consumed without binding the flag, and any stale caller
that keeps treating the result as a list fails loudly (it would iterate a `bool`).

**Only `rc == 0` is an observation.** `rc == 1` (tmux command error, e.g. "can't find
window") is also treated as unverifiable. Exiting on it buys nothing — if the window
is genuinely gone, our pane is gone with it and the process dies anyway — and it
closes off a whole class of tmux-error-shaped false positives.

**A partially-parsed listing is not an observation either.** `discover_window_panes`
silently drops any line that does not split into exactly 8 tab-separated fields, or
whose pid/width/height are not integers (`:1768-1777`, two bare `continue`s). If tmux
answers `rc == 0` with our own row intact but a **sibling row truncated or garbled**
— a partially flushed listing, or a window name containing a tab — the sibling
vanishes from the result and the caller sees exactly the same value as genuine
solitude. A self-sighting rule alone does **not** catch this: our row is present, so
the listing looks like a positive "I am alone". Therefore `observed` means *tmux
answered **and** every non-blank line parsed*: one dropped record makes the whole
listing unverifiable. Completeness is decided at the parser, which is the only place
that can see the drop.

**The caller additionally demands a positive self-sighting.** Auto-close requires a
complete listing that contains our own pane and nothing else. This is defense in depth
behind the completeness flag (it also covers a well-formed listing that simply does
not mention us), and it preserves today's behavior when `TMUX_PANE` is unset
(auto-close never fires).

**Confirmed with the user during planning:**
- **N = 2 consecutive verified-empty observations** before exiting (~3 s extra pane
  lifetime at the default 3 s refresh). Cheap insurance against an unknown single-tick
  glitch; any non-empty *or* unverifiable observation resets the streak.
- **Persistent failure never closes the pane.** There is no failure budget that
  eventually exits — that would reintroduce t1446 with a longer fuse. Worst case is a
  stale companion pane the user closes with `q`, which is strictly better than
  silently losing a live one.

## Implementation

### 1. `.aitask-scripts/monitor/monitor_core.py` — `discover_window_panes` (`:1752-1792`)

Change the signature to `-> tuple[bool, list[TmuxPaneInfo]]`.

- `rc != 0` → `(False, [])`.
- `rc == 0` → parse as today, but track completeness: replace each bare `continue`
  (`:1771`, `:1777`) with one that first sets a local `complete = False`. Blank lines
  are skipped **without** clearing the flag. Return `(complete, panes)`.

So a listing with any unparseable record returns `observed=False` **together with the
panes that did parse** — the caller gets whatever was seen but is told the view is
incomplete, and the panes are still there for any future caller that only needs a
best-effort list.

Docstring states the contract explicitly: `observed` is `True` only when tmux answered
**and** every non-blank record parsed; `observed=False` means *unverifiable*, never
*empty*, and callers must not treat the two alike.

### 2. `.aitask-scripts/monitor/minimonitor_app.py`

- Module-level constant next to the other tunables:
  `AUTO_CLOSE_CONFIRMATIONS = 2` — with a comment naming t1446 and the reset rule.
- New instance field beside `self._mount_time` (`:251`):
  `self._empty_window_streak: int = 0`.
- Rewrite `_check_auto_close` (`:511-519`) so every path decides "unverifiable"
  explicitly and resets the streak:

```python
def _check_auto_close(self) -> None:
    """Exit only on a POSITIVELY OBSERVED empty window (t1446).

    An unverifiable observation — tmux timeout, transport failure, a listing
    that does not even contain our own pane — is NOT evidence the window is
    empty, and never exits. It also resets the confirmation streak.
    """
    if self._monitor is None or self._own_window_id is None:
        return
    observed, panes = self._monitor.discover_window_panes(self._own_window_id)
    own_pane = os.environ.get("TMUX_PANE")
    if not observed or not own_pane:
        # tmux failed, or the listing did not parse completely (a dropped
        # sibling row looks exactly like solitude) — not an observation.
        self._empty_window_streak = 0
        return
    pane_ids = {p.pane_id for p in panes}
    if own_pane not in pane_ids:
        self._empty_window_streak = 0      # listing without us: not a self-sighting
        return
    if pane_ids - {own_pane}:
        self._empty_window_streak = 0      # other panes remain
        return
    self._empty_window_streak += 1
    if self._empty_window_streak >= AUTO_CLOSE_CONFIRMATIONS:
        self.exit()
```

### 3. `tests/test_monitor_modal_space_dispatch.py:93`

Update the `_FakeMonitor` stub to the new contract: `return (False, [])`, with a short
comment that the fake observes nothing. (No assertion in that suite depends on it —
its `capture_all_async` returns `None`, so the tick never reaches the check.)

### 4. New `tests/test_minimonitor_auto_close_guard.py`

Three layers, so each negative control breaks exactly one. Mock-based; no live tmux.
Layers 1 and 2 drive the **real** `TmuxMonitor.discover_window_panes` (constructed
directly — its `__init__` is pure attribute setup, no tmux) with only `tmux_run`
faked, so the whole `rc → decision` chain is under test rather than a replica.

1. **Contract** — real `discover_window_panes`, `tmux_run` faked per case:
   - `rc=-1` → `(False, [])`; `rc=1` → `(False, [])`
   - `rc=0` + two valid lines → `(True, [2 panes])`
   - `rc=0` + empty stdout → `(True, [])`
   - `rc=0` + **valid own row + truncated sibling row** (7 fields) →
     `(False, [own])` — the parsed pane is still returned, but the listing is flagged
     incomplete. Same for a sibling row whose `pane_pid` is not an integer.
   - `rc=0` + valid rows separated by a blank line → `(True, [...])` (blank lines do
     not clear the flag).
2. **Decision** — real `MiniMonitorApp` object with `exit` recorded, `_monitor` a real
   `TmuxMonitor` with a scripted `tmux_run`, calling the real `_check_auto_close`:
   - 5 consecutive `rc=-1` ticks → `exit` never called *(the AC's rc = -1 test)*
   - alone-in-window → no exit after 1 call, exit after the 2nd
   - alone, `rc=-1`, alone → still no exit (streak reset), alone again → exit
   - another pane present → never exits
   - `rc=0` listing that omits our own pane → never exits
   - **`rc=0`, our own row valid, sibling row truncated** — repeated 5× → `exit` never
     called. This is the case a self-sighting rule alone would wave through.
3. **Wiring / acceptance** — mounted app via `app.run_test()`, `_mount_time` rewound
   past the 5 s grace, driving the real `_refresh_data` tick (instrumented in the style
   of `tests/test_minimonitor_own_mark.py`'s layer 3): a stalled tmux (`rc=-1`) tick
   leaves the app running; flipping the fake to "alone" exits it after two ticks. This
   is what proves the `:484-485` call site and the streak survive a real cycle.

**Negative controls (named, one mutation each):**

| mutation | must fail |
|---|---|
| revert §1 to `if rc != 0: return []` (and the caller to `if not other_panes: self.exit()`) | layer 1 `test_transport_failure_is_not_an_empty_window`, layer 2 `test_repeated_transport_failure_never_exits`, layer 3 `test_stalled_tmux_tick_does_not_close_the_app` |
| keep the pair but restore the bare `continue`s (drop the completeness flag) | layer 1 `test_truncated_sibling_row_makes_the_listing_unverifiable`, layer 2 `test_dropped_sibling_row_never_exits` |
| drop the streak (`AUTO_CLOSE_CONFIRMATIONS = 1`) | layer 2 `test_exit_requires_two_consecutive_verified_empty` |

A **passing** negative control means the test is wrong, not that the code is safe.

### Post-phase (risk mitigations)

1. `[live_autoclose_verification]` Drive the **supported launch path** (`./ait
   minimonitor`, which `exec`s `monitor/minimonitor_app.py` — so the pane's
   `pane_pid` *is* the app process) in a throwaway tmux session on the **same tmux
   server** (never `env -u TMUX`, which would talk to a different server; every
   command carries an explicit `-t` target).

   **Setup** — one window, one long-lived sibling, the companion beside it:

   ```bash
   cd /home/ddt/Work/aitasks
   tmux kill-session -t mm1446 2>/dev/null || true
   tmux new-session -d -s mm1446 -n agent-t1446 -c "$PWD" 'sleep 3600'
   tmux split-window -t mm1446:agent-t1446 -c "$PWD" './ait minimonitor'
   sleep 8   # clear the 5 s post-mount grace + ~1 refresh cycle
   tmux list-panes -t mm1446:agent-t1446 -F '#{pane_id} #{pane_pid} #{pane_current_command}'
   ```

   Bind the two ids from that listing: `sib` = the `sleep` pane, `mm` / `mmpid` = the
   `python` pane. **If the split did not produce exactly two panes, stop** — the
   fixture is wrong and nothing below is evidence.

   **(a) Sibling remains → companion must stay open.** Wait ≥4 refresh cycles and
   prove the app is *live*, not a frozen UI — two independent signals:

   ```bash
   tmux capture-pane -p -t "$mm" > /tmp/mm.a; ct0=$(awk '{print $14+$15}' /proc/$mmpid/stat)
   sleep 12
   tmux capture-pane -p -t "$mm" > /tmp/mm.b; ct1=$(awk '{print $14+$15}' /proc/$mmpid/stat)
   tmux list-panes -t mm1446:agent-t1446 -F '#{pane_id}'   # must still list BOTH ids
   diff /tmp/mm.a /tmp/mm.b; echo "cpu_ticks: $ct0 -> $ct1"
   ```

   **PASS** = both pane ids still listed **and** (`diff` reports a difference — the
   idle counters repaint — **or** `ct1 > ct0`, the process is still burning CPU on
   its tick). **FAIL** = the `python` pane is gone (the t1446 regression), or both
   liveness signals are static (the UI froze — a *different* defect, report it, do not
   count it as a pass).

   **(b) Sibling dies → companion must close.** The companion is the window's last
   pane, so its exit takes the window (and this single-window session) with it:

   ```bash
   tmux kill-pane -t "$sib"
   for i in $(seq 1 15); do sleep 1; tmux has-session -t mm1446 2>/dev/null || break; done
   tmux has-session -t mm1446 2>/dev/null && echo "STILL ALIVE (FAIL)" || echo "CLOSED after ${i}s (PASS)"
   ```

   **PASS** = `CLOSED` within 15 s (expected ~6 s = two 3 s cycles). **FAIL** =
   `STILL ALIVE` — auto-close never fires, meaning the completeness flag or the
   `TMUX_PANE` ↔ `pane_id` self-sighting rule is unsatisfiable against real tmux
   output. Capture `tmux capture-pane -p -t "$mm"` before cleanup, revise the fix, and
   do **not** ship on the strength of the faked tests alone.

   **Cleanup (always, both outcomes):** `tmux kill-session -t mm1446 2>/dev/null ||
   true; rm -f /tmp/mm.a /tmp/mm.b`

   **(c)** Record the verbatim PASS/FAIL lines from (a) and (b) in the plan's Final
   Implementation Notes.

## Verification

```bash
# new suite + the touched stub's suite
~/.aitask/venv/bin/python tests/test_minimonitor_auto_close_guard.py
~/.aitask/venv/bin/python tests/test_monitor_modal_space_dispatch.py

# every suite that drives _refresh_data or the monitor core (regression sweep)
bash tests/run_all_python_tests.sh    # read ONLY the last line: PYTHON SUITE: …
```

Then the live tmux check — the exact commands and pass/fail evidence are the
`[live_autoclose_verification]` post-phase step above; it is a required step of this
plan, not an optional smoke test.

Step 9 (Post-Implementation) handles merge, gate verification, and archival.

## Risk

### Code-health risk: low

- The fix removes the *fatal* consequence of a tmux stall but leaves
  `discover_window_panes` on the **sync** `tmux_run` path, called from the async
  `_refresh_data` tick — so the same 5 s timeout still blocks Textual's event loop
  during a stall. This contradicts the t1111_3 invariant that
  `tests/test_monitor_refresh_no_sync_tmux.py` encodes (that suite does not reach this
  call). · severity: medium · → mitigation: async_window_pane_discovery
- The completeness flag widens "unverifiable": a *persistently* unparseable record —
  e.g. a window renamed with a literal tab in it, which breaks the 8-field split for
  every row in that window — would disable auto-close permanently rather than
  occasionally. That is the accepted direction of failure (a lingering pane the user
  closes with `q`, never a lost live one), and the same rename also breaks our own
  row, so the self-sighting rule would refuse anyway. · severity: low · → mitigation:
  accepted trade-off; the normal path is proven by inline post-phase
  live_autoclose_verification
- The layer-3 wiring test could pass **vacuously** if its instrumentation neuters the
  auto-close check the way `tests/test_minimonitor_own_mark.py:543` does
  (`_own_window_id = None`). · severity: low · → mitigation: the negative control named
  in Implementation §4 (no separate task)

### Goal-achievement risk: low

- No automated test can prove auto-close *still fires* against real tmux: the fakes
  produce `pane_id`s that match `TMUX_PANE` by construction, so a real-world mismatch
  in that comparison would leave the new "my own pane must be in the listing" rule
  permanently unsatisfiable — auto-close would silently never fire and companion panes
  would accumulate. (Today's code compares the same two values, so this is a
  pre-existing assumption rather than a new one — but the fix makes a mismatch
  *silent* in the other direction.) · severity: medium · → mitigation: inline post-phase
  live_autoclose_verification

### Planned mitigations

- timing: post-phase | name: live_autoclose_verification | type: manual_verification | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — a faked test cannot prove auto-close still fires against real tmux | desc: live tmux check that the companion stays open beside a live agent and closes within ~2 refresh cycles after the agent pane is killed
- timing: after | name: async_window_pane_discovery | type: enhancement | priority: medium | effort: medium | inline_risk: high | added_complexity: medium | addresses: code-health — the sync tmux_run on the async refresh tick still blocks the event loop for up to 5 s during a stall | desc: move discover_window_panes onto tmux_run_async, await _check_auto_close from the tick, and extend tests/test_monitor_refresh_no_sync_tmux.py to cover the minimonitor refresh path

**Post-inline reassessment:** the confirmed inline post-phase adds a verification-only
step that touches no production code and cannot invalidate the plan. Both levels stand
at **code-health: low** / **goal-achievement: low**.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, in four files.
  `monitor_core.discover_window_panes` (`:1752`) now returns
  `(observed, panes)`; `observed` is `True` only when tmux answered (`rc == 0`)
  **and** every non-blank record parsed — the two bare `continue`s that silently
  drop malformed records now clear a `complete` flag, and blank lines are skipped
  without clearing it. `minimonitor_app` gained the module constant
  `AUTO_CLOSE_CONFIRMATIONS = 2`, the `_empty_window_streak` field, and a rewritten
  `_check_auto_close` in which every non-observation (tmux failure, incomplete
  listing, listing without our own pane) resets the streak and returns without
  exiting. `tests/test_monitor_modal_space_dispatch.py:93`'s `_FakeMonitor` stub was
  moved to the new `(False, [])` shape. New suite
  `tests/test_minimonitor_auto_close_guard.py` — 21 tests, three layers.
- **Deviations from plan:** none in substance. One correction to the plan's negative
  control table: the parser-only mutation (re-collapsing `rc != 0` into a *verified*
  empty) does **not** fail the layer-2/3 tests, because the caller's self-sighting
  rule catches an empty listing on its own. The control that fails them is the full
  pre-fix revert (parser **and** caller), which is what the plan's first row actually
  specifies; the run below used exactly that.
- **Issues encountered:**
  - A concurrent session was editing the same worktree on **t1449** (session-divider
    single-sourcing), owning `monitor_app.py`, `monitor_shared.py`,
    `tests/test_minimonitor_other_section.py`, `tests/test_monitor_session_divider.py`
    **and three hunks inside `minimonitor_app.py`** (the `format_session_divider`
    import, a CSS block, and the divider call site). Committing the file wholesale
    would have absorbed t1449's in-progress work, so this task's commit stages only
    its own hunks of `minimonitor_app.py` via a filtered patch to the index; the
    t1449 hunks were left untouched in the working tree.
  - Layer 3 must NOT clear `_own_window_id` the way `test_minimonitor_own_mark.py`
    does to keep auto-close out of its way — doing so makes the whole layer pass
    vacuously. That trap is called out in the suite docstring.
- **Key decisions:**
  - `(observed, panes)` pair rather than `list | None`: with `| None` a future caller
    writing the natural `if not panes: exit()` re-creates this exact bug, since `None`
    is falsy. A 2-tuple cannot be consumed without binding the flag.
  - `rc == 1` (tmux command error) counts as unverifiable too. Exiting on it buys
    nothing — if the window is genuinely gone our pane is gone with it.
  - Completeness is decided **at the parser**, the only place that can see a dropped
    record. Confirmed load-bearing: negative control 2 fails
    `test_dropped_sibling_row_never_exits`, which the caller's self-sighting rule
    alone does not catch (our own row is present in that listing).
  - N = 2 consecutive verified-empty observations before exiting, and **no** opposite
    budget — repeated failures never close the pane (both confirmed with the user
    during planning).
- **Verification run:**
  - `tests/test_minimonitor_auto_close_guard.py` — 21/21 OK.
  - `tests/test_monitor_modal_space_dispatch.py` — 7/7 OK.
  - `bash tests/run_all_python_tests.sh` — `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.
  - Negative controls (each applied alone, then reverted; repo verified free of
    `NEGCTRL` markers afterwards):
    | mutation | named tests that failed |
    |---|---|
    | full pre-fix revert (parser `return (True, [])` + caller's self-sighting guard disabled) | `test_transport_failure_is_not_an_empty_window`, `test_repeated_transport_failure_never_exits`, `test_stalled_tmux_tick_does_not_close_the_app` (7 total) |
    | bare `continue`s restored (completeness flag dropped) | `test_truncated_sibling_row_makes_the_listing_unverifiable`, `test_unparseable_pid_makes_the_listing_unverifiable`, `test_dropped_sibling_row_never_exits` (3 total) |
    | `AUTO_CLOSE_CONFIRMATIONS = 1` | `test_exit_requires_two_consecutive_verified_empty` (5 total) |
- **`[live_autoclose_verification]` post-phase result (real tmux, session `mm1446`):**
  - Fixture: `%422` = `sleep 3600` sibling, `%423` = `python` (the `./ait minimonitor`
    companion, pid 4041322) — exactly two panes, as required.
  - **(a) sibling remains → PASS.** After 12 s both `%422` and `%423` were still
    listed. UI capture was byte-identical across the interval, but CPU time advanced
    `cpu_ticks: 47 -> 63`, so the process was ticking, not frozen — the plan's
    "diff differs OR ct1 > ct0" liveness criterion, satisfied by the second signal.
  - **(b) sibling dies → PASS.** `tmux kill-pane -t %422` →
    `CLOSED after 5s (PASS)`, i.e. within two 3 s refresh cycles, as designed.
  - Cleanup ran and was confirmed (`cleanup OK`).
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/monitor_core.py:1410-1425` — `get_pane_option` returns
    `""` on `rc != 0`, and `compute_shadow_staleness` (`:538-540`) reads that empty
    string as "the shadow has not analyzed anything yet: nothing to warn about". A
    tmux failure therefore suppresses a staleness warning — the same
    unverifiable-read-as-negative class as t1446, in a different function.
  - `.aitask-scripts/aitask_minimonitor.sh:37` and
    `.aitask-scripts/lib/agent_launch_utils.py:1567` — the single-instance guards test
    `pane_current_command` for `minimonitor` / `monitor_app`, but a live minimonitor
    pane reports `python` (confirmed in this task's live fixture: `%423 … python`), so
    neither guard can ever fire. Harmless but dead. (Also noted in t1446's own
    "Out of scope" section.)
  - `.aitask-scripts/lib/agent_launch_utils.py:1465-1603` — `maybe_spawn_minimonitor`
    spawns the companion but never arms the `pane-died` cleanup hook, and
    `.aitask-scripts/lib/tui_switcher.py:1387` arms it with a **bare**
    `set-hook -p … pane-died` (index 0) — the overwrite hazard
    `attach_shadow_cleanup_hook` was written to avoid. (Carried over from t1446's
    "Out of scope" section; not re-verified live in this session.)
