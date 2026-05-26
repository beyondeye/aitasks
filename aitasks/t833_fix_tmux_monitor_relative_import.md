---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [ait_monitor, testing]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-25 23:09
updated_at: 2026-05-26 12:56
boardidx: 130
---

## Context

Surfaced during t826_2 verification. `tests/test_git_tui_config.py`
has 3 errors when run in isolation, all rooted in the same upstream
issue:

```
File "/home/ddt/Work/aitasks/.aitask-scripts/monitor/tmux_monitor.py", line 42, in <module>
    from .prompt_patterns import PromptPattern, all_patterns
ImportError: attempted relative import with no known parent package
```

The test loads `tmux_monitor` by inserting `.aitask-scripts/monitor/`
onto `sys.path` and importing the module by bare name, which means
the relative `from .prompt_patterns import ...` has no parent package
to resolve against.

This is **not** caused by t826_2 — it reproduces on a clean `main`.
But it leaves the failing tests as silent red flags in any
`run_all_python_tests.sh` run.

## Fix options

1. **Drop the relative import** in `.aitask-scripts/monitor/tmux_monitor.py:42`:
   change `from .prompt_patterns import PromptPattern, all_patterns` to
   `from prompt_patterns import PromptPattern, all_patterns`. Matches
   how the test (and every other consumer that uses `sys.path` insertion)
   loads the module. Lowest-friction fix.

2. **Make the test load the module as a package** — add an
   `__init__.py` to `.aitask-scripts/monitor/` and import as
   `monitor.tmux_monitor`. Heavier change, may affect other
   `sys.path`-anchored consumers.

Option 1 is the surgical fix and matches how the rest of the
`.aitask-scripts/lib/` modules already structure their imports
(absolute imports with `sys.path` insertion).

## Verification

- Before: `python3 tests/test_git_tui_config.py` reports 3 ERRORs.
- After: 0 ERRORs, all 17 assertions pass.
- Run `bash tests/run_all_python_tests.sh` to confirm no other
  consumer was relying on the relative import.

## Out of Scope

- Restructuring `.aitask-scripts/monitor/` into a proper Python
  package (heavier refactor — defer if Option 1 is sufficient).

## References

- Surfaced in t826_2's Final Implementation Notes
  (`aiplans/p826/p826_2_tui_switcher_show_inactive_projects.md`,
  "Upstream defects identified" section).
- Affected file: `.aitask-scripts/monitor/tmux_monitor.py:42`
- Failing tests: `tests/test_git_tui_config.py` (3 errors)
