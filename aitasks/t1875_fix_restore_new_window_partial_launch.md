---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [frozen, session_persistence]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1847
followup_kind: upstream_defect
created_at: 2026-09-24 11:37
updated_at: 2026-09-24 15:52
---

## Origin

Spawned from t1847 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agent_restore.py:~585 — _launch_into_new_window leaves the new agent window untracked when launch_in_tmux returns no pid or a -1 rc after the server created the window (the partial-launch/uncertain-rc class agent_reopen handles with its attempt-name protocol)`

## Diagnostic context

A gone-pane restore (`aitask_frozen.sh restore <id>` whose recorded pane no
longer exists) starts the replacement agent with `launch_in_tmux(...,
new_window=True)` and then resolves its pane id with
`resolve_pane_id_by_pid(session, pid)`. Three partial-success shapes leave a
running agent window that no record tracks, while `_rollback` puts the record
back to `frozen` as if nothing had launched:

1. `launch_in_tmux` returns `(None, None)` — `new-window` succeeded but its
   `-P` output did not parse into a pid;
2. the tmux gateway returns rc `-1` (`TmuxClient.run` folds a timeout into
   `(-1, "")`) after the server already created the window;
3. `resolve_pane_id_by_pid` misses the pid (t1847 fixed one cause — the bare
   `=<session>` target — but a race or a vanished pane still misses).

t1847's reopen coordinator (`lib/agent_reopen.py`) faced the same class for
viewer windows and solved it with an ATTEMPT-NAME identity: the window is
created detached under `aitask-reopen-<id>-<nonce>` (set atomically by tmux),
identified from `-P` output or by that name, stamped under a name guard, and
cleaned up only with guarded kills (`kill_if_stamped` / name-guarded), never
unstamping first; survivors are adopted on the next run.

## Suggested fix

Apply the same protocol to `_launch_into_new_window`: launch under a
per-attempt name, resolve the pane from `-P` output or the name lookup (with
`=<session>:` targets), and on any failure after the window exists either
record it or remove it with a guarded kill — never report a rollback while a
launched agent is still running untracked. Add live coverage alongside
`tests/test_frozen_reopen_live.sh` (it already has the synthetic-root + fake
`claude` fixture for real restores).
