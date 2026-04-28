---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Ready
labels: [testing, bash_scripts]
created_at: 2026-04-27 17:24
updated_at: 2026-04-27 17:24
boardidx: 10
---

The macOS audit (t658) baseline run revealed 11 test failures all caused by `ModuleNotFoundError: No module named 'yaml'` (or `textual` / `rich`). The repo has a venv at `~/.aitask/venv/` with PyYAML, textual, and rich installed, but these tests invoke plain `python3`, which on macOS is system Python without those packages. They reproduce the same way on any host where the system Python lacks the deps.

## Affected tests

- `tests/test_agentcrew_error_recovery.sh`
- `tests/test_agentcrew_terminal_push.sh`
- `tests/test_apply_initializer_output.sh`
- `tests/test_apply_initializer_tolerant.sh`
- `tests/test_explain_context.sh`
- `tests/test_explain_format_context.sh`
- `tests/test_install_merge.sh`
- `tests/test_multi_session_minimonitor.sh`
- `tests/test_multi_session_monitor.sh`
- `tests/test_stats_verified_rankings.sh`
- `tests/test_tui_switcher_multi_session.sh`

## Reference pattern

`tests/test_crew_groups.sh` already does the right thing:
```bash
PYTHON=python3
[[ -x /Users/$USER/.aitask/venv/bin/python ]] && PYTHON=/Users/$USER/.aitask/venv/bin/python
```
(It then breaks on a different issue — see the sibling task on hand-curated copy lists.)

## Suggested approach

Either:
1. Add a shared helper `tests/lib/venv_python.sh` exposing `AITASK_PYTHON` (resolves `~/.aitask/venv/bin/python` if present, falls back to `python3`), source it in each affected test, and replace the literal `python3` calls; or
2. Have each test do the inline two-line check above near the top.

Option 1 is preferred — single point of fix when the venv path conventions change.

## Verification

After the fix, on a host where `~/.aitask/venv/bin/python` exists with `yaml`/`textual`/`rich` installed, all 11 tests above must report PASS. On a host without the venv, they must fall back gracefully — either still passing (system Python has the deps) or skipping with a clear message (system Python doesn't, e.g., `SKIP: PyYAML not available`).
