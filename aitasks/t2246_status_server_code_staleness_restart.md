---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [monitor, minimonitor]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2034
implemented_with: claudecode/opus5_5
created_at: 2026-11-08 17:57
updated_at: 2026-11-09 10:33
---

## Problem

The shared monitor status server (t2037) is keyed only on **(tmux socket, framework
`VERSION`)**. Every client (`ait monitor`, `ait minimonitor`, applink) reads its
producer state (snapshots, discovery, the session map) from that server. A commit that
changes producer-side code without bumping `VERSION` (any dev-checkout commit) never
retires the running server. The server only exits after its idle grace (30 s with no
subscriber), and that never fires while at least one minimonitor is open, which is
always the case in practice. So **every producer-side monitor fix is silently masked**
until someone happens to kill the server by hand.

We need a deliberate procedure for **detecting** that the running server's code differs
from what the clients (and the on-disk checkout) expect, and for **deciding** what to do
about it: restart, route to a fresh server, or drain the old one.

## How it was found (durable evidence, 2026-11-08)

Symptom: the `agent-sitrep` window (sitrep agent + sitrep TUI + minimonitor) showed **two**
minimonitor items, one for the agent and one for the TUI. It should show only the agent.

- The filter already exists. Since t2211_2 (commit f71802d35, 2026-11-08 09:01),
  `TmuxMonitor._parse_list_panes` drops any pane stamped `@aitask_sitrep_tui_root`
  (`.aitask-scripts/monitor/monitor_core.py`, the `is_sitrep_tui_pane(...)` → `continue`
  branch).
- The live stamps were correct. `tmux list-panes -a` showed agent `%603`
  `@aitask_sitrep_root=/home/ddt/Work/aitasks`, TUI `%650`
  `@aitask_sitrep_tui_root=/home/ddt/Work/aitasks`, and minimonitor `%605`
  `@aitask_monitor_kind=minimonitor:…`.
- Every minimonitor process had started after f71802d35.
- The status server process was
  `status_server.py serve --socket /run/user/1000/aitasks/monitor-2d0b888256e321e6-0.40.1.sock --version 0.40.1 …`,
  pid 3870908, started **2026-11-06 11:14**, two days before the filter landed. Its
  discovery is the pre-t2211_2 code, so it publishes the TUI pane as an agent card.
  `VERSION` was 0.40.1 throughout, so the probe/`ensure` reused it.
- Manual workaround (not the fix): kill the stale server pid. Clients fall back, then
  `ensure` starts a server running the current code.

## Current mechanics (what the fix must change)

- `status_server.py` `server_paths()`: the socket stem is `monitor-<tmux key>-<version slug>`.
- `ensure()`: `probe()` → `_welcome_pid(msg, version)` accepts any welcome whose
  `version` matches. If it is reachable, it returns `RUNNING` and is reused.
- The welcome is `{"type": "welcome", "proto": …, "version": …, "server": {"impl": "python", "pid": …}}`.
  It carries no code identity.
- `status_client.MonitorClient`: on connect it raises `version_mismatch` only on `version`
  inequality.
- Spec: `aidocs/framework/monitor_status_protocol.md` (keying, lifecycle/idle, the
  "breaking edit" note around the version field). Read it before touching the welcome.

## Scope

1. **Code identity.** The server reports an identity for the producer code it actually
   runs, and clients and `ensure` can compute the same identity from the checkout.
   - It must be **content-derived over every input the producer consumes**, never
     mtime/stat freshness. One candidate is a digest of the source files of every
     framework module loaded at server start. Planning must check whether
     lazily-imported modules escape that set.
   - A server that reports **no** identity (the current server, and any legacy one)
     must read as mismatched/unknown on every consumer. It must never be treated as a
     match.
   - Keep it impl-agnostic so the Go server (t2038, postponed) can report its binary's
     identity through the same field.
2. **Decision policy.** Planning picks one and records why the others were rejected.
   - (a) Key the socket on the code identity too. New clients reach a fresh server, and
     the old one drains through its grace as old clients exit. Cost: two scanners
     coexist transiently.
   - (b) A client with newer code asks the old server to retire. This must not strand
     clients that still run the old code.
   - (c) The server watches its own inputs and exits or re-execs when they change, and
     clients reconnect.
   - Constraints: never kill a server that other live clients still depend on without
     a reconnect path. The existing opt-out `AITASKS_MONITOR_SERVER=0` must keep working.
     Recovery must be bounded and report the actual state (it must not loop).
3. **Operator verbs.** Add `status` (pid, start time, version, reported identity,
   match-vs-checkout) and an explicit `restart`/`retire` to `status_server.py`. Planning
   decides whether to also surface them through an `ait` command. A new helper path must
   follow `aidocs/framework/aitasks_extension_points.md`.
4. **Visible signal.** When connected to a server whose identity does not match,
   `ait monitor` and `ait minimonitor` show it, e.g. alongside the existing
   server/fallback mode indicator. Being silently masked is exactly the failure here.
5. **Docs.** Update `aidocs/framework/monitor_status_protocol.md` (welcome field, keying,
   lifecycle, policy). Check whether the welcome addition needs a `proto` bump.

## Verification

- Tests: a stub server whose welcome reports a different identity, and one that reports
  none. Assert the chosen policy in each case, with a pre-fix control showing the
  current code reuses both.
- Live check: with the fix in place and a server started from an older checkout, open
  the `agent-sitrep` window. Its minimonitor lists exactly **one** item (the sitrep
  agent), and the sitrep TUI pane is absent from both the monitor and minimonitor lists.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2245** id=2026-11-09T09:10:41Z.20adfaf282ea0672e7d2a6a4 from=t2245 from_verified=yes at=2026-11-09T09:10:41Z base=a5763bd4eaaf17b0afa044e1f1864ddfc2836923 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t2245 (claim — verify against the tree before relying on it).
> | 
> | t2245 committed a5763bd4e on main, touching three files you have uncommitted edits in:
> | - .aitask-scripts/monitor/status_server.py — `_start_control_client` and `_pick_control_session` gained a keyword-only `live_mapping: bool = False` parameter (backward compatible). `_handle_exit_seen` now calls `_start_control_client(live_mapping=True)`. On the live path `_pick_control_session` calls `self.monitor.invalidate_sessions_cache()` and ignores the cached `self._mapping`, because both still list a session that just went away. Any new producer slice or fake you write must provide `invalidate_sessions_cache()`.
> | - aidocs/framework/monitor_status_protocol.md — only the `%exit` bullet (session switch under detach-on-destroy off; restart picks from a fresh session query). Your `Signal.` bullet edit and your other sections were left out of the commit.
> | - tests/test_monitor_status_server_live.py — only the `Covered:` docstring lines and new TmuxExitTests cases (`control_clients`, `test_session_switch_restarts_the_control_client`, `test_session_destroy_restarts_on_a_live_session`, `_served_session_destroyed`). Your EnsureTests block was left out.
> | 
> | The commit was built against HEAD with only t2245's hunks and was not taken from your working tree. As of this moment (a moment-relative claim, not dated by the SHA), the working-tree copies of these files already contained t2245's hunks, so `git diff` on them should now show only your own changes. HEAD moved under your in-flight edits. Also as of this moment, the working-tree status_server.py imports a `status_restart` module that was not on disk, so the status-server tests could not run from the shared tree.

> **👁 note:read** id=2026-11-09T09:46:59Z.be1f8b93273fa30b96549bf6 by=t2246 at=2026-11-09T09:46:59Z mode=explicit ids=2026-11-09T09:10:41Z.20adfaf282ea0672e7d2a6a4

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-09T08:33:17Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-09T09:48:24Z status=pass attempt=1 type=human
