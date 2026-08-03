---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [bash_scripts]
anchor: 1111
created_at: 2026-08-03 16:07
updated_at: 2026-08-03 16:07
boardidx: 13312
---

## Origin

Spawned from t1374 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:650,684 — install_pypy()/_install_pypy_linux() abort all of `ait setup` via `die` when the PyPy INTERPRETER cannot be installed (e.g. `uv python install` offline). Same defect class as t1374 fixed for pip: an opt-in tier taking down the core install. `ait setup --with-pypy` on an offline machine dies instead of warning and continuing without the fast path. Out of scope there (t1374 covers `pip install` sites only); the macOS branch `_install_pypy_macos` (~line 590-612) needs the same audit.`

## Diagnostic context

t1374 fixed the *pip* half of this defect class: every `pip install` in
`aitask_setup.sh` now runs through `pip_install_guarded()`, so a failing pip
warns and lets each caller's existing `verify_venv_*` check decide, instead of
aborting the whole run under `set -euo pipefail`.

The *interpreter-install* half was left untouched, and it is not a `set -e`
accident — it is an explicit `die`:

- `_install_pypy_linux()` — `"$uv_bin" python install "pypy@$AIT_PYPY_PREFERRED" || die "uv python install pypy@$AIT_PYPY_PREFERRED failed."` (line 650)
- `setup_pypy_venv()` — `die "PyPy install completed but interpreter still not found."` (line 684)

Reached whenever `setup_pypy_venv` needs to CREATE the venv: `--with-pypy`, or a
plain `ait setup` on a machine whose `$PYPY_VENV_DIR` exists but no longer holds
a valid PyPy interpreter (the `have_valid_venv` probe fails). On an offline or
proxied machine `uv python install` cannot reach the network and the whole
`ait setup` dies — the same "an optional tier bricks the core install" failure
t1374 removed for pip.

Note `_ensure_uv()` may itself download `uv`, so the failure can occur one level
earlier.

Cross-platform: `aidocs/framework/aitasks_extension_points.md` ("Cross-platform
audit for platform-specific bugs") requires auditing `_install_pypy_macos()` for
the same shape before finalizing scope — it installs via brew and has its own
`die`/warn mix.

## Suggested fix

Degrade instead of dying: when the interpreter cannot be installed, warn that
the PyPy fast path is unavailable, leave no partial `$PYPY_VENV_DIR` behind, and
`return 0` so setup continues on the CPython venv. (Since t1374,
`resolve_pypy_python()` rejects a dependency-incomplete PyPy, so a leftover
directory is inert — but it is still misleading.) Keep `die` only where the user
explicitly asked for PyPy AND continuing would be silently wrong; decide that
explicitly rather than by inheritance.

Verify with the pattern established in `tests/test_setup_pip_install_guards.sh`:
drive the real function in a child shell with a stubbed installer that exits 1,
plus a negative control that mechanically restores the bare `die`.
