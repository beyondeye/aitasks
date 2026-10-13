---
priority: low
effort: low
depends: []
issue_type: test
status: Ready
labels: [tests, tmux, trails]
gates: [risk_evaluated]
anchor: 1957
followup_kind: review_finding
created_at: 2026-10-13 17:19
updated_at: 2026-10-13 17:19
---

## Origin

Spawned from t1971 (review of its new live tmux test).

## Problem

`tests/test_trails_focus_mailbox_live.py` (t1957_2) starts its private tmux
server in `setUp` with `self.client.run(["new-session", "-d", ...])` and no
`-f /dev/null`. Socket isolation (`TMUX_TMPDIR` + `AITASKS_TMUX_SOCKET`) keeps
it off the user's server, but a fresh server still loads the developer's tmux
config (`~/.tmux.conf` / `~/.config/tmux/tmux.conf`). Startup hooks there could
create extra panes or set pane-local options, and then fail the test's
`len(self.panes) == 2` and unset-option assertions for reasons unrelated to the
mailbox code. The verdict depends on whoever runs the suite.

## Fix

Mirror `tests/test_monitor_pane_option_live.py` (t1971):

- Start the server with the global flag:
  `self.client.run(["-f", "/dev/null", "new-session", "-d", "-s", SESSION, ...])`.
  `TmuxClient._argv` builds `tmux -L <sock> -f /dev/null new-session ...`, and
  tmux reads `-f` only for the command that starts the server.
- Keep the static socket-containment assertion before any mutation, and the
  existing pane-count precondition after `new-window`.

## Verification

- `~/.aitask/venv/bin/python -m pytest tests/test_trails_focus_mailbox_live.py -q` passes.
- Optional check: with a scratch config that sets `@aitask_trails_focus`
  globally, passed through `-f`, the old setUp fails the unset-request
  assertion and the new one is unaffected.
