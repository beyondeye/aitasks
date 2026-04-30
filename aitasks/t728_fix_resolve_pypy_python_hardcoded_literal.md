---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [ait_setup, python, installation]
created_at: 2026-04-30 15:58
updated_at: 2026-04-30 15:58
---

## Origin

Spawned from t727 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/python_resolve.sh:112 — resolve_pypy_python() hardcodes 'pypy3.11 pypy3' candidate list, ignoring AIT_PYPY_PREFERRED. Same single-source-of-truth violation as the find_pypy() literal that was fixed in aitask_setup.sh during t727. Bumping AIT_PYPY_PREFERRED to 3.12 will silently match a stale 3.11 binary on PATH first.`

## Diagnostic context

While auditing the macOS PyPy install path during t727, we replaced the hardcoded `pypy3.11 pypy3` literal in `aitask_setup.sh`'s `find_pypy()` candidate list with `"pypy$AIT_PYPY_PREFERRED" pypy3` so a future bump of `AIT_PYPY_PREFERRED` (e.g. to 3.12) propagates to PATH lookups. A grep for `pypy3.11` across the framework surfaced a second copy of the same bug in `.aitask-scripts/lib/python_resolve.sh:112`, inside `resolve_pypy_python()`. Both functions perform the same role (probe candidate PyPy interpreters and return the first usable one); both should honor the same constant. `AIT_PYPY_PREFERRED` is defined as the single source of truth at `lib/python_resolve.sh:37` — yet the same file's resolve function hardcodes `pypy3.11`.

## Suggested fix

In `lib/python_resolve.sh`, change:

```bash
    for cand in pypy3.11 pypy3; do
```

to:

```bash
    for cand in "pypy$AIT_PYPY_PREFERRED" pypy3; do
```

The exact same one-line shape that t727 applied to `aitask_setup.sh:456`.

## Verification

- `bash tests/test_python_resolve_pypy.sh` — note this test is pre-existing-broken (see t727 Final Implementation Notes); fixing it is not in scope here. Confirm the modified line is byte-equivalent to the t727 fix and doesn't introduce new shellcheck warnings.
- Manually: `AIT_PYPY_PREFERRED=3.12 bash -c "source .aitask-scripts/lib/python_resolve.sh; resolve_pypy_python"` should attempt `pypy3.12` lookup before `pypy3` (after this fix), instead of `pypy3.11` then `pypy3` (before).

## Out of scope

- Deduping `find_pypy()` (in `aitask_setup.sh`) and `resolve_pypy_python()` (in `lib/python_resolve.sh`): they share intent but live in different modules with different consumers. A future refactor could consolidate them, but this task is just the literal substitution.
- Fixing `tests/test_python_resolve_pypy.sh` itself: pre-existing-broken (PyPy stub not detected by `resolve_pypy_python` even when present at `~/.aitask/pypy_venv/bin/python`). Track separately.
