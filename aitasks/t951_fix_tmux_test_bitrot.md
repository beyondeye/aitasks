---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing, tmux]
created_at: 2026-06-10 08:42
updated_at: 2026-06-10 08:42
---

## Origin

Spawned from t936 during Step 8b review. t936 relaxed the tmux-test guard so
the 8 tmux/multi-session tests run alongside a live tmux session. With the
tests now actually runnable, two of them surfaced **pre-existing** failures
(proven identical on `main`/HEAD in a clean, no-tmux environment — independent
of the t936 guard change).

## Upstream defect

- `.aitask-scripts/monitor/tmux_monitor.py:42 — relative import `from .prompt_patterns import PromptPattern, all_patterns` fails when `tests/test_multi_session_monitor.sh` runs `python -c "import tmux_monitor as tm"` with `PYTHONPATH` set to the monitor dir. tmux_monitor is imported as a top-level module, so its package-relative import raises `ImportError: attempted relative import with no known parent package`. Fix is in the test's invocation (import as `monitor.tmux_monitor` with `PYTHONPATH=.aitask-scripts`, matching the pattern used by test_tmux_run_parity.sh / test_tmux_control.sh) or by making the import robust.`
- `tests/test_multi_session_primitives.sh — stale assertion: expects `AitasksSession` FIELDS `project_name,project_root,session` but the dataclass now also exposes `is_live,is_stale` (actual: `is_live,is_stale,project_name,project_root,session`). 19/20 sub-checks pass; the expected-fields list needs updating to match the current dataclass.`

## Diagnostic context

Surfaced while verifying t936: running all 8 tmux tests with a live marker
session on the default socket, 6 passed and these 2 failed. The failures are
not socket/isolation related — one is a Python packaging/import-invocation
issue, the other a stale field-set assertion. Both reproduce on HEAD with the
original guard once a tmux-free terminal lets the test body run, confirming
they predate t936.

## Suggested fix

- test_multi_session_monitor.sh: import via the package path
  (`from monitor.tmux_monitor import TmuxMonitor` with `PYTHONPATH=.aitask-scripts`)
  as the sibling tmux tests already do, instead of `import tmux_monitor`.
- test_multi_session_primitives.sh: update the expected FIELDS list to include
  `is_live` and `is_stale` (or assert a subset).
