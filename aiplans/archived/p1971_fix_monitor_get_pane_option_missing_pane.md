---
Task: t1971_fix_monitor_get_pane_option_missing_pane.md
Base branch: main
Output branch: main
---

# t1971 — `get_pane_option` must not read a vanished pane as "verified unset"

## Context

`TmuxMonitor.get_pane_option` (`.aitask-scripts/monitor/monitor_core.py:2225-2250`)
reads with `show-options -pqv` and treats `rc == 0` as a verified read. tmux 3.7c
answers a **missing** pane under `-q` with rc 0 and empty output (measured in
t1957_2 and pinned by `tests/test_trails_focus_mailbox_live.py`). So a pane
that vanished reads as `(True, "")`, a *verified* "option not set". The
docstring says the tuple exists to prevent exactly that (t1451).

**What it breaks.** The only consumer is `compute_shadow_staleness`
(`monitor_core.py:783`), used by minimonitor's freshness tick
(`minimonitor_app.py:3820`, `:4892`) and the monitor's picker paths
(`monitor_app.py:1282`, `:3403`). Suppose a shadow pane vanishes after discovery
(`find_shadow_pane_info_async`) and before the option read. Today the result is
`(True, "")`, then `(False, None)` ("never analyzed, nothing to warn"). The
minimonitor then records `ReadRecency(False, None)` and latches
`_loop_stale_false_pending = True` (`minimonitor_app.py:3825-3830`). That feeds
a false "fresh" edge into the review loop and clears a standing read-recency
verdict on evidence that does not exist.

**What the consumer should do with a vanished shadow** (the task asks this
first). It should get `(None, None)`, "unverifiable, preserve". That already
happens on a failed read, and no consumer change is needed. The state for "the
shadow is gone" belongs to the discovery branch: on the next tick
`find_shadow_pane_info_async` sees no shadow, and the `not shadow_pane` branch
(`minimonitor_app.py:4978-4991`) clears `_shadow_read_recency`, the combined
verdict, the banner and the phase binding. The freshness reader should not
duplicate that decision from one racy read.

## Approach — read first, then confirm the pane only when the value is empty

The task suggests replacing the read with a single
`display-message -p -t <pane> '#{pane_id}\t#{<opt>}'`, as t1957_2's
`read_trails_focus_request` does. I am **not** taking that shape here, because
it changes what gets read. `show-options -p` (no `-A`) returns the
**pane-local** value only. A format `#{@opt}` returns the **effective,
inherited** value: pane, then window, then global window, then session (tmux(1),
OPTIONS: "Pane options inherit from window options"). The method is documented
as reading a pane-scoped option, and the shadow stamp is written pane-scoped
only (`aitask_shadow_capture.sh:369`, `set-option -p`). So the fix should add
the missing-pane discrimination and leave the lookup scope alone.

New logic:

1. `show-options -pqv -t <pane> <opt>`. If `rc != 0`, return `(False, "")` (unchanged).
2. If the value is **non-empty**, return `(True, value)`. tmux only prints a
   value for a pane that exists, so this needs no second round trip. This is the
   steady state once the shadow has stamped, which keeps the cost the
   minimonitor's throttle comment (`minimonitor_app.py:3814`) cares about.
3. If the value is **empty**, the read is ambiguous ("unset" or "pane gone").
   Confirm with `display-message -p -t <pane> '#{pane_id}'` and accept only when
   the echoed id **equals** `pane_id`. rc ≠ 0, an empty echo (missing pane) or a
   different id (tmux falling back to another pane) all give `(False, "")`.
   An exact echo gives `(True, "")`.

**Ordering is load-bearing: read, *then* confirm.** tmux pane ids (`%N`) come
from a monotonically increasing counter and are never reused within a server.
So a pane that still exists at the confirm also existed at the earlier read.
The reverse order (confirm, then read) would let the pane vanish in between and
recreate the bug. The docstring will say this.

**Precondition:** `pane_id` must be a `%N` id, because the echo comparison is
exact. Every production caller passes one: shadow panes come from
`list-panes -F '#{pane_id}…'` (`shadow_query_args`, `monitor_core.py:580`). A
non-`%N` target would fail closed on an empty value (`(False, "")`, then
preserve), never open.

## Implementation steps

1. **Live test first (red against the current code).** Create
   `tests/test_monitor_pane_option_live.py`, modelled on
   `tests/test_trails_focus_mailbox_live.py`:
   - `@unittest.skipUnless(shutil.which("tmux"))`. In `setUp`, use a short
     `tempfile.mkdtemp(prefix="ait1971_", dir="/tmp")`, patch `TMUX_TMPDIR`
     and `AITASKS_TMUX_SOCKET="ait1971"` in the environment, and pop
     `TMUX`/`TMUX_PANE`. **Then** construct `TmuxMonitor(session=SESSION)`:
     its `TmuxClient()` resolves the socket at construction. Assert containment
     statically (`mon._tmux.socket_args == ["-L", "ait1971"]`) before any
     mutation.
   - **Start the private server with a clean config:**
     `client.run(["-f", "/dev/null", "new-session", "-d", "-s", SESSION, "-x", "80", "-y", "24", "sleep 600"])`.
     `TmuxClient._argv` builds `tmux -L ait1971 -f /dev/null new-session …`, so
     `-f` is a tmux global flag. tmux reads it only when that command starts the
     server; later calls (including `TmuxMonitor`'s) talk to the running server
     and load no config. Without it a new server loads the developer's
     `~/.config/tmux/tmux.conf` (present on this machine), whose hooks could
     create panes or set pane-local options and break the unset-option
     assertions for reasons that have nothing to do with `get_pane_option`.
     Add `addCleanup(kill-server)` through that same client. Then assert the
     server is clean as a precondition: `list-panes -s -t ={SESSION}: -F '#{pane_id}'`
     yields exactly one pane, which becomes the test's pane id. `_backend`
     stays `None`, so calls take the gateway's subprocess path.
   - Cases, each run through `asyncio.run(mon.get_pane_option(...))`:
     a. live pane, `set-option -p @opt 1000` gives `(True, "1000")`;
     b. live pane, option unset gives `(True, "")`;
     c. **missing pane `%9999` gives `(False, "")`**, plus the control
        `client.run(["show-options","-p","-q","-v","-t","%9999","@opt"]) == (0, "")`
        to prove the old probe could not tell;
     d. **scope is pane-local**: `set-option -w @opt win` with the pane-local
        value unset still gives `(True, "")`. This pins the reason for not
        switching to a format read. Measure, as a control, whether
        `display-message -p -t <pane> '#{@opt}'` returns `win`. If it does,
        keep that assertion as the pinned rationale. If it does not, drop the
        control and simplify the docstring rationale (the fix stays correct
        either way).
     e. **consumer end-to-end**: `compute_shadow_staleness(mon, "%9999", pane, 3.0)`
        gives `(None, None)` (before the fix it gives `(False, None)`).
   - Run it **before** touching the source and confirm that c and e fail and
     a, b, d pass. That run is the negative control: the test detects the
     defect. (No stash: the test is written first and the source edited after.)

2. **Fix `get_pane_option`** (`monitor_core.py:2225-2250`) as described above:

   ```python
   rc, out = await self.tmux_run_async(
       ["show-options", "-pqv", "-t", pane_id, option], timeout=timeout
   )
   if rc != 0:
       return (False, "")
   value = out.strip()
   if value:
       return (True, value)
   # `-q` answers a MISSING pane exactly like an unset option — rc 0, no
   # output (t1971) — so an empty value is a verified "unset" only once the
   # pane is confirmed. AFTER the read on purpose: pane ids are never reused
   # within a server, so a pane that exists now existed when it was read.
   rc, out = await self.tmux_run_async(
       ["display-message", "-p", "-t", pane_id, "#{pane_id}"], timeout=timeout
   )
   if rc != 0 or out.strip() != pane_id:
       return (False, "")
   return (True, "")
   ```

   Update the docstring:
   - `ok` is also `False` for a pane that does not exist (t1971).
   - The read-then-confirm ordering and its justification.
   - The `%N` precondition.
   - The confirm runs only on an empty value, so it is a cost gate.
   - Why the read stays `show-options` rather than a format read: pane-local
     vs inherited scope.

3. **Docstring of `compute_shadow_staleness`** (`monitor_core.py:813-821`). Next
   to the t1451 paragraph, add one sentence: a shadow pane that vanished
   between discovery and the read is also a failed read (`(None, None)`,
   preserve), because `-q` answers a missing pane with rc 0 and no output.
   Clearing state for a vanished shadow belongs to the caller's discovery
   branch, not to this read. The table rows are unchanged; "`get_pane_option`
   reported failure" already covers it.

4. **Update `GetPaneOptionContractTests`** (`tests/test_shadow_seam.py:430-460`).
   The fake `tmux_run_async` currently returns one canned `(rc, out)` for every
   call. Make it a scripted, call-recording fake (a list of responses popped in
   order, with each argv appended to `calls`). Then pin:
   - non-empty value gives `(True, "1000.0")` with **exactly one** call (the cost gate);
   - empty value + echo `"%5\n"` gives `(True, "")`, with call 1 = `show-options`
     and call 2 = `display-message … #{pane_id}`, in that order (the ordering);
   - empty value + empty echo (missing pane) gives `(False, "")`;
   - empty value + a different echo (`"%7\n"`) gives `(False, "")`;
   - empty value + confirm `rc -1` gives `(False, "")`;
   - read `rc -1` / `rc 1` give `(False, "")` with **one** call (no confirm after a failed read).

   Rename `test_unset_option_is_a_VERIFIED_empty` so it says "verified only
   when the pane is confirmed". Stub monitors elsewhere (`_StaleMon`,
   `test_minimonitor_concern_action.py`) stub `get_pane_option` itself and stay
   unchanged.

**Follow-up (not in this task's scope):** the model test
`tests/test_trails_focus_mailbox_live.py` (`setUp`, `new-session` without
`-f /dev/null`) has the same config-isolation gap. After commit, offer it as a
separate follow-up task (Step 8b/8e) rather than editing t1957_2's test here.

## Verification

- `~/.aitask/venv/bin/python -m pytest tests/test_monitor_pane_option_live.py -q`.
  Red before step 2 (cases c and e), green after.
- `~/.aitask/venv/bin/python -m pytest tests/test_shadow_seam.py -q`.
- Neighbouring consumers: `tests/test_minimonitor_concern_action.py`,
  `tests/test_minimonitor_concern_smoke.py`,
  `tests/test_monitor_refresh_no_sync_tmux.py`.
- `bash tests/test_no_raw_tmux.sh`: the new call goes through the gateway
  (`tmux_run_async`). The live test uses `TmuxClient`, as its model does.
- Full Python suite: `bash tests/run_all_python_tests.sh`, reading only the
  final `PYTHON SUITE:` verdict line.

## Step 9 (Post-Implementation)

This runs on the current branch (profile `fast`, no worktree), so there is no
merge. After Step 8 review and commit, archive with
`./.aitask-scripts/aitask_archive.sh 1971` and push with `./ait git push`.

## Risk

### Code-health risk: low
- The echo comparison is exact, so a caller passing a non-`%N` target (e.g. `sess:1.0`) would read every empty value as a failed read and the freshness banner would only ever be preserved, never cleared. All current callers pass `%N` ids from `list-panes -F '#{pane_id}'`, and the failure direction is preserve (safe) · severity: low · → mitigation: none (precondition documented in the docstring, step 2)
- One extra tmux round trip when the stamp is empty (a shadow that has not analyzed yet, or a vanished pane) · severity: low · → mitigation: none (cost-gated on empty values only, pinned by the one-call test in step 4)

### Goal-achievement risk: low
- Depends on tmux behaviour measured on 3.7c (`display-message -t <missing>` gives rc 0 and an empty line). Another version could return rc 1, or fall back to a different pane. Both fail closed under the exact-echo rule · severity: low · → mitigation: none (live test in step 1 pins it on the installed tmux)
- Without config isolation, the live test's verdict could depend on the developer's tmux config (startup hooks creating panes or setting pane options) rather than on `get_pane_option` · severity: low · → mitigation: none (addressed in step 1: the server starts with `-f /dev/null` and a one-pane precondition is asserted)

## Final Implementation Notes
- **Actual work done:** As planned. `TmuxMonitor.get_pane_option` (`.aitask-scripts/monitor/monitor_core.py`) still reads with `show-options -pqv`. When the value is empty, it then confirms the pane with `display-message -p -t <pane> '#{pane_id}'` and reports `(True, "")` only on an exact echo. rc != 0, an empty echo or a different id give `(False, "")`. Docstrings of `get_pane_option` and `compute_shadow_staleness` were updated: missing pane = failed read, read-then-confirm ordering, `%N` precondition, cost gate, and pane-local vs inherited scope. New live test `tests/test_monitor_pane_option_live.py` (5 cases). `GetPaneOptionContractTests` in `tests/test_shadow_seam.py` was rewritten over an in-order, call-recording gateway fake (7 cases).
- **Deviations from plan:** None. Case d's control held: `display-message '#{@opt}'` returns the inherited window value (`win`) while `show-options -p` returns empty. The assertion was kept as the pinned rationale for not switching to a format read.
- **Issues encountered:** None. Test-first negative control: before the fix the live test failed exactly the missing-pane case and the consumer end-to-end case (`(True, "")` / `(False, None)`), and the other 3 passed. After the fix: 5/5. The full Python suite passed (`PYTHON SUITE: PASSED (runner=pytest, exit=0)`), `tests/test_no_raw_tmux.sh` passed, and the neighbouring minimonitor/monitor suites passed (252).
- **Key decisions:**
  - Kept `show-options -p` over the task's suggested single `display-message '#{pane_id}\t#{@opt}'` read, because a format returns the *inherited* value, which would change what the method reads (now measured, not assumed).
  - The confirm runs only on an empty value and only after the read; pane ids are never reused within a server, so a pane alive at the confirm was alive at the read.
  - No consumer change: a vanished shadow now gives `(None, None)` (preserve). Clearing a gone shadow's state belongs to minimonitor's discovery branch (`not shadow_pane`), which runs on the next tick.
  - Per review: the live server starts with `-f /dev/null` so the developer's tmux config cannot add panes or options, plus a one-pane precondition. `tests/test_trails_focus_mailbox_live.py` (t1957_2) has the same config-isolation gap; it is offered as a separate follow-up rather than edited here.
- **Upstream defects identified:** None
