# Python TUI Performance Options

Investigation of options to speed up the aitasks Python TUIs (board, codebrowser, monitor, minimonitor) without rewriting source code, while keeping cross-platform support.

## Current Stack

- **Interpreter:** CPython 3.14.3 in `~/.aitask/venv/`. JIT *available* (`sys._jit`) but **disabled** (this build was not compiled with `--enable-experimental-jit`). Free-threading off (`Py_GIL_DISABLED: 0`).
- **Frameworks:** `textual==8.1.1` + `rich==14.3.2` — both pure-Python, no native extensions.
- **Other deps:** `pyyaml==6.0.3`, `linkify-it-py==2.1.0`, `tomli>=2.4.0,<3`, optional `plotext==5.3.2`.
- **Codebase:** ~87 `.py` files, **~40K LOC** total.
  - Board (`aitask_board.py`): **5200 LOC**.
  - Codebrowser app + helpers: ~3500 LOC.
  - Monitor (`monitor_app.py`): 1778 LOC.
  - Minimonitor (`minimonitor_app.py`): 733 LOC.
  - Shared `tmux_monitor.py`: 740 LOC.
- **Cold-start cost:** dominated by `import textual` (~115 ms); board parse adds ~26 ms.
- **Distribution:** `ait setup` installs CPython user-scoped via `uv` on Linux, brew on macOS. Venv at `~/.aitask/venv`. Python is resolved through `lib/python_resolve.sh`.

## Per-TUI Bottleneck Classification

The optimization target is different for each TUI. **One approach does not fit all.**

| TUI | Primary bottleneck | Class | What helps |
|-----|--------------------|-------|------------|
| **Board** | Widget tree builds, frontmatter parsing, your code + Textual rendering | CPU-bound (Python + Textual) | PyPy (helps Textual too); mypyc/Nuitka help your code only; cache parsed frontmatter |
| **Codebrowser** | Render diff for syntax highlighting, scroll/selection lag inside Textual (see t257) | CPU-bound (mostly Textual) | PyPy mostly; source-level fix to selection-render path |
| **Monitor** | **N × `fork+exec(tmux)` per 3s tick** (subprocess.run / asyncio.create_subprocess_exec for each agent pane) | **I/O-bound** (OS fork/exec) | **`tmux -C` control mode** (single persistent connection, zero forks). Or `pipe-pane`. Adaptive polling. **Compile/JIT options give ~0% here.** |
| **Minimonitor** | Same as monitor | Same | Same |

### Monitor refresh loop (the hot path)

`tmux_monitor.py::capture_all_async()` spawns one `tmux capture-pane` subprocess per agent pane every 3 seconds via `asyncio.create_subprocess_exec`. Per-call cost is ~1-10 ms of `fork()` + `exec(tmux)` work — **OS-level, not Python-level**. With 5-10 agents that's 6-15 fork+exec cycles every refresh. PyPy, Nuitka, mypyc, JIT — none of them speed up `fork+exec`.

## Compile / JIT Options Compared

For board + codebrowser specifically, where Python execution is actually the bottleneck.

### Constraints recap

- Cross-platform.
- Keep source code unchanged.
- Distribution model: source vs. binary artifact is open.

### Options that match constraints

| Approach | What it does | Distribution | Realistic win on board/codebrowser |
|----------|--------------|--------------|-------------------------------------|
| **mypyc** | Compiles type-annotated `.py` → C extension `.so` per platform. Source remains importable as fallback. Used by mypy/black/uv. | Ship sdist + per-platform wheels (cibuildwheel). pip auto-selects; falls back to source. | 1.5-4× on type-annotated hot modules. **Zero win on Textual itself** (third-party). |
| **Cython "pure-Python mode"** | Type hints + `cythonize` → `.so` per platform. | Same as mypyc. | Similar; more knobs but more invasive. |
| **Nuitka `--module`** | Compiles each `.py` → `.so`. | Same wheels model. | 1.3-2× typical; bigger artifacts. |
| **Nuitka `--standalone`** | Single per-platform binary bundling frozen interpreter + all deps. | Ship N binaries (~50-100 MB each). Loses "ship source" property. | Same as `--module` (AOT compile). User installs no Python at all. |
| **PyPy** | JIT-based alternative interpreter. Speeds up your code AND Textual AND Rich. | Ship same source; install pypy3 instead of cpython. | Often **2-5× on Textual workloads**. PyPy 3.11 is current; no 3.12+ syntax can be used in code. |
| **Enable CPython 3.14 JIT** | Use a CPython built with `--enable-experimental-jit`. | Different interpreter binary; no artifact change. | Currently ~10-20% on PEP 744 benchmarks; experimental. |
| **Free-threaded `python3.14t`** | Drops GIL. | Different interpreter binary. | Near-zero for asyncio-driven TUIs (not the bottleneck). |

### Honest ranking for board + codebrowser

1. **PyPy** — biggest single lever. Speeds up Textual + Rich + your code. Simplest to try.
2. **Source-level fixes (profiling-driven)** — could match or beat PyPy if the bottleneck is algorithmic (e.g., t257 scroll lag is likely a render-diff issue compilation can't fix).
3. **Nuitka `--standalone` with PGO** — meaningful for your code, zero help for Textual.
4. **mypyc on hot modules** — same caveat; only your code.
5. **CPython 3.14 + JIT enabled** — experimental, ~10-20%.
6. **Free-threaded build** — near-zero for asyncio-driven TUIs.

### What doesn't help, and why

- **Compiling your code won't fix t257-style felt slowness.** Codebrowser scroll/selection lag is almost certainly inside Textual's render diff path. Compile wins don't propagate into Textual unless you swap the whole interpreter (PyPy).
- **Compile/JIT options give ~0% on monitor/minimonitor.** Their bottleneck is `fork()` + `exec(tmux)`, an OS cost.

## PyPy Compatibility Audit

**Codebase passes — no porting needed.**

- **No Python 3.12+ syntax in use:**
  - Zero PEP 695 (`type X = ...`, generic `def foo[T]`).
  - Zero `typing.override`.
  - Zero `tomllib` imports (uses `tomli` package).
  - Extensive `from __future__ import annotations` (the right pattern for cross-version compat).
- **All deps support 3.9+:**
  - `textual>=3.9,<4`
  - `rich>=3.8`
  - `pyyaml>=3.8`
  - `linkify-it-py>=3.10`
  - `tomli>=3.8`
  - `plotext>=3.5`

PyPy 3.11 satisfies all of them. No CPython-internal extensions in the dep set.

## PyPy Distribution Integration Sketch

The existing `ait setup` architecture already has the right shape — PyPy slots in as a parallel interpreter family using the same patterns.

### Existing layers in `aitask_setup.sh` + `lib/python_resolve.sh`

1. **Interpreter resolution** (`lib/python_resolve.sh`): cached lookup with `AIT_PYTHON` override → `~/.aitask/venv/bin/python` → `~/.aitask/bin/python3` → system `python3`.
2. **Private Python install** (`aitask_setup.sh::install_modern_python`): macOS via brew (`brew install python@<ver>`), Linux via uv (`uv python install $AIT_VENV_PYTHON_PREFERRED`).
3. **Venv creation** (`aitask_setup.sh::setup_python_venv`): `python -m venv $VENV_DIR`, then `pip install` deps.

### Three integration options

#### Option A: Dual-venv, opt-in (safe default)

| Layer | Current | Add |
|-------|---------|-----|
| Path constants | `VENV_DIR=~/.aitask/venv` | `PYPY_VENV_DIR=~/.aitask/pypy_venv`, `AIT_PYPY_PREFERRED=3.11` |
| Install | `install_modern_python` | `install_pypy`: `uv python install pypy@3.11` (uv supports PyPy as first-class). macOS fallback: `brew install pypy3`. |
| Venv setup | `setup_python_venv` | `setup_pypy_venv`: same `pip install` line into `~/.aitask/pypy_venv` |
| Resolver | `require_ait_python` | Add `require_ait_pypy` (returns PyPy if installed, else empty). Cached in `_AIT_RESOLVED_PYPY`. |
| TUI launchers | All use `require_ait_python` | `aitask_board.sh`, `aitask_codebrowser.sh`, `aitask_settings.sh`, `aitask_stats.sh` use new `require_ait_python_fast` (PyPy if available, else CPython). `aitask_monitor.sh`, `aitask_minimonitor.sh` **stay on CPython**. Short-lived CLI scripts (`aitask_pick.sh`, `aitask_create.sh`, …) **stay on CPython**. |
| Setup UX | Plotext prompt | Add `--with-pypy` flag and prompt: `Install PyPy for faster TUIs (board, codebrowser)? [y/N]` |

Touchpoints: ~5 files, all additive. Removable in one commit. Existing CPython users see zero change unless they opt in.

#### Option B: Replace CPython entirely with PyPy

- ✗ CLI cold-start regression: every short-lived `python` invocation in `ait` scripts pays PyPy warmup (~150-300 ms).
- ✗ Loses 3.14 features and forward-compat (PyPy is currently 3.11).
- ✗ Edge-case risk: anything depending on CPython internals later silently breaks.
- ✓ Simpler — no dual logic.

**Not recommended** unless CPython startup cost on cold CLI invocations is measured to be negligible.

#### Option C: Per-invocation runtime toggle via env var

Most flexible. `AIT_USE_PYPY=1 ait board` routes just that invocation through PyPy. Cheap to implement on top of Option A: `require_ait_python_fast` honors the env var. Useful for users who want to A/B test without committing.

### Distribution implications

You don't ship PyPy yourself — `ait setup` installs it via `uv` (already a dependency on Linux) or brew. Disk cost: ~50-80 MB PyPy + ~50 MB second venv = ~100-150 MB additional in `~/.aitask/`. Acceptable for an opt-in feature.

## Recommendations

1. **Profile first.** Spend an hour with `py-spy record` on a slow board interaction and a slow codebrowser scroll. The result determines which option to pursue:
   - If >50% of samples are inside `textual/` → PyPy.
   - If they're inside aitasks code → mypyc/Nuitka.
   - If they're in terminal I/O (`os.write`, `select`) → no compile option helps; need source-level fixes.

2. **Treat board/codebrowser separately from monitor/minimonitor.** The fixes are different classes:
   - Board/codebrowser → PyPy spike (Option C is the cheapest entry point).
   - Monitor/minimonitor → tmux control mode (`tmux -C`) refactor, replacing per-tick subprocess spawns with one persistent connection. 5-20× refresh speedup potential and reduces tmux server load.

3. **Don't adopt Python 3.12+ syntax in new code** until PyPy 3.12 ships, if PyPy integration goes ahead.

## Related Tasks

- **t257** (`aitasks/t257_performance_when_chaning_selection.md`) — codebrowser scroll/selection lag. Likely a Textual render-diff issue, not interpreter speed. Adjacent to PyPy adoption but not duplicated by it.
