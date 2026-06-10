---
Task: t962_manual_verification_harden_launch_in_tmux_python_server_crea.md
Base branch: main
plan_verified: []
---

# Plan: t962 — Manual-verification auto-execution (harden launch_in_tmux Python server creation)

## Context

t962 verifies **t956**, which hardens the Python `launch_in_tmux` new-session
path so that when it genuinely creates the tmux **server** (no server running
yet) the server is spawned inside a persistent `session.slice` systemd-user
service — mirroring t943's bash `ait_tmux_new_session_persistent`. The
load-bearing flag is `systemd-run --user --slice=session.slice` with
`KillMode=none`, so a compositor / `app.slice` teardown can no longer reap the
server. When a server is already running the call is a plain *attach* (no
systemd-run wrapper).

Code under verification: `.aitask-scripts/lib/agent_launch_utils.py`
(`_systemd_user_available`, `_persistent_new_session_prefix`,
`_new_session_tmux_argv`, `launch_in_tmux`).

## Environment notes

- Host `omg16`, `systemctl --user is-system-running` = running, all of
  `systemd-run`/`systemctl`/`systemd-escape`/`setsid`/`tmux` present.
- This agent's own shell runs in
  `app.slice/app-ghostty-surface-transient-2801.scope`, and the user's live
  tmux server (default socket, session `aitasks`) is attached. Therefore the
  literal manual steps (no-server-on-default-socket launch; **restart the
  Hyprland compositor**; stop a *real* sibling `app-*.scope`) were **not** run —
  they would disturb or kill this live session. Each was substituted with a
  faithful, self-contained experiment on a **private tmux socket** (`-L`) and
  **throwaway** `app.slice`/`session.slice` systemd units, exercising the real
  t956 code to generate argv. The checklist's parenthetical explicitly sanctions
  the "`systemctl --user stop` a sibling `app-*.scope`" alternative to the
  compositor restart.

## Execution Log

### Item 1 — server lands in session.slice, not app.slice
- Item text: From a plain terminal with NO tmux server running, launch via the
  TUI new-session path; confirm the server cgroup is `/session.slice/ait-tmux-*`,
  not `/app.slice/`.
- Approach: drive the real `_new_session_tmux_argv` with `get_tmux_sessions`
  monkeypatched to `[]` (simulate no server), then execute the emitted argv on a
  private socket `-L aitverify962`.
- Action run:
  - argv from code = `['systemd-run','--user','--slice=session.slice',
    '--unit=ait-tmux-aitverify962-…','--property=Type=forking',
    '--property=KillMode=none','--collect','--quiet','--','tmux','new-session',
    '-d','-s','aitverify962','-n','monitor','-c','/tmp','sleep 600']`
  - launched same prefix with `tmux -L aitverify962 …`; `cat /proc/<srv>/cgroup`.
- Output (trimmed): server cgroup =
  `/user.slice/user-1000.slice/user@1000.service/session.slice/ait-tmux-aitverify962-test.service`;
  NOT in app.slice.
- Verdict: **pass**

### Item 2 — session.slice server survives the teardown
- Item text: with that server in session.slice, restart the Hyprland compositor
  (or `systemctl --user stop` a sibling `app-*.scope`); confirm `tmux
  list-sessions` still works.
- Approach: keep the Item-1 session.slice server alive; tear down throwaway
  `app.slice` units (`systemctl --user stop`) — the sanctioned sibling-scope
  substitute for the compositor restart.
- Action run: stopped `ait962ctrl-app` (during Item 3) and a second
  `ait962sibling-app`, re-checking `tmux -L aitverify962 list-sessions` after each.
- Output (trimmed): server survived both teardowns; still
  `aitverify962: 1 windows`, pid 3570650 still in
  `…/session.slice/ait-tmux-aitverify962-test.service`.
- Verdict: **pass** (literal compositor restart not executed — would kill this
  live session; substituted with sibling app.slice-scope teardown)

### Item 3 — control: AIT_NO_SYSTEMD_RUN=1 lands in app.slice and is killed
- Item text: repeat the no-server launch with `AIT_NO_SYSTEMD_RUN=1`; server
  lands in `/app.slice/` and the same teardown kills it.
- Approach: confirm the control argv; then trap a tmux server inside a throwaway
  `app.slice` unit (`KillMode=control-group`, the default the fix avoids) and
  stop the unit.
- Action run:
  - With `AIT_NO_SYSTEMD_RUN=1`: `_systemd_user_available()` = False,
    `_persistent_new_session_prefix` = None, argv =
    `['setsid','tmux','new-session','-d','-s','aitverify962c','-n','monitor',
    '-c','/tmp','sleep 600']` (no session.slice).
  - `systemd-run --user --slice=app.slice --unit=ait962ctrl-app
    --property=KillMode=control-group … tmux -L ait962ctrl new-session …`;
    server cgroup confirmed under `/app.slice/ait962ctrl-app.service`.
  - `systemctl --user stop ait962ctrl-app`.
- Output (trimmed): after stop, `tmux -L ait962ctrl list-sessions` failed —
  server killed by the app.slice teardown (expected contrast).
- Verdict: **pass** (literal launcher-scope = this agent's ghostty scope could
  not be torn down safely; demonstrated the identical app.slice + control-group
  kill mechanism via a throwaway unit)

### Item 4 — already-running server: plain attach, no spurious unit
- Item text: when a tmux server is ALREADY running, the new-session launch
  attaches plainly with no spurious `ait-tmux-*` transient systemd unit
  (`systemctl --user list-units 'ait-tmux-*'`).
- Approach: with the user's default-socket server present, inspect the real
  `_new_session_tmux_argv` output, then do a live throwaway attach launch and
  diff the unit list.
- Action run: `get_tmux_sessions()` truthy → argv =
  `['tmux','new-session','-d','-s','aitverify962b','-n','monitor','sleep 5']`
  (no systemd-run, no setsid); `tmux new-session -d -s aitverify962b …` on the
  default socket; `systemctl --user list-units 'ait-tmux-*'` before/after diff;
  killed throwaway session.
- Output (trimmed): NEW_AIT_TMUX_UNITS = 0; only the unrelated pre-existing
  leftover unit present.
- Verdict: **pass**

## Cleanup
- Killed private tmux servers: `aitverify962`, `ait962ctrl`, `ait962sib`.
- Stopped/GC'd throwaway systemd units: `ait-tmux-aitverify962-test.service`,
  `ait962ctrl-app`, `ait962sibling-app` (all `--collect`; none remain loaded).
- Removed `/tmp/aitverify962_units_*.txt`.
- Left untouched: the user's default-socket `aitasks` server and the unrelated
  `ait-tmux-aitverify955A_*` leftover from a prior verification.
