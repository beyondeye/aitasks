---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [test, bug]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-25 11:50
updated_at: 2026-05-25 17:18
---

## Symptom

`tests/test_desync_state.py::test_changelog_warns_for_data_desync_and_ignores_bad_helper_output`
fails on a clean `main` checkout with:

```
.aitask-scripts/lib/task_utils.sh: line 16: <tmpdir>/project/.aitask-scripts/lib/yaml_utils.sh: No such file or directory
```

## Root cause

`tests/test_desync_state.py:44-51` defines `copy_changelog()`:

```python
def copy_changelog(project: Path) -> Path:
    ...
    for name in ["desync_state.py", "task_utils.sh", "terminal_compat.sh", "archive_utils.sh"]:
        shutil.copy2(LIB_SRC / name, lib_dir / name)
    return script_dir / "aitask_changelog.sh"
```

The list omits `yaml_utils.sh`. `task_utils.sh:16` sources
`yaml_utils.sh` unconditionally, so any test scaffold that invokes
`aitask_changelog.sh` after `copy_changelog()` runs crashes before the
script body executes.

## Fix

Add `yaml_utils.sh` to the file list in `copy_changelog()`:

```python
for name in ["desync_state.py", "task_utils.sh", "terminal_compat.sh",
             "archive_utils.sh", "yaml_utils.sh"]:
```

If running the test still fails after adding `yaml_utils.sh`, audit
`task_utils.sh`'s full source-chain (and any other helpers it pulls
in) for additional missing libs.

## Origin

Surfaced during t823 (`fix_tui_switcher_desync_line_stale_across_sessions`)
while running `python3 -m unittest tests.test_desync_state`. Confirmed
via `git stash` round-trip that the failure pre-existed any t823
changes — listed in t823's plan under "Upstream defects identified".

## Acceptance criteria

1. `python3 -m unittest tests.test_desync_state` runs all 6 tests
   green from a clean `main` checkout.
2. No other changes outside `tests/test_desync_state.py`.
