---
priority: medium
effort: high
depends: [t952_1]
issue_type: refactor
status: Ready
labels: [tmux, ait_bridge]
created_at: 2026-06-10 12:48
updated_at: 2026-06-10 12:48
---

## Context

Stage 3 of the t952 tmux-centralization decomposition (see `aiplans/p952_*`).
Moves the persistent control-mode client (`TmuxControlBackend` /
`TmuxControlClient`) ownership under the gateway so control-mode becomes
**reusable beyond monitor**, and re-points `TmuxMonitor` onto the gateway's
exec-strategy dispatcher. This is the **perf-sensitive** child (monitor refresh
hot path). Behavior-preserving. Depends on t952_1 only (parallel-eligible with
t952_2 / t952_4 in principle — but see the t822_3 coordination note).

**⚠️ t822_3 COORDINATION:** t822_3 is extracting `monitor_core` from the same
`monitor/` files this child edits (`tmux_monitor.py`, `tmux_control.py`).
**Rebase this child after t822_3 lands, or coordinate the edits** to avoid a
hard collision. Children t952_1 / t952_2 / t952_4 do not touch `monitor/` and
are unaffected.

## Key files to modify
- `.aitask-scripts/monitor/tmux_control.py` — thread the gateway socket args
  into the `tmux -C attach` spawn (currently lines ~98-99); move backend
  ownership under the gateway.
- `.aitask-scripts/monitor/tmux_monitor.py` — re-point `TmuxMonitor.tmux_run`
  (~line 266) and `_tmux_async` (~line 255) to delegate to the gateway's
  exec-strategy dispatcher; keep them as thin shims so all ~14 monitor call
  sites are untouched. Remove the now-duplicated raw helpers
  (`_run_tmux_subprocess` / `_run_tmux_async`) once they live in the gateway —
  OR keep them as the gateway's internal fallback primitives (decide at plan
  time; the anti-regression guard in t952_5 will whitelist whichever remains).
- `.aitask-scripts/lib/tmux_exec.py` — grow a session-bound control-mode
  dispatcher (try-backend-then-subprocess) that `TmuxMonitor` delegates to.

## Reference files for patterns
- `.aitask-scripts/monitor/tmux_monitor.py:255-285` — the existing dispatcher
  (`_tmux_async` / `tmux_run`): try `self._backend` (control client), fall back
  to subprocess on `rc == -1`. This logic moves into the gateway verbatim.
- `.aitask-scripts/monitor/tmux_control.py:1-70` — `TmuxControlBackend` /
  `TmuxControlClient`: persistent `tmux -C attach`, session-bound, clean
  `request_sync` / `request_async` → `(rc, stdout)`, `-1` on transport failure.

## Implementation plan
1. Introduce a gateway control-mode dispatcher that owns "control-client when
   alive, subprocess fallback on `-1`" — preserving the fallback-on-`-1` logic
   from `tmux_monitor.py:259-264,281-285` exactly.
2. `TmuxMonitor.tmux_run` / `_tmux_async` become thin delegations to it
   (signatures unchanged → call sites untouched).
3. Thread the gateway socket args (cached at construction, NOT per-call) into
   the `tmux -C attach` argv between `"tmux"` and `"-C"`.

## Risks
- **Perf hot path:** no per-call config reads — cache socket args once.
- **Keep the backend session-bound** (`TmuxControlBackend(session=...)`); do NOT
  gold-plate into a server-wide control client — that is a separate future task.
- Preserve `(rc, stdout)` `-1`-transport-failure semantics exactly.

## Verification
- **Keystone oracle:** `tests/test_tmux_run_parity.sh` — runs `tmux_run` with
  the backend started and not started, asserting identical results. This is the
  behavior-preservation oracle for this child.
- `tests/test_tmux_control.sh`, `tests/test_tmux_control_resilience.sh`.
- Add an assertion that the `tmux -C attach` argv includes the socket flag when
  `AITASKS_TMUX_SOCKET` is set.
- Run under `require_isolated_tmux`.
- This child gets its own Risk evaluation at pick time.
