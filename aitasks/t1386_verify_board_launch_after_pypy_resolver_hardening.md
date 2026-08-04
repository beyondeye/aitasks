---
priority: medium
effort: medium
depends: [1374]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1374]
created_at: 2026-08-03 16:09
updated_at: 2026-08-03 16:09
boardidx: 20480
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1374

## Verification Checklist

- [ ] `ait board` boots on the PyPy fast path in a real terminal — confirm the pane renders the board, not a traceback. (`resolve_pypy_python` now imports textual/yaml/linkify_it/tomli before returning the interpreter; aitask_board.sh:12 consumes it.)
- [ ] Confirm the resolved interpreter really is PyPy: `bash -c 'source .aitask-scripts/lib/python_resolve.sh; require_ait_python_fast'` prints the pypy_venv path and the board pane starts from it.
- [ ] Make PyPy dependency-incomplete (e.g. `~/.aitask/pypy_venv/bin/pip uninstall -y pyyaml`) and launch `ait board`: it must fall back to the CPython venv and boot normally — NOT crash on `import yaml`. Restore with `ait setup --with-pypy` afterwards.
- [ ] With the same dependency-incomplete PyPy, `AIT_USE_PYPY=1 ait board` must die with "PyPy not found. Run 'ait setup --with-pypy' to install it." rather than launching a doomed board.
- [ ] No stray output leaks into the interpreter path: the board pane must not report a path containing `(_common_types_metatype...` or any other import diagnostic. (Guards the probe's stdout redirection — `import yaml` under PyPy prints Cython lines.)
- [ ] Board startup feels unchanged: the fast-path probe now imports the runtime set (~150ms extra, once, memoized). Confirm no perceptible regression in time-to-first-render.
