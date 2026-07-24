---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [reporting]
gates: [risk_evaluated]
anchor: 1162
created_at: 2026-07-24 15:17
updated_at: 2026-07-24 15:17
---

## Origin

Risk-mitigation ("after") follow-up for t1217, created at Step 8d after implementation landed.

## Risk addressed

Goal-achievement — `lib/work_report_gather.py` keeps its `stats/` `sys.path`
insert, so the `lib/` layer direction is repaid for `board/` but **not fully
restored**. From t1217's plan:

> One deliberate exclusion: `lib/work_report_gather.py` keeps its `stats/`
> `sys.path` insert, so the `lib/` layer direction is repaid for `board/` but
> **not fully restored**. This is out of scope for t1217 and is surfaced (not
> hidden) via the guard's allowlist entry · severity: low

## Goal

Finish restoring the `lib/` layer direction by removing the last upward reach
from the base layer into a sibling TUI package.

`.aitask-scripts/lib/work_report_gather.py:47-51` currently runs:

```python
for _sub in ("stats",):
    _sub_dir = os.path.join(_SCRIPTS_DIR, _sub)
    if _sub_dir not in sys.path:
        sys.path.insert(0, _sub_dir)
```

solely to satisfy `from stats_data import DAY_NAMES, collect_stats` (line 57).

Relocate the shared surface (`DAY_NAMES`, `collect_stats` — check for other
consumers first) into the base layer, exactly as t1217 did for `task_yaml.py`,
then drop the insert.

## Key files

- `.aitask-scripts/lib/work_report_gather.py` — the importer (drop the loop)
- `.aitask-scripts/stats/stats_data.py` — the module holding the shared surface
- `.aitask-scripts/stats/stats_app.py` — the other consumer; must keep working
- `tests/test_no_lib_to_tui_import.sh` — **remove** the
  `work_report_gather.py:stats` allowlist entry; the allowlist should then hold
  only the `shortcut_scopes.py:*` reflection-loader entry

## Verification

- `bash tests/test_no_lib_to_tui_import.sh` — must pass with the allowlist
  entry removed (that removal is the acceptance criterion)
- `bash tests/test_work_report_gather.sh` — includes the board-equivalence oracle
- `bash tests/test_stats_data.sh`, `tests/test_stats_multistage.py`,
  `tests/test_stats_include_registered.py`
- `bash tests/run_all_python_tests.sh`
- Direct-invocation check (the suite runner exports sibling dirs on PYTHONPATH
  and would mask a broken bootstrap):
  `source .aitask-scripts/lib/python_resolve.sh; PY="$(require_ait_python)";`
  `env -u PYTHONPATH "$PY" -c "import sys; sys.path.insert(0, '.aitask-scripts/lib'); import work_report_gather"`
- `env -u PYTHONPATH "$PY" -c "import sys; sys.path.insert(0, '.aitask-scripts/stats'); import stats_app"`
