---
Task: t955_manual_verification_harden_tmux_sessions_against_whole_serve.md
Base branch: main
plan_verified: []
---

# Plan: t955 — Manual-verification auto-execution (harden tmux against whole-server teardown)

## Context

t955 verifies t943, which spawns the framework-created tmux **server** inside a
persistent systemd-user service under `session.slice` (via
`ait_tmux_new_session_persistent` in `terminal_compat.sh`, called from
`spawn_session_detached` in `tmux_bootstrap.sh`), so a compositor / `app.slice`
teardown no longer kills the shared server and every project's session with it.
Auto-verification was run autonomously (Step 1.5, autonomous strategy) before
the interactive loop.

**Environment note:** the running shell's own cgroup at verification time was
`/app.slice/tmux-spawn-…scope` (i.e. the pre-t943 placement), and the live
`aitasks` server occupies the default tmux socket. To avoid disturbing that
real server, the helper's exact `systemd-run` / `setsid` invocations were
replicated on **dedicated sockets** (`-L aitverify955A/B/F`) — the helper
hardcodes the default socket, so isolated testing required socket override.
The cgroup-placement flags (`--slice=session.slice`) and lifecycle properties
are identical to the helper.

## Execution Log

### Item 1 — Server escapes app.slice via real launch
- Item text: Server escapes app.slice; cgroup contains `/session.slice/ait-tmux-…service`, not `/app.slice/`; `systemctl --user list-units 'ait-tmux-*'` active.
- Approach: CLI invocation — faithful replica of the helper's `systemd-run --user --slice=session.slice --unit=ait-tmux-… --property=Type=forking --property=KillMode=none --collect` on a dedicated socket.
- Action run: `systemd-run … tmux -L aitverify955A new-session -d -s … -n monitor 'sleep 900'`; then `tmux -L aitverify955A display-message -p '#{pid}'`, `cat /proc/<pid>/cgroup`, `systemctl --user list-units 'ait-tmux-*'`.
- Output (trimmed): cgroup = `/user.slice/user-1000.slice/user@1000.service/session.slice/ait-tmux-aitverify955A_sess-…service`; unit `loaded active running`.
- Verdict: **pass**

### Item 2 — Survives compositor teardown (the real proof)
- Item text: With the server in session.slice, restart the Hyprland compositor → tmux/session survives.
- Approach: Not fully automatable — restarting the live compositor would tear down the user's whole graphical session. Ran a safe MODEL of the cgroup teardown mechanism instead.
- Action run: Started server A in `session.slice`; started server B in a stoppable `app.slice` transient service; `systemctl --user stop <app.slice-unit>` (models compositor/app.slice teardown).
- Output (trimmed): After the stop, A (session.slice) **SURVIVED**; B (app.slice) was **KILLED**. The session.slice unit is a sibling of app.slice, so an app.slice teardown does not reach it.
- Verdict: **defer** — model evidence is strong, but the literal "restart the Hyprland compositor" E2E is destructive and left for the user. One real compositor restart closes this and item 3 together.

### Item 3 — Negative control (app.slice server killed by the SAME teardown)
- Item text: Rerun the teardown with `AIT_NO_SYSTEMD_RUN=1` (server lands in app.slice) and confirm the SAME teardown DOES kill it.
- Approach: Placement half verified autonomously; kill half modeled (shared with item 2's experiment).
- Action run: `AIT_NO_SYSTEMD_RUN=1` → `ait_systemd_user_available` returns unavailable (fallback ladder); the fallback server's cgroup = `/app.slice/tmux-spawn-…scope` (NOT session.slice). In the teardown model, the app.slice server was killed by the same stop the session.slice server survived.
- Output (trimmed): fallback cgroup confirmed app.slice; app.slice server KILLED by unit stop.
- Verdict: **defer** — "the SAME teardown" literally refers to the item-2 compositor restart; close together with item 2.

### Item 4 — Fallback rung on a non-systemd host (or AIT_NO_SYSTEMD_RUN=1)
- Item text: `bash tmux_bootstrap.sh <project>` → `tmux has-session` succeeds, window `monitor` present, behavior identical to before.
- Approach: CLI invocation — faithful replica of the setsid fallback rung on a dedicated socket (helper hardcodes the default socket, occupied by the live server).
- Action run: `AIT_NO_SYSTEMD_RUN=1` source-check of `ait_systemd_user_available`; `setsid tmux -L aitverify955F new-session -d -s … -n monitor 'sleep 900'`; `tmux -L aitverify955F has-session -t '=…'`; `list-windows`.
- Output (trimmed): `ait_systemd_user_available` → unavailable; `HAS_SESSION:yes`; window `monitor` present.
- Verdict: **pass**

### Item 5 — Server cleanly deactivates
- Item text: From inside the ait session, `tmux kill-server` → the `ait-tmux-*.service` unit deactivates (no lingering unit, thanks to --collect / no RemainAfterExit).
- Approach: CLI invocation — `kill-server` on the session.slice server A, then inspect the unit.
- Action run: `tmux -L aitverify955A kill-server`; `systemctl --user list-units 'ait-tmux-*'`; `systemctl --user show <unit> -p ActiveState -p LoadState`; `systemctl --user is-active <unit>`.
- Output (trimmed): `list-units 'ait-tmux-*'` empty; `LoadState=not-found`, `ActiveState=inactive`; `is-active` exit 4. No lingering unit.
- Verdict: **pass**

## Cleanup

- Killed test tmux servers on sockets `aitverify955A`, `aitverify955B`, `aitverify955F` (all confirmed gone).
- Transient units `ait-tmux-aitverify955A_sess-…` and `ait-verify-negctrl-appslice-…` collected (`--collect`) / `reset-failed`; no lingering test units.
- Removed scratch state file `/tmp/aitverify955_state.txt`.
- The user's live default-socket `aitasks` server was never touched (verified before and after).
- Pre-existing `ait-tmux-aitverify962-test.service` belongs to a different session (t962) and was intentionally left alone.

## Final Implementation Notes

- **Actual work done:** Autonomous auto-verification of all 5 checklist items. Items 1, 4, 5 passed via direct, faithful replication of the t943 code path on isolated sockets. Items 2 and 3 deferred: the literal proof (restarting the live Hyprland compositor) is destructive, so a safe cgroup-teardown model was run instead, demonstrating that a session.slice server survives an app.slice-unit teardown while an app.slice server is killed by it.
- **Deviations from plan:** Used dedicated tmux sockets (`-L`) instead of the helper's default socket, because the live `aitasks` server occupies the default socket and the helper hardcodes it. The `systemd-run`/`setsid` flags were otherwise identical.
- **Issues encountered:** None. The teardown could not be the literal compositor restart (would disrupt the user's desktop); modeled via `systemctl --user stop` of a sibling app.slice unit.
- **Key decisions:** Defer (not pass) for items 2/3 since their definitive proof is the human-run compositor restart; model evidence recorded as corroboration.
- **Upstream defects identified:** None.
