---
Task: t2057_minimonitor_pick_running_warning_ignores_frozen.md
Base branch: main
Output branch: main
---

# t2057 — Stop the monitors treating frozen agents as live (pick warning + kill sites)

## Context

A frozen agent keeps `category == AGENT` (`frozen=True`, `frozen_record_id` set),
and its pane holds the `ait frozenagent` stand-in viewer. Three paths still
treat it like a live agent:

1. **t2057.** `MiniMonitorApp._find_running_agent_line`
   (`.aitask-scripts/monitor/minimonitor_app.py:3444`) says
   "⚠ t<id> is already running" for a frozen stand-in. t2054 made this
   reachable through `p` on a frozen followed agent.
2. **t2058.** On `n`, `_launch_pick_for_own` (`:3277`) sets `should_kill` from
   the task status alone. `_launch_pick` (`:3309`) then calls
   `kill_agent_pane_smart` after the launch. On a frozen Done agent this takes
   the sink's **unleased** kill-then-drop path (`monitor_core.py:3747-3756`),
   which silently deletes the only copy of the agent's output.
3. **t2059.** A race in `p`. The frozen guard in `_on_pick_number_entered`
   reads the snapshot taken when the prompt opened. If the agent is frozen
   while the dialogs are open, a ticked kill still reaches the same sink.

The full monitor has **no** "already running" scan (grep confirms). It does
have the t2058 defect on its own `n`:
`MonitorApp._launch_pick_for_sibling` (`monitor_app.py:3747`) kills the
focused pane through `kill_agent_pane_smart` for parent/archived/Done tasks
with no frozen check. Same sink, same guard, so it is fixed here too.

## Approach

One shared kill-time check, used at both `n` kill sites. It reads the
target's frozen state at the moment of the kill, both from the current
snapshot and from the live `@aitask_frozen` pane option. Only a **verified
live** target is killed. Frozen or unverifiable targets are never handed to
`kill_agent_pane_smart`. The user is told the kill was skipped and pointed at
`k` (the leased `_drop_frozen`).

### 1. `monitor_core.py`: sync pane-option read

Add `TmuxMonitor.get_pane_option_sync(pane_id, option, timeout=2.0) -> tuple[bool, str]`
next to the async `get_pane_option` (`:2302`). It has the same contract and
the same two steps, through the sync `self.tmux_run`:
- `show-options -pqv -t <pane> <option>`. rc≠0 → `(False, "")`.
- A non-empty value → `(True, value)`.
- An empty value → `display-message -p -t <pane> '#{pane_id}'` must echo
  `pane_id`, else `(False, "")`. This is because `-q` answers a missing pane
  like an unset option (t1971).

Its docstring points at `get_pane_option` for the rationale rather than
repeating it. It needs a sync twin because both kill sites run in sync
push_screen callbacks, and `kill_agent_pane_smart` is itself sync and
tmux-blocking there. The call goes through the gateway (`tmux_run`), so
`tests/test_no_raw_tmux.sh` stays green.

### 2. `monitor_shared.py`: shared check on the mixin (next to `_is_frozen`, `:686`)

```python
def _kill_target_state(self, pane_id: str) -> str:
    """'live' | 'frozen' | 'unverified' — read at KILL time (t2057/t2058/t2059).
    ...docstring: kill_agent_pane_smart's frozen path is an unleased
    kill-then-drop that deletes the capture; a snapshot can be a tick stale,
    so the live @aitask_frozen pane option is read too; anything not proven
    live fails closed (the kill is irreversible, skipping it is not).
    Residual: a freeze landing between this read and the kill is not
    covered — only the leased `aitask_frozen.sh drop` closes that."""
    snap = self._snapshots.get(pane_id)
    if snap is not None and self._is_frozen(snap):
        return "frozen"
    ok, value = self._monitor.get_pane_option_sync(pane_id, FROZEN_OPTION)
    if not ok:
        return "unverified"
    return "frozen" if value else "live"
```

`FROZEN_OPTION` is imported from `monitor_core` (`:483`).

### 3. `minimonitor_app.py`

- **`_find_running_agent_line` (t2057).** A frozen snapshot no longer counts
  as running. The scan keeps the first frozen match and returns the live
  warning when a live agent exists (live takes precedence). Otherwise it
  returns a distinct note for the frozen one:
  `"⚠ t{id} has a frozen agent in this session, window {idx}:{name} — restore or re-pick it from its viewer (R / P)"`.
  The decision is recorded in a comment. Silence would hide a real
  duplicate-work hazard, and the line goes into the existing wrapping
  `#pick-running` Static, so it fits the narrow dialog. The text stays plain
  `Content` (t2017).
- **`_launch_pick`'s `on_pick_result` kill (t2058 + t2059).** Replace the bare
  `kill_agent_pane_smart(kill_pane_id)` with:
  ```python
  state = self._kill_target_state(kill_pane_id)
  if state == "live":
      self._monitor.kill_agent_pane_smart(kill_pane_id)
      self._focused_pane_id = None
  elif state == "frozen":
      self.notify("Followed agent is frozen — launched without kill; "
                  "drop it with k", severity="warning")
  else:
      self.notify("Could not confirm the followed agent is still live — "
                  "launched without kill", severity="warning")
  ```
  This one site covers both `n` (`_launch_pick_for_own`) and `p`
  (`_on_pick_confirmed`), as t2059 asked ("the two fixes should share this
  check"). Launch still comes first, as before. The `_launch_pick` docstring
  gets a line on the guard.

### 4. `monitor_app.py`: full monitor `n` (`_launch_pick_for_sibling`)

The kill runs before the dialog. Gate it on `self._kill_target_state(pane_id) == "live"`.
For frozen, notify `"{window} is frozen — not killed; drop it with k"`
(`markup=False`, since window names are tmux input). For unverified, notify
`"Could not confirm {window} is still live — not killed"`. The pick dialog
still opens in every case.

## Tests

`tests/test_minimonitor_pick_by_number.py`:
- `_FakeMonitor` gains `get_pane_option_sync` with a scriptable
  `frozen_live` map (default `(True, "")` = verified live) and records the calls.
- `AlreadyRunningScanTests`:
  - (a) a frozen snapshot of the target gives no "already running" text and
    gives the frozen note naming the window;
  - (b) a live snapshot of the same task still warns (control);
  - (c) live and frozen panes both present → the live warning wins.
- A new `KillTimeFrozenRecheckTests` drives the **real** `_launch_pick`, with
  the patches of `SharedLaunchImplementationTests` plus `mm.launch_in_tmux`
  and `mm.maybe_spawn_minimonitor`:
  - (t2059) live followed agent, kill ticked; the snapshot flips to
    `frozen=True` between confirm and launch result → no kill, a warning toast;
  - (t2059, live read) the snapshot stays live but the pane option reads a
    record id → no kill;
  - an unverified read `(False, "")` → no kill, the "could not confirm" toast;
  - control: it stays live → killed.
- (t2058) A frozen Done followed agent on `n` (`_launch_pick_for_own`) →
  launch happens, no `kill_agent_pane_smart` call. A live Done control kills.

`tests/test_minimonitor_pick_next_characterization.py`: complete the doubles.
`_snap` gets `frozen=False` / `frozen_record_id=""`. `_FakeMonitor` gets
`get_pane_option_sync → (True, "")`. The existing kill-heuristic and ordering
tests keep passing unchanged.

`tests/test_monitor_pick_launch_sites.py`: complete the `_Host` doubles the
same way. In `SiblingPickTests`, add a frozen Done focused pane → not killed,
dialog still opened, warning. The existing
`test_parent_archived_and_done_are_killed_before_the_dialog` stays as the
live control.

Check `tests/test_monitor_markup_literal_sinks.py` (it references these
callbacks) and keep any new notify that interpolates a window name `markup=False`.

### Reader contract: pin the REAL `get_pane_option_sync` (review concern)

The launch tests above stub `get_pane_option_sync`. Without more, they would
pass even if the production reader reported a missing pane or a failed lookup
as verified live, which is exactly the failure the fail-closed guard exists to
prevent. Today `GetPaneOptionContractTests` (`tests/test_shadow_seam.py:430`)
and `LivePaneOptionTests` (`tests/test_monitor_pane_option_live.py:49`)
exercise only the async method. Both are extended to cover both
implementations, with no copied test bodies.

- **`tests/test_shadow_seam.py`.** Add
  `GetPaneOptionSyncContractTests(GetPaneOptionContractTests)`, overriding
  only `_read`. It scripts `mon.tmux_run` (sync) with the same
  `(rc, out)` queue and records argv in `self.calls`, then calls
  `mon.get_pane_option_sync("%5", "@opt")`. Every inherited case therefore
  runs against the sync reader:
  - a non-empty value → `(True, v)` in exactly 1 call;
  - a verified empty → `(True, "")` with the exact two-call argv;
  - a missing-pane echo `""` → `(False, "")`;
  - a mismatched echo `%7` → `(False, "")`;
  - a failed confirm `-1` → `(False, "")`;
  - a transport failure `-1` → `(False, "")` in 1 call;
  - a tmux error `1` → `(False, "")` in 1 call.

  Each variant also stubs the *other* gateway to raise. The async `_read` sets
  `mon.tmux_run` to raise and the sync one sets `mon.tmux_run_async` to raise.
  This way each class proves its own implementation and cannot pass through
  the sibling.
- **`tests/test_monitor_pane_option_live.py`.** Add
  `LivePaneOptionSyncTests(LivePaneOptionTests)`, overriding only `_read` to
  call `self.mon.get_pane_option_sync(pane, OPTION)`. This reuses the
  private-server cases: a set option reads back, an unset option on a live
  pane is a verified empty, a missing pane `%9999` is a failed read, and the
  read is pane-local (not inherited). The staleness case does not go through
  `_read`, so it simply re-runs. The module docstring gets one line naming
  both readers.

These two modules boot no TUI, so they stay in the parallel lane.

## Verification

```bash
python3 tests/test_minimonitor_pick_by_number.py
python3 tests/test_minimonitor_pick_next_characterization.py
python3 tests/test_monitor_pick_launch_sites.py
python3 tests/test_monitor_markup_literal_sinks.py
python3 tests/test_shadow_seam.py
python3 tests/test_monitor_pane_option_live.py
bash tests/test_no_raw_tmux.sh
AIT_TEST_WORKERS=4 bash tests/run_all_python_tests.sh --test-dir tests   # last line = verdict
```

Then Step 9 (Post-Implementation): archival of t2057 and deletion of the
folded t2058/t2059.

## Out of scope (record as upstream defects at Step 8)

The same "frozen while a confirm dialog is open" race exists at three other
`kill_agent_pane_smart` call sites, which are reached through `k`/`r`
confirmations rather than the pick flows:
- `minimonitor_app.py` `_on_own_kill_confirmed` (`:3197`);
- `monitor_app.py` `_on_kill_confirmed` (`:3674`) and `_on_restart_confirmed` (`:3881`);
- `applink/router.py:541`.

`_kill_target_state` is the ready-made guard for them.

## Risk

### Code-health risk: low
- The strict `snap.frozen` test doubles in two characterization modules and
  the fake monitors must be completed, otherwise they raise. This is bounded
  and mechanical, and it is the pattern t1705_7 established · severity: low ·
  → mitigation: none (covered by the Tests section)
- Residual TOCTOU: a freeze that lands between the live option read and the
  kill (milliseconds) is not caught. Only the leased `aitask_frozen.sh drop`
  closes it, and that is outside this task · severity: low · → mitigation:
  none (accepted residual, documented in the docstring)

- The new sync reader could silently diverge from the async one's fail-closed
  contract while stub-only launch tests stay green · severity: low (residual —
  both contract classes are subclassed to run against the sync reader, scripted
  and on a live private server) · → mitigation: none (covered by "Reader
  contract" in the Tests section)

### Goal-achievement risk: low
None identified.
