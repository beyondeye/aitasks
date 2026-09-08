---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing, python]
gates: [risk_evaluated]
anchor: 1705
followup_kind: upstream_defect
created_at: 2026-09-08 11:28
updated_at: 2026-09-08 11:28
---

## Origin

Spawned from t1729 during Step 8b review.

## Upstream defect

- `tests/test_minimonitor_concern_smoke.py:541 — builds its fake agent binaries with `shutil.copy2(sys.executable, ...)` and states in a comment that "`pane_current_command` must really be the agent name — rung 1 of `agent_key_from_pane` reads it, and a `python3` pane would resolve to \"\" and silently classify unscoped". On macOS that premise is false, so every assertion resting on it passes vacuously.`

## Diagnostic context

Measured during t1729 (macOS 15 / arm64, Homebrew CPython 3.13 in
`~/.aitask/venv`):

A copy of `sys.executable` does **not** report the copied file's name. The
Homebrew `python3.13` binary re-execs the framework app bundle, so the process
tmux sees is the bundle's:

```
$ cp "$(python3 -c 'import sys;print(sys.executable)')" /tmp/x/a_claude
$ tmux new-session -d "/tmp/x/a_claude -c 'import time;time.sleep(30)'"
$ tmux list-panes -a -F '#{pane_current_command}'
Python
```

`agent_key_from_command` lowercases the basename and looks it up in
`AGENT_KEYS`; `python` is not a member, so it returns `""`. The module is green
today, which is exactly the problem — the assertions that depend on the pane
resolving to `codex` / `opencode` / `claude` are not testing what their comment
claims.

Note this is the *same defect family* t1729 fixed in `test_agent_keys.py` and
`test_prompt_scoping_live.py`, but a **different** binary: those copied
`/bin/sleep` (which macOS refuses to execute at all), this one copies the Python
interpreter (which runs, but under the wrong name).

## Suggested fix

`tests/lib/fake_agent_binary.py` (added by t1729) already solves exactly this —
it produces an executable whose name really is the agent name, verifying each
rung by running it. This module needs the **real-file** form (no
`allow_symlink`), because it reads pane commands through tmux:

```python
from fake_agent_binary import FakeAgentBinaryUnavailable, fake_agent_binary
```

Two things to check while porting:

1. The module currently runs `fake stub frame H` — a Python stub script as
   `argv[1]`. The ladder's binaries are `sleep`-shaped and take a duration, so
   the pane command needs rethinking: either keep a copied interpreter for the
   *stub-running* role and use a ladder binary only where the **name** matters,
   or replace the stub mechanism. Do not assume a drop-in swap.
2. Confirm the assertions actually change state once the premise holds — if they
   still pass identically, they were not testing the pane resolution and the
   comment should be corrected instead.

Follow `tests/lib/fake_agent_binary.py`'s docstring for why a symlink and an
`exec -a` rename both fail here (tmux names a process after the resolved
executable, never after `argv[0]`).
