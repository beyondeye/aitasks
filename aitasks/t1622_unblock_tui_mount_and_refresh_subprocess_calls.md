---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitormini, aitask_monitor, tui, tmux, performance]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1598
followup_kind: upstream_defect
created_at: 2026-08-26 08:01
updated_at: 2026-08-26 08:47
---

## Origin

Spawned from t1598 during Step 8b review.

## Upstream defect

- `monitor/minimonitor_app.py:1008` — raw `subprocess.run(["tmux", …], timeout=5)`
  on the mount path; a genuine up-to-5s startup blocker on a wedged tmux.
  Deliberately out of scope in t1598: it is allowlisted in `test_no_raw_tmux.sh`
  and correctly probes the *ambient* server before `self._monitor` exists, so
  routing it through the gateway would query the wrong socket.
- `monitor/monitor_app.py:1518` — `_get_desync_summary` spawns a fresh Python
  interpreter (2s cap) synchronously on the full monitor's refresh path. Not
  wasted there (its bar is always shown), so it needs an async sibling rather
  than the gate minimonitor got.
- `lib/stale_lock.sh:acquire` — no bounded guard wait, unlike
  `stale_lock_release` and `stale_lock_guarded_section`. Deliberately not fixed:
  it would take `aitask_create.sh`'s worst case from 10s to 50s and silently
  rescale the adapters' seconds-to-attempts conversion.
- `tests/test_agent_marks_concurrency.sh:~126` — hand-rolled dead-pid fixture of
  the shape `tests/lib/proc_fixtures.sh:11-22` explicitly warns against; the file
  does not source `proc_fixtures.sh`. Mitigated by `sleep 0`, so it is a hygiene
  issue rather than the 60s hazard the comment describes.

## Diagnostic context

t1598 fixed a ~10s startup input stall in `ait minimonitor`. Its root cause was
the tick-1 marks purge awaited inline on the App message pump; the fix moved the
first refresh into a worker, deferred the purge, hopped the control client to a
thread, and ported minimonitor's refresh path to the async tmux gateway.

While enumerating blocking calls on the mount and refresh paths, four further
sites surfaced that t1598 did NOT address. The first two are real latency bugs
of the same family — a synchronous subprocess on a Textual path — and are the
actionable part of this task. The third and fourth are recorded judgement calls:
t1598 considered and rejected both, with reasons, and they are listed here so the
reasoning is not lost rather than as work items. Re-opening either should start
by re-reading those reasons in aiplans/archived.

Note the `_get_desync_summary` case is NOT a copy of the minimonitor fix:
minimonitor could simply gate the call on `_session_bar_enabled` (its bar
defaults to hidden), whereas the full monitor always shows its bar, so the
string is genuinely needed and the call must become async instead.

## Suggested fix

For `:1008`, either lower the timeout to 2s (matching `_update_own_window_info`)
or drop the probe entirely and let the first tick's `_update_own_window_info`
populate the three fields — it re-derives the same window id / index / name every
tick, and the only consumer of `_own_window_id` is `_check_auto_close`, which is
already grace-gated past mount.

For `:1518`, add `get_desync_summary_async` to `monitor/desync_summary.py` using
`asyncio.create_subprocess_exec` plus a cached-only reader, pre-fetch it in
`_refresh_data`, and pass it into `_rebuild_session_bar` — note that method has a
second, keypress-driven call site that should use the cached path.
