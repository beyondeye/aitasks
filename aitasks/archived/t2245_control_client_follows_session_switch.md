---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [tmux, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2236
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-08 17:51
updated_at: 2026-11-09 11:11
completed_at: 2026-11-09 11:11
---

## Origin

Spawned from t2242 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/monitor_core.py:1595` — TmuxControlClient._reader_loop does not notice a session switch: under tmux `detach-on-destroy off` (set in the user's tmux.conf), destroying the attached session moves the live control client to another session (e.g. `aitasks_mob`) instead of emitting %exit, so the backend stays CONNECTED and serves every query from the other project (reproduced with the t2242 fix applied: kill-session -t =zz → display-message answers zz_mob). Needs an attach-time `detach-on-destroy on` for the control client or a `%session-changed`/`%client-session-changed` check that treats a switch as death.

## Diagnostic context

t2242 made `TmuxControlClient._attach_argv` attach with an exact-match `=<session>` target, which closes the prefix-match route at attach and reconnect time. While building its reconnect regression (Case B2 in `tests/test_tmux_control_resilience.sh`), the "destroy the target session" step never triggered a reconnect on the developer machine. The isolated test servers still read the user's tmux.conf, which sets `set -g detach-on-destroy off`. Under that option tmux does not detach a client whose session is destroyed; it switches the client to another session. A direct probe, run with the t2242 fix in place:

- `detach-on-destroy off` → after `kill-session -t =zz`, the backend stays `connected`, the same client object is alive, and `display-message -p '#{session_name}'` returns `zz_mob`.
- `detach-on-destroy on` → state goes to `reconnecting`, the client is dead, and the request returns `(-1, "")`.

So the same cross-project symptom t2242 fixed for attach still exists for an already-attached client whose session goes away. Case B2 works around it by pinning `detach-on-destroy on` on its fixture server. Practical impact is likely limited (the monitor usually runs inside the session that would be destroyed), but a monitor or minimonitor running in another session, or any long-lived control backend, would silently start serving another project's panes.

## Suggested fix

Either set the option per-client at attach (for example, a `set-option -t =<session> detach-on-destroy on` sent over the control channel right after attach — but it is a session option, so it also changes the user's own interactive clients on that session, and `-g` would change the whole server), or have `_reader_loop` treat `%session-changed` / `%client-session-changed` to a session other than `self.session` as death (set `saw_exit`/teardown), so the supervisor's exact-match reconnect takes over. Add a live regression that leaves `detach-on-destroy off` in effect, destroys the target while `<S>_mob` runs, and asserts the backend never answers from the decoy. Include a pre-fix control.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-08T20:16:28Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-09T09:07:00Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-09T09:11:15Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:da81cb4215079907

> **✅ gate:risk_evaluated** run=2026-11-09T09:11:15Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2245/risk_evaluated_2026-11-09T09:11:15Z-risk_evaluated-a1.log`
