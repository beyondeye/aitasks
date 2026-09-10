---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [tmux, codeagent, session_persistence]
gates: [risk_evaluated]
anchor: 1705
followup_kind: upstream_defect
created_at: 2026-09-10 14:57
updated_at: 2026-09-10 14:57
---

## Origin

Spawned from t1773 during Step 8b review (plan §9.1).

## Upstream defect

- `.aitask-scripts/lib/agent_freeze.py:902-990` — `drop_record()` probes the pane
  (`frozen_ops.probe_pane`, :964) and then kills it (`kill-window` / `kill-pane`,
  :981) in a **separate** tmux call. A tmux server restart between the two can
  hand the kill an unrelated agent's recycled `%N`.
- `.aitask-scripts/lib/agent_freeze.py:659-676` — `_respawn_standin()` issues a
  bare `respawn-pane -k` on the recorded pane (`frozen_ops.respawn`, :676) with no
  stamp check in the same dispatch — the same race.

## Diagnostic context

t1773 measured (tmux 3.6a) that pane ids are monotonic within a server and never
reused, but a **restarted server renumbers from `%0`** — so a server restart is
the only way a recorded `%N` can name a different pane, and a two-call
probe-then-act leaves exactly that window open. t1773 closed it for `restore`
with `agent_frozen_ops.respawn_if_stamped()`: the stamp check and the destructive
command travel as one `if-shell -F` dispatch, and success is proved by a per-call
token written last in the matched branch — never by a pid delta, which across a
restart compares two different panes. `tests/test_frozen_respawn_atomic_live.sh`
pins each tmux fact and drives the real restart race (Part B).

`drop` was deliberately left out of t1773: its kill is the one path that deletes
a session's only capture, so it gets its own task rather than riding along in a
bug fix. Until this lands, `restore` and `drop` / `_respawn_standin` differ in
their safety guarantee.

## Suggested fix

Route `_respawn_standin` through `respawn_if_stamped`. For `drop_record`, add a
stamp-conditional kill primitive in `agent_frozen_ops` (same `if-shell -F` +
branch-token shape) and keep its tri-state preflight (`unknown` must still fail
closed). Extend the atomic live suite with a kill-side Part B.
