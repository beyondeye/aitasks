---
Task: t1974_isolate_trails_focus_live_test_tmux_config.md
Base branch: main
Output branch: main
---

# t1974 — Isolate the trails focus live test from the developer's tmux config

## Context

`tests/test_trails_focus_mailbox_live.py` (t1957_2) starts its private tmux
server in `setUp` without `-f /dev/null`. Socket isolation keeps it off the
user's server, but a fresh server still sources `~/.tmux.conf` /
`~/.config/tmux/tmux.conf`; hooks there (e.g. a `session-created` split) or
global options can break `len(self.panes) == 2` and the unset-option
assertions, so the verdict depends on who runs the suite. The sibling test
`tests/test_monitor_pane_option_live.py:64-67` (t1971) already does it right.

`TmuxClient._argv` (`.aitask-scripts/lib/tmux_exec.py:236`) builds
`tmux -L <sock> <args...>`, so passing `-f /dev/null` as the first caller args
yields `tmux -L ait1957 -f /dev/null new-session ...` — valid global-flag
placement; tmux reads `-f` only for the command that starts the server.

## Change (single file: `tests/test_trails_focus_mailbox_live.py`, setUp)

Replace

```python
        rc, _ = self.client.run(["new-session", "-d", "-s", SESSION,
                                 "-x", "80", "-y", "24", "sleep 600"])
```

with (mirroring t1971's comment and layout)

```python
        # `-f` is a global flag, read only by the command that starts the server.
        rc, _ = self.client.run(["-f", "/dev/null", "new-session", "-d",
                                 "-s", SESSION, "-x", "80", "-y", "24",
                                 "sleep 600"])
```

Keep unchanged: the static `socket_args == ["-L", "ait1957"]` containment
assertion before any mutation, and the `len(self.panes) == 2` precondition after
`new-window`. Later commands (`new-window`, the launcher's window in
`test_no_receiver_opens_a_trails_window`) talk to the already-running server, so
they need no `-f`.

Also update the module docstring's "Runs on a throwaway server" paragraph with
one clause noting the server starts with `-f /dev/null` so the developer's tmux
config cannot add panes or options.

## Verification

1. `~/.aitask/venv/bin/python -m pytest tests/test_trails_focus_mailbox_live.py -q` passes.
2. Negative control (scratchpad only, nothing in the repo): a scratch
   `HOME` / `XDG_CONFIG_HOME` holding a `.tmux.conf` with
   `set-hook -g session-created 'split-window -d "sleep 600"'`:
   - pre-fix copy of the test (from `git show HEAD:...`, `REPO_ROOT` pinned to
     the repo) under that HOME → fails the pane-count precondition;
   - fixed test under that HOME → passes.
3. Step 9 (Post-Implementation): commit, archive, push per the workflow.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** `setUp` in `tests/test_trails_focus_mailbox_live.py` now starts the private server with `["-f", "/dev/null", "new-session", ...]` (same comment and layout as `tests/test_monitor_pane_option_live.py`); the module docstring notes the config isolation. The socket-containment assertion and the 2-pane precondition are unchanged.
- **Deviations from plan:** None.
- **Issues encountered:** None. Verification: the live test passes 5/5. Negative control in the scratchpad: with a scratch `HOME`/`XDG_CONFIG_HOME` whose `tmux.conf` sets `set-hook -g session-created 'split-window -d "sleep 600"'`, the pre-fix copy (from `git show HEAD:`) failed all 5 tests at the pane-count precondition (`3 != 2`), and the fixed copy passed 5/5.
- **Key decisions:** Used a `session-created` split hook as the hostile config rather than a global `@aitask_trails_focus` option. A global user option is not reliably visible to a pane-scoped read without `-A`, but an extra pane always breaks the precondition.
- **Upstream defects identified:** None
