---
priority: medium
effort: low
depends: []
issue_type: test
status: Ready
labels: [reporting, testing]
gates: [risk_evaluated]
anchor: 1162
created_at: 2026-07-28 18:05
updated_at: 2026-07-28 18:05
boardidx: 71680
---

## Origin

Risk-mitigation ("after") follow-up for t1235, created at Step 8d after implementation landed.

## Risk addressed

Code-health — blast radius across the stats TUI import sites. From t1235's plan:

> Wide-but-shallow blast radius: one file move plus 9 production import sites
> (the stats CLI, `stats_app.py`, and all 7 files under `stats/panes/`), 4 test
> files and 3 doc files. Each edit is mechanical, but a missed pane is a
> `ModuleNotFoundError` that stops the TUI from starting — `stats/panes/__init__.py`
> imports every pane eagerly · severity: medium

During t1235's plan review, `stats/panes/velocity.py` was in fact missing from the
first draft's importer list. It was caught by human review, not by a test.

## Goal

Make a missed or broken import site in the stats TUI fail a test rather than only
fail at TUI runtime.

Today the only automated coverage of the pane import chain is
`tests/test_stats_include_registered.py`, which path-loads `stats_app.py` and
therefore drags in `stats.panes`. That works, but it is incidental coverage: its
subject is pane registration, its failure message points at `stats_app`, and it
does not enumerate the pane modules, so it cannot say *which* pane broke.

Add a dedicated import-level regression test that:

- Path-loads (or imports) **every** module under `.aitask-scripts/stats/panes/`
  and `stats_app.py`, enumerating the directory rather than hardcoding a list, so
  a newly added pane is covered automatically.
- Runs each import in an **isolated interpreter** with `PYTHONPATH` unset and only
  `.aitask-scripts` on `sys.path` — this is what proves `stats/__init__.py`'s own
  `lib/` bootstrap is doing the work, rather than a path some other module
  happened to insert first.
- Names the offending module in the failure message.

Note `tests/lib/import_isolated.py` and `tests/test_python_bootstrap_isolation.sh`
landed from t1236 and already provide an isolated-import harness — reuse it rather
than writing a parallel one.

## Negative control

The test must be shown to discriminate: temporarily break one pane's import (e.g.
revert `stats/panes/velocity.py` to `from stats.stats_data import ...`) and confirm
the new test fails **and names velocity.py**, then restore the file by hand (not
`git checkout --`).

## Key files

- `.aitask-scripts/stats/panes/` — 6 pane modules plus `base.py`, all imported
  eagerly by `stats/panes/__init__.py`
- `.aitask-scripts/stats/__init__.py` — the `lib/` bootstrap under test
- `tests/lib/import_isolated.py` — existing isolated-import harness (t1236)
- `tests/test_stats_include_registered.py` — the incidental coverage this replaces
  or complements

## Verification

- The new test passes on a clean tree
- The negative control above fails and names the broken pane
- `bash tests/run_all_python_tests.sh`
