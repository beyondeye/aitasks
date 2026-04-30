---
priority: medium
effort: high
depends: []
issue_type: performance
status: Ready
labels: [performance, setup, tui]
children_to_implement: [t718_1, t718_2, t718_3, t718_4]
created_at: 2026-04-30 08:34
updated_at: 2026-04-30 10:36
boardidx: 20
---

## Goal

Add **opt-in PyPy support** for the long-running Textual TUIs (board, codebrowser, settings, stats) using a per-invocation env-var toggle (Option C in `aidocs/python_tui_performance.md`). Keep CPython as the default for everything else.

## Background

`aidocs/python_tui_performance.md` documents the analysis. Key facts:

- Board (5200 LOC) and codebrowser (~3500 LOC) are CPU-bound, with most time spent inside Textual + Rich (pure Python) and the aitasks widget code. PyPy's tracing JIT speeds up all three; AOT compilers (mypyc/Cython/Nuitka) only help aitasks code, not Textual.
- Codebase is **PyPy 3.11 compatible today**: no PEP 695 syntax, no `tomllib`, no `typing.override`. All deps support Python 3.9+.
- Monitor/minimonitor are NOT covered by this task — their bottleneck is `fork+exec(tmux)`, not Python execution. See the sibling task on tmux control-mode refactor.
- Short-lived CLI scripts (`aitask_pick.sh`, `aitask_create.sh`, etc.) stay on CPython to avoid the ~150-300 ms PyPy warmup penalty.

## Approach

Option C from the aidoc — a runtime toggle with the dual-venv infrastructure of Option A underneath. PyPy is a sibling interpreter, additive to the existing CPython venv.

### Touchpoints

1. **`.aitask-scripts/aitask_setup.sh`**
   - Add `setup_pypy_venv()` paralleling `setup_python_venv()`. Target dir: `$HOME/.aitask/pypy_venv`.
   - Add `install_pypy()` paralleling `install_modern_python()`:
     - Linux: `uv python install pypy@3.11` (uv supports PyPy as a first-class interpreter family).
     - macOS: `brew install pypy3` (fallback) or uv if available.
   - Add `--with-pypy` setup flag and an interactive prompt: `Install PyPy for faster TUIs (board, codebrowser)? [y/N]`.
   - Constants: `AIT_PYPY_PREFERRED=3.11`, `PYPY_VENV_DIR=$HOME/.aitask/pypy_venv`. Treat them as the single source of truth (no literal duplication across helpers — see `feedback_single_source_of_truth_for_versions.md`).

2. **`.aitask-scripts/lib/python_resolve.sh`**
   - Add `resolve_pypy_python()` and `require_ait_pypy()`, mirroring the CPython lookups. Cache in `_AIT_RESOLVED_PYPY`.
   - Add `require_ait_python_fast()`: if `AIT_USE_PYPY=1` (or unset and PyPy installed and the calling script has opted in via a flag — see step 3), return PyPy if available; else fall back to `require_ait_python` (CPython). Keep current `require_ait_python` semantics unchanged.

3. **TUI launcher scripts** (only the long-running ones)
   - `.aitask-scripts/aitask_board.sh`, `aitask_codebrowser.sh`, `aitask_settings.sh`, `aitask_stats.sh`: switch from `require_ait_python` to `require_ait_python_fast`.
   - `.aitask-scripts/aitask_monitor.sh`, `aitask_minimonitor.sh`: **stay on CPython** (PyPy gives ~0% there).
   - All other scripts: stay on CPython.

4. **Documentation**
   - Update `CLAUDE.md` shell-conventions section if needed to document `require_ait_python_fast` vs `require_ait_python`.
   - Add a website doc or README section explaining `AIT_USE_PYPY=1` and `--with-pypy`.

5. **Setup / install integration tests**
   - Per CLAUDE.md "Test the full install flow for setup helpers": run `bash install.sh --dir /tmp/scratchXX` then `--with-pypy` and confirm the pypy venv is built and contains the deps. Don't stop at unit-level helper tests.

## Out of scope

- Replacing CPython entirely (Option B in the aidoc — explicitly rejected for now).
- Adopting any Python 3.12+ syntax in code that would run under PyPy. PyPy 3.11 is current; 3.12+ syntax would break the fast path.
- Any changes to monitor/minimonitor — handled by sibling task.
- Profiling / benchmarking infrastructure beyond a one-time spike to confirm wins. A profiling task can be split out if useful.

## Acceptance Criteria

- `ait setup --with-pypy` installs PyPy 3.11 into `$HOME/.aitask/pypy_venv` with all deps.
- `AIT_USE_PYPY=1 ait board` launches board on PyPy when available.
- `AIT_USE_PYPY=1 ait monitor` still uses CPython (excluded by design).
- Without `--with-pypy`, `ait setup` and existing flows are byte-for-byte unchanged for current users.
- Removing PyPy support is a clean, single-commit revert.

## Reference

`aidocs/python_tui_performance.md` — full background and analysis.
