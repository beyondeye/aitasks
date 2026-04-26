---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [agentcrew, brainstorming]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-26 12:13
updated_at: 2026-04-26 12:15
---

## Symptom

In the `ait brainstorm` TUI for an active crew (e.g. `brainstorm-635`), pressing
"Start Runner" shows the toast `Runner started`, but the runner is never
actually alive: agents stay in `Waiting`, no `_runner_alive.yaml` is written,
and the dashboard never advances past "imported proposal, awaiting reformatting".

## Root cause

`./.aitask-scripts/agentcrew/agentcrew_runner.py` only adds
`.aitask-scripts/` to `sys.path` (line 18):

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

It then imports `from lib.agent_launch_utils import ...`, which works because
`lib` is a folder under that path. But inside
`.aitask-scripts/lib/agent_launch_utils.py:23`:

```python
from tui_registry import TUI_NAMES as _DEFAULT_TUI_NAMES
```

This is a **flat** import — it requires `.aitask-scripts/lib/` itself to be
on `sys.path`. The runner crashes immediately with:

```
ModuleNotFoundError: No module named 'tui_registry'
```

Confirmed by running:

```
./ait crew runner --crew brainstorm-635 --check
```

Every other importer of `agent_launch_utils` (board, monitor, minimonitor,
codebrowser, settings, brainstorm_app, tmux_monitor, tui_switcher,
agent_command_screen, history_screen) adds `lib/` to `sys.path`. Only
`agentcrew_runner.py` was missed.

The `tui_registry` import was added by commit `7620450b` (t601 — "Centralize
TUI registry and merge tui_window_names config"), so the runner has been
broken for **all** crew launches since that commit.

## Why the TUI lies

`./.aitask-scripts/agentcrew/agentcrew_runner_control.py:67-78` `start_runner()`:

```python
def start_runner(crew_id: str) -> bool:
    try:
        subprocess.Popen(
            [AIT_PATH, "crew", "runner", "--crew", crew_id],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except OSError:
        return False
```

`Popen` succeeds the moment the OS spawns the child — it does not verify the
child stayed alive. With `stderr=DEVNULL` the import traceback is fully
silenced, so the TUI's `notify("Runner started")` is shown even when the
child died milliseconds later.

## Fix

### Primary (1 line — restores function)

Add the missing `lib/` `sys.path` insert in
`.aitask-scripts/agentcrew/agentcrew_runner.py` near the existing one:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
```

### Hardening (recommended — surfaces future crashes)

In `agentcrew_runner_control.start_runner()`:

1. Capture stderr to a temp log file (or a per-crew log under the worktree)
   instead of `DEVNULL` — discarding the traceback is what hid this bug for
   weeks.
2. After `Popen`, briefly poll `proc.poll()` for ~1 s. If the child exited
   non-zero in that window, return `False` and surface the captured stderr
   tail in the TUI's `notify(..., severity="error")`.

This makes the next regression visible the moment the user clicks "Start
Runner" instead of after they wonder why nothing happens for minutes.

## Verification

1. With the fix applied:
   ```bash
   ./ait crew runner --crew brainstorm-635 --check
   ```
   should print `Runner: not running (no alive file)` (exit 1) instead of the
   `ModuleNotFoundError` traceback.

2. In the brainstorm TUI on `crew-brainstorm-635`, pressing **Start Runner**
   should:
   - write `.aitask-crews/crew-brainstorm-635/_runner_alive.yaml` with
     `status: running` and a fresh `last_heartbeat`,
   - move the `initializer_bootstrap` agent from `Waiting` → `Ready` →
     `Running` within one runner interval,
   - update `_crew_status.yaml` from `Initializing` to `Running`.

3. Regression check: temporarily break the runner import (e.g. add
   `import nonexistent_module` at the top of `agentcrew_runner.py`),
   click **Start Runner** in the TUI, and confirm it now shows an error
   toast (not "Runner started").

## Affected entry points

Any code path that invokes `ait crew runner` for an existing crew is broken
until the fix lands. Confirmed sites:
- Brainstorm TUI **Start Runner** button (`brainstorm_app.py:2899-2908`)
- Brainstorm CLI `start-runner` subcommand (`brainstorm_cli.py:54,67-70`)
- Any direct shell invocation: `./ait crew runner --crew <id>`

## Notes

- This is a regression-fix; no behavior change beyond restoring the
  pre-t601 import path.
- The hardening change is small but valuable — keep it in scope unless
  it grows beyond ~30 LOC, in which case split it into a follow-up.
