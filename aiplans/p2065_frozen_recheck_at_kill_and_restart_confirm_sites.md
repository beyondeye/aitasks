---
Task: t2065_frozen_recheck_at_kill_and_restart_confirm_sites.md
Base branch: main
Output branch: main
---

# t2065 — Frozen re-check at the kill / restart confirm sites

## Context

`TmuxMonitor.kill_agent_pane_smart` kills a pane first and then runs
`aitask_agent_sessions.sh drop` for a frozen record. That kill takes no lease,
and the drop deletes the capture, which is the only copy of the agent's output.
t2057 closed this for the pick flows by re-checking at kill time with
`MonitorSharedMixin._kill_target_state(pane_id)` (`monitor/monitor_shared.py:701`),
which returns `live|frozen|unverified`.

Four call sites still reach the smart kill without that check:

- the `k` confirm callbacks in the minimonitor and the full monitor;
- the full monitor's `r` restart callback, which checks frozen state only when
  the action starts and kills inside the pick-dialog callback;
- the applink remote `kill_pane`, which has no frozen check at all.

An agent frozen by another monitor while one of these dialogs is open still
gets the unleased kill-then-drop.

Rule at every site: call the smart kill only when the state is `"live"`. On
`"frozen"` or `"unverified"`, do nothing and say why.

Plan review surfaced two more defects on the same path, both verified in the
code:
- The full monitor's `k` callback kills whatever is focused when the dialog
  closes, not the pane the dialog described (step 2).
- The live option alone is not what the smart kill consumes. It drops the
  record named in the discovery cache, so the guard reads that cache too
  (steps 0 and 4).

## Implementation

### 0. `.aitask-scripts/monitor/monitor_shared.py` — `_kill_target_state` also reads what the kill consumes

`kill_agent_pane_smart` decides whether to drop a record from
`self._pane_cache[pane_id].frozen_record` (`monitor_core.py:3779`), not from
the snapshot or the live option. Those sources can disagree:

- A liveness-only restore clears the live `@aitask_frozen` stamp before
  discovery refreshes the cache. The record and captures are kept on purpose.
- Mid-refresh, a callback can run after discovery rewrote `_pane_cache` but
  before `_snapshots` was committed.

In either case a `(True, "")` live read would pass the guard while the smart
kill still drops the stale record and its retained captures. So the guard reads
the cached record the kill consumes, between the snapshot read and the live
read:

```python
        snap = self._snapshots.get(pane_id)
        if snap is not None and self._is_frozen(snap):
            return "frozen"
        # The record id `kill_agent_pane_smart` will drop comes from the
        # monitor's discovery cache, not the snapshot or the live option: a
        # restore can clear the live stamp before discovery refreshes it, and
        # the kill would still drop that stale record and its captures (t2065).
        cached = self._monitor.get_pane(pane_id)
        if cached is not None and cached.frozen_record:
            return "frozen"
        ok, value = ...  # unchanged live read
```

Strict `cached.frozen_record`, no `getattr` default, following the
`_is_frozen` rule. Update the docstring: there are three reads, and the second
covers the cache/live disagreement. This changes every caller (the t2057 pick
flows plus the sites below).

Test doubles that need `get_pane(pane_id)`, defaulting to `None` (unknown to
the cache → smart kill does a raw `kill_pane`, no drop):
- `tests/test_monitor_pick_launch_sites.py` (`_Host._Monitor`)
- `tests/test_minimonitor_pick_by_number.py`
- `tests/test_minimonitor_pick_next_characterization.py`
- `tests/test_monitor_markup_literal_sinks.py` (`_FakeMonitor`)

Each double gets a settable `cached` map, so tests can plant a cached
`frozen_record`.

### 1. `.aitask-scripts/monitor/minimonitor_app.py` — `_on_own_kill_confirmed`

After the `confirmed`/`_monitor` guard and the `name` lookup, and before
`kill_agent_pane_smart`:

```python
        # Re-read at kill time, not when `k` opened the dialog: the agent may
        # have been frozen since, and a frozen pane would take the smart kill's
        # unleased kill-then-drop (t2065, as t2057 did for `n`/`p`).
        state = self._kill_target_state(pane_id)
        if state == "frozen":
            self.notify(f"{name} is frozen — not killed; press k again to drop it",
                        severity="warning", markup=False)
            return
        if state != "live":
            self.notify(f"Could not confirm {name} is still live — not killed",
                        severity="warning", markup=False)
            return
```

"press k again" is correct here: `action_kill_own_agent` sends a frozen
snapshot to `_confirm_drop_frozen`, the leased drop. When the live read sees
the freeze before the snapshot does, the next refresh catches up.

### 2. `.aitask-scripts/monitor/monitor_app.py` — `_on_kill_confirmed`: bind the target, then re-check

**Bind the pane.** `action_kill_pane` currently passes `self._on_kill_confirmed`
as the callback, and the callback reads the mutable `self._focused_pane_id`.
The refresh loop does not pause for modals. Each of these reassigns focus while
the dialog is open:

- `_consume_focus_request` (`monitor_app.py:1129`)
- `_maybe_auto_switch` (`:1138`)
- focus restoration (`:1603-1622`)

So if A is frozen while its dialog is open and focus moves to live B, a
confirmation that described A would verify B and kill B. Fix it the way the
minimonitor already works:

```python
        pane_id = snap.pane.pane_id
        self.push_screen(
            KillConfirmDialog(snap, task_info),
            callback=lambda ok: self._on_kill_confirmed(ok, pane_id),
        )
...
    def _on_kill_confirmed(self, confirmed: bool | None, pane_id: str) -> None:
        """Callback after kill confirmation dialog.

        ``pane_id`` is the pane the dialog described, bound when it opened —
        never re-read from ``_focused_pane_id``, which refresh can move while
        the dialog is up (focus requests, auto-switch, focus restoration).
        """
        if not confirmed or self._monitor is None:
            return
```

After a successful kill, clear focus only if it still points at the killed
pane: `if self._focused_pane_id == pane_id: self._focused_pane_id = None`.
Restart already does this.

**Then add the re-check.** Use the same block as step 1, with the same wording,
between the `name` line and `kill_agent_pane_smart`. `action_kill_pane` also
routes frozen panes to `_confirm_drop_frozen`.

`_kill_toast` in `tests/test_monitor_markup_literal_sinks.py` calls
`app._on_kill_confirmed(True)`; it becomes `app._on_kill_confirmed(True, "%1")`.
Grep `tests/` for any other `_on_kill_confirmed(` callers and update them too.

### 3. `.aitask-scripts/monitor/monitor_app.py` — `_on_restart_confirmed`

Inside `on_pick_result`, replace the unconditional `if self._monitor:` kill
with a check that runs **before the launch**. On anything other than `"live"`,
**do not launch** and return after `call_later(self._refresh_data)`:

- A restart means "replace this agent". If the kill is skipped and the launch
  goes ahead, a second agent runs the same task next to the frozen stand-in,
  and the windows can collide on `agent-pick-<id>` (the existing comment
  explains why the kill comes first).
- A frozen card already has its own route: `action_restart_task`'s message
  points to the viewer's `R`/`P`.

```python
                if self._monitor:
                    # Re-read at kill time (t2065): the agent may have been
                    # frozen since `r` opened the dialogs. Without a live kill
                    # there is no restart — launching anyway would duplicate
                    # the task beside the frozen stand-in.
                    state = self._kill_target_state(pane_id)
                    if state == "frozen":
                        self.notify(
                            f"{old_window_name} is frozen — not restarted; "
                            "press s to switch to its viewer, then R to "
                            "restore or P to re-pick",
                            severity="warning", markup=False)
                        self.call_later(self._refresh_data)
                        return
                    if state != "live":
                        self.notify(
                            f"Could not confirm {old_window_name} is still "
                            "live — not restarted",
                            severity="warning", markup=False)
                        self.call_later(self._refresh_data)
                        return
                    ok, _ = self._monitor.kill_agent_pane_smart(pane_id)
                    ...  # unchanged
```

There is no extra check in `_on_restart_confirmed` before the pick dialog
opens. The check guards the irreversible step at the moment it runs, and an
earlier read would still leave the window open.

### 4. `.aitask-scripts/applink/router.py` — `_kill_pane`: refuse, do not route to the drop

A remote client gets none of the desktop "captured output is deleted" warning.
Sending it to the leased drop would delete the transcript without that warning,
so a frozen or unverifiable pane is **refused**. Retiring it stays a desktop
`k` action.

- Import `FROZEN_OPTION` from `monitor.monitor_core`. `server.py` already
  imports that module, and the router test puts `.aitask-scripts` on
  `sys.path`. If the router can be imported without the scripts dir on the
  path, add it next to `_LIB_DIR`.
- Add a helper:

```python
    def _kill_refusal(self, msg_id, verb, pane_id):
        """err frame when ``pane_id`` is not proven live, else ``None`` (t2065).

        ``kill_agent_pane_smart``'s frozen path is an unleased kill-then-drop
        that deletes the capture; a remote client never sees the desktop's
        capture-loss warning, so a frozen pane is refused here and retired from
        a desktop monitor's ``k`` (the leased drop). Unreadable fails closed.
        """
        # The record the smart kill drops comes from the discovery cache; a
        # restore can clear the live stamp first, so both are read.
        cached = self._monitor.get_pane(pane_id)
        if cached is not None and cached.frozen_record:
            return self._err(msg_id, verb, ERR_BAD_PAYLOAD,
                             "pane holds a frozen agent; drop it from a desktop monitor (k)",
                             detail={"reason": "frozen"})
        ok, value = self._monitor.get_pane_option_sync(pane_id, FROZEN_OPTION)
        if not ok:
            return self._err(msg_id, verb, ERR_BAD_PAYLOAD,
                             "could not confirm pane is live",
                             detail={"reason": "unverified"})
        if value:
            return self._err(msg_id, verb, ERR_BAD_PAYLOAD,
                             "pane holds a frozen agent; drop it from a desktop monitor (k)",
                             detail={"reason": "frozen"})
        return None
```

- Call it in `build_details`: `refusal = self._kill_refusal(...)`; if
  `refusal` is set, return it, otherwise return the target dict.
  `_two_phase` runs `build_details` in both phases, right before `execute`, so
  this one call refuses up front and also re-checks at execution time. Add a
  comment saying so.
- Phase-1 change: a pane that no longer exists now gets
  `BAD_PAYLOAD unverified` instead of a `confirm_required` target with only
  `pane_id`. The existing test "target degrades to pane_id when pane unknown"
  uses `%404`, so its stub monitor needs a defined option read. To keep that
  degrade test meaningful, the stub reads as live by default: `(True, "")`.
- `_kill_window` is not in scope. It kills a whole window through
  `kill_window`, with no record drop and no capture deletion.

### 5. Tests

**`tests/test_monitor_pick_launch_sites.py`** (`_Host` already stubs
`get_pane_option_sync` and uses the real `_kill_target_state`)
- `RestartPickTests`: the exact-log assertions in
  `test_tmux_kills_then_launches_the_edited_command` and
  `test_launch_error_after_kill_returns_before_refresh` gain a leading
  `("read", "%7", "@aitask_frozen")`.
- New: frozen after the dialog opened (snapshot `frozen=True` set between
  `_open()` and `callback(cfg)`), then the variant where the live read returns
  `(True, "rec-1")`, then unverified `(False, "")`. For each, assert there is
  no `("kill", …)`, no `("launch", …)` and the warning text.

**New `KillConfirmRecheckTests` in the same file**, for `MonitorApp`'s `k`
flow. Open the dialog through the real `action_kill_pane`: the host needs
`_get_focused_pane_id` and `_confirm_drop_frozen`, and it captures the pushed
callback. Then confirm. Cases:
- live control: one kill, "Killed …";
- frozen snapshot;
- frozen on the live read;
- **cached `frozen_record` with a verified-empty live option** (the restore
  disagreement);
- unverified.

Every case except the control asserts no kill. Plus the **focus-move
regression**: open the dialog for A (`%7`), freeze A, add a live B (`%8`) and
set `_focused_pane_id = "%8"`, then confirm. Neither pane is killed, the
frozen-A warning is shown, and B is never read or killed. Its paired control:
same focus move, A still live → only `%7` is killed, and `_focused_pane_id`
stays `"%8"`.

**Core-cache regression**: run the real `TmuxMonitor.kill_agent_pane_smart`
against a monitor whose `_pane_cache["%7"]` carries `frozen_record="rec-1"`
and whose `tmux_run` is stubbed. Patch `_drop_session_record` to record calls.
Through `MonitorApp._on_kill_confirmed` with a verified-empty live option,
assert that `_drop_session_record` is never called and no kill reaches
`tmux_run`. This pins the guard against the real consumer, not a double's
reading of it. If driving the real `TmuxMonitor` from `_Host` is impractical,
put this one case in the applink router test with a real `TmuxMonitor`
instance.

**`tests/test_minimonitor_pick_by_number.py`**: a new
`OwnKillConfirmRecheckTests` drives the real `action_kill_own_agent` →
`KillConfirmDialog` callback → `_on_own_kill_confirmed` with the existing
`_mk_app` harness. It flips the snapshot or `pane_option` between push and
callback, as `KillTimeFrozenRecheckTests` does. Cases: live control, frozen
snapshot, frozen live read, unverified.

**`tests/test_monitor_markup_literal_sinks.py` `TOAST_SITES`**: add the new
window-naming toasts:
- `monitor: kill frozen` / `monitor: kill unverified`, and the minimonitor
  pair, all via `_kill_toast` with a `frozen_read` argument. Extend
  `_kill_toast(cls, ok, frozen_read=(True, ""))` to pass it into
  `_FakeMonitor`.
- `monitor: restart frozen` / `monitor: restart unverified`: extend
  `toast_monitor_restart(name, frozen_read=...)`. Its `_launch` helper needs
  no change, because the callback returns before `launch_in_tmux`.

**`tests/test_applink_router.sh`**: give `StubMonitor` a
`frozen = {}  # pane_id -> (ok, value)` map and a
`get_pane_option_sync(p, option, timeout=2.0)` method that logs the option
and returns `self.frozen.get(p, (True, ""))`. New checks:
- unconfirmed `kill_pane` on a frozen pane → `BAD_PAYLOAD` reason `frozen`,
  no kill call;
- confirmed `kill_pane` when the pane flipped to frozen after phase 1 →
  `frozen`, no kill call (pins the execution-time re-check);
- unverified → reason `unverified`, no kill;
- cached `frozen_record` with a verified-empty live option → reason `frozen`,
  no kill. `StubMonitor.get_pane`'s `SimpleNamespace` gains a `frozen_record`
  field, default `""`, set from a new `cached_frozen` map;
- a real `TmuxMonitor` (constructed as in `server.py`, `tmux_run` stubbed,
  `_drop_session_record` patched), with `_pane_cache` holding a frozen record
  and the live option empty → confirmed `kill_pane` refused, and
  `_drop_session_record` never called;
- the existing live control keeps executing, and the option read names
  `@aitask_frozen`.

### 6. Docs

`aidocs/applink/monitor_port_design.md`: after the `kill_pane maps to
kill_agent_pane_smart` bullet (around line 88), add one bullet. It says the
server refuses `kill_pane` with `err BAD_PAYLOAD`, `detail.reason` set to
`"frozen"` or `"unverified"`, when the pane carries `@aitask_frozen` or its
state cannot be read. Both phases are checked. A frozen agent is retired from a
desktop monitor's `k`, the leased drop that warns about capture loss. Keep it
current-state prose.

Residual limitation, inherited and documented in the `_kill_target_state`
docstring: a freeze that lands between the read and the kill is not caught.
Only the leased `aitask_frozen.sh drop` closes that window. No change.

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests   # verdict: last line
python3 -m pytest tests/test_monitor_pick_launch_sites.py tests/test_minimonitor_pick_by_number.py tests/test_monitor_markup_literal_sinks.py -q
bash tests/test_applink_router.sh
```

Negative control: temporarily remove the re-check in one site and confirm the
new frozen test fails, then restore it. Do this in an isolated scratch copy,
never with git restore or stash in the shared worktree.

## Step 9 (Post-Implementation)

Work happens on the current branch, so there is no merge. Commit code as
`bug: … (t2065)`, then archive per Step 9.

## Risk

### Code-health risk: low
None identified. The cached-record read in `_kill_target_state` also changes
the t2057 pick flows, and four test doubles need `get_pane`. A missed double
raises `AttributeError` loudly and the full suite in Verification runs it, so
this is a step in the plan, not a residual risk. The guards stay local and
reuse the existing helper. The restart behaviour
change (no launch without a live kill) is deliberate and pinned by tests.

### Goal-achievement risk: low
None identified. Every site the task lists is covered. The applink choice
(refuse rather than route to the drop) is the one the task left open; the
reason is in step 4. The mobile companion does not issue `kill_pane` today, so
the new `err` reasons break no client.

## Final Implementation Notes

- **Actual work done:**
  - **Shared guard.** `_kill_target_state` (`monitor_shared.py`) now reads three sources: the snapshot, then the monitor's discovery cache (`get_pane(...).frozen_record`, the record `kill_agent_pane_smart` drops), then the live `@aitask_frozen` option.
  - **Minimonitor `k`.** `_on_own_kill_confirmed` re-checks at kill time.
  - **Full monitor `k`.** `action_kill_pane` binds the pane id into the callback; `_on_kill_confirmed(confirmed, pane_id)` re-checks and clears focus only if focus is still on the killed pane.
  - **Restart.** `_on_restart_confirmed` re-checks before the kill and neither kills nor launches unless the pane is live.
  - **Applink.** `_kill_pane` refuses through `_kill_refusal` (cache record, then live option) with `BAD_PAYLOAD` `frozen`/`unverified`. It runs in both `_two_phase` phases, so the confirmed request re-checks right before the kill.
  - **Docs.** Added the refusal bullet to `aidocs/applink/monitor_port_design.md`.
- **Deviations from plan:**
  - The router imports `FROZEN_OPTION` lazily inside `_kill_refusal`, with `.aitask-scripts` added to `sys.path` at module load. `aitask_applink_validate_profile.sh` also imports the router, and that path should not pull in `monitor_core`.
  - The real-`TmuxMonitor` regression went into both `test_monitor_pick_launch_sites.py` (`RealSmartKillCacheTests`, which also pins that the unguarded smart kill *does* drop the cached record) and `test_applink_router.sh`.
- **Issues encountered:** with `list-panes` failing, `kill_agent_pane_smart` falls back to a raw `kill_pane` that never drops a record. The real-monitor fixture therefore answers `list-panes` with rc 0 and empty output, which takes the whole-window branch, the one that retires the record.
- **Key decisions:**
  - Restart on a non-live pane aborts entirely: launching beside a frozen stand-in would duplicate the task.
  - Applink refuses rather than routing to the drop, because a remote client gets no capture-loss warning.
  - `_kill_window` was left out of scope: it drops no record.
- **Negative controls** (isolated scratch copy, deleted afterwards). Removing each of these turned the matching new tests red:
  - the cache read in `_kill_target_state` (4 red);
  - the monitor `k` re-check (6 red);
  - the bound pane id (2 red);
  - the restart re-check (6 red);
  - the minimonitor `k` re-check (5 red);
  - the applink guard (red);
  - the applink cache read (red).
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/monitor_app.py:3930-3935` — `_on_restart_confirmed` still calls `launch_in_tmux` (and reports "Restarted agent for t<id>") when `kill_agent_pane_smart` returns `ok=False`. A failed kill leaves the original agent alive while a replacement starts on the same task. This was pre-existing at HEAD (line 3893) and is separate from the frozen guard. The fix: return with a warning on kill failure, plus a regression asserting no launch and no success toast. → follow-up **t2075** (created during Step 8 review).

## Post-Review Changes

### Change Request 1 (2026-10-20)
- **Requested by user:** verify a concern that restart launches after a failed kill, and address it if valid.
- **Changes made:** none to code. Verified: HEAD has the same behaviour, so it is pre-existing and separable. Per the concern's stated disposition ("follow-up"), it was recorded under Upstream defects identified for Step 8b to offer as a follow-up task.
- **Files affected:** this plan file only.

### Change Request 2 (2026-10-20)
- **Requested by user:** the same concern; noted that the plan documented the defect but supplied no follow-up task ID.
- **Changes made:** created follow-up task t2075 (`restart_aborts_launch_on_failed_kill`, `bug`, `followup_kind: upstream_defect`, `followup_of: 2065`) and linked it from the upstream-defect bullet. No code change in t2065; the disposition stays follow-up.
- **Files affected:** this plan file; `aitasks/t2075_restart_aborts_launch_on_failed_kill.md` (new).
