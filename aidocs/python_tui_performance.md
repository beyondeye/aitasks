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
| TUI launchers | All use `require_ait_python` | `aitask_board.sh`, `aitask_settings.sh`, `aitask_brainstorm_tui.sh`, `aitask_syncer.sh` use new `require_ait_python_fast` (PyPy if available, else CPython). `aitask_codebrowser.sh`, `aitask_monitor.sh`, `aitask_minimonitor.sh`, `aitask_stats_tui.sh` **stay on CPython** (codebrowser empirically loses on PyPy per t718_6; monitor/minimonitor's bottleneck is `fork+exec(tmux)` and PyPy still loses on the post-t719_2 control-mode path per t718_5; stats-tui depends on `plotext`, which is installed only in the CPython venv). Short-lived CLI scripts (`aitask_pick.sh`, `aitask_create.sh`, `aitask_stats.sh`, …) **stay on CPython**. |
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

## t718_5 Empirical Verification — monitor/minimonitor under PyPy (2026-05-17)

The parent t718 plan excluded `aitask_monitor.sh` / `aitask_minimonitor.sh` from the PyPy fast path on the *theoretical* grounds that their hot path is `fork+exec(tmux)`, which PyPy cannot accelerate. t718_5 measured this directly. **Verdict: REVERT — but the original rationale is partially obsolete and is replaced below.**

### Important context update — t719_2 has already landed

The "fork+exec dominates" framing in the *Per-TUI Bottleneck Classification* table above was correct in 2025, but **`t719_2` (hot-path integration of tmux control mode) is already archived**. Today `TmuxMonitor._tmux_async` routes through a persistent `TmuxControlBackend` running on a dedicated bg-thread event loop (see `.aitask-scripts/monitor/tmux_control.py`); fork+exec only happens on transport failure or before the backend has connected. Both `monitor_app.py:642` and `minimonitor_app.py:241` start the control client at app boot.

The benchmark below therefore measures **two paths**:

- **Legacy fallback path** (`start_control_client()` never called) — represents what monitor would do without t719_2. Equivalent to the pre-t719 codebase.
- **Production control-mode path** (`start_control_client()` called and `is_alive`) — represents what monitor actually does today.

PyPy loses on **both** paths, for **different** reasons. The negative result is robust.

### Workload

- Machine: Linux (Arch / Hyprland), this repo.
- CPython: 3.14.4 (`~/.aitask/venv/bin/python`).
- PyPy: 7.3.21 / Python 3.11.15 (`~/.aitask/pypy_venv/bin/python`).
- Isolated benchmark sessions `pypy_bench_<pid>_{3,8,15}` with 3, 8, and 15 idle bash panes.
- Direct microbenchmark of `TmuxMonitor.capture_all_async()` — the exact function the monitor calls every 3 s.
- `multi_session=False` so discovery stayed scoped to the bench session.
- Two sweeps: legacy fallback path (N=100 iter, 20 warmup, 3 reps) and control-mode path (N=500 iter, 50 warmup for CPython / **500 warmup for PyPy** to fully prime its JIT, 3 reps).
- Part 3 (strace `fork,execve` sanity check) was skipped because `strace` is not installed on this machine.

### Legacy fork+exec fallback path (no `start_control_client()`)

| Panes | CPython median | PyPy median | PyPy / CPython |
|-------|----------------|-------------|----------------|
| 3     | 2.75 ms        | 8.90 ms     | **3.2× slower** |
| 8     | 3.47 ms        | 19.17 ms    | **5.5× slower** |
| 15    | 4.61 ms        | 34.14 ms    | **7.4× slower** |

Why PyPy loses here: each tick fires `asyncio.gather(*[capture_pane_async(p) for p in panes])`, one `asyncio.create_subprocess_exec("tmux", "capture-pane", …)` per pane. PyPy's asyncio + subprocess wrapping is heavier per call than CPython's optimized C-level subprocess module, and the slowdown scales linearly with pane count (more fork+exec calls per gather). JIT cannot accelerate OS-level work.

### Production control-mode path (`start_control_client()` called)

| Panes | CPython median | PyPy median | PyPy / CPython |
|-------|----------------|-------------|----------------|
| 3     | 0.37 ms        | 0.65 ms     | **76% slower**  |
| 8     | 0.62 ms        | 1.18 ms     | **90% slower**  |
| 15    | 1.03 ms        | 1.01 ms     | ~equal (within noise) |

Why PyPy still loses here, even though the workload is now mostly Python/asyncio: the per-tick work is small (sub-millisecond on CPython) and dominated by `asyncio.run_coroutine_threadsafe` round-trips between the calling thread and the control backend's bg-loop, plus very little hot Python code per call. PyPy's per-coroutine and cross-thread scheduling overhead is heavier than CPython's, and there is too little user-code work per tick for JIT to amortize. The slowdown gap *narrows* with pane count (76% → 90% → ~equal): PyPy's fixed per-tick overhead is closer to constant while CPython grows linearly with pane count, so the two converge near 15 panes and would likely cross over only at very large pane counts (well above realistic usage).

### Cold-start `import monitor_app` (5 reps each, median)

| Interpreter | Median ms |
|-------------|-----------|
| CPython     | 159 ms    |
| PyPy        | 325 ms    |

PyPy regresses cold-start by ~166 ms (~2× slower). Standard PyPy warmup penalty (~150-300 ms per the Distribution section above), confirmed on this codebase.

### Decision: REVERT (do not wire to fast path)

`aitask_monitor.sh` and `aitask_minimonitor.sh` remain on `require_ait_python` (CPython). The pre-decision-rule threshold was "KEEP if PyPy improves the 8-pane workload by ≥10%"; the actual control-mode result is 90% *slower* at 8 panes. Cold-start is worse too. PyPy ties at 15 panes but never wins, and would only have a chance to pull ahead at workload sizes well above typical usage.

### What would change this verdict

- **Not** t719_2 alone — that has already landed and PyPy still loses (see above).
- Possibly t719_3 (adaptive polling) or t719_4 (pipe-pane push), which further change the hot path. If t719_4 lands and shifts the per-tick work toward Python-side parsing of pushed frames (less asyncio thread-hopping), the picture could change. **Re-measure t718_5 after t719_4 archives.**
- A very large pane count (≫ 15) where CPython's per-pane cost grows faster than PyPy's per-tick overhead. Not realistic for the documented use cases.

Until one of those conditions is met, do not re-run this benchmark or re-attempt the swap.

## t718_6 Empirical Verification — board / codebrowser under PyPy (2026-05-17)

Sibling t718_2 wired the two largest Textual surfaces — `aitask_board.sh`
(KanbanApp, 5176 LOC) and `aitask_codebrowser.sh` (CodeBrowserApp, 1504 LOC
+ helpers) — to the PyPy fast path on the *theoretical* grounds quoted in
the *Compile/JIT options* row above. t718_6 measured this directly.
**Verdict: MIXED — board KEEPs PyPy; codebrowser REVERTs to CPython.**

### Workload

- Machine: Linux (Arch / Hyprland), this repo.
- CPython: 3.14.4 (`~/.aitask/venv/bin/python`).
- PyPy: 7.3.21 / Python 3.11.15 (`~/.aitask/pypy_venv/bin/python`).
- Textual `App.run_test(size=(160, 48))` Pilot driver — same pattern as
  `tests/test_board_view_filter.py:76`.
- **Board workload:** `pause → 20× down → a → i → g → a → r → pause`
  (exercises card navigation, view-mode cycling, and a full refresh that
  re-reads task files from disk). Avoids modal-pushing keys (`enter`,
  `n`, `O`, etc.) which would deadlock Pilot.
- **Codebrowser workload:** open with `--focus
  .aitask-scripts/brainstorm/brainstorm_app.py` (~5200 LOC,
  syntax-highlighted), then `pause → 10× pagedown → 10× pageup → end →
  home → pause`. The `--focus` arg short-circuits the file-tree pane
  via `_parse_focus_value()` at `codebrowser_app.py:454`.
- 5 warmup iterations + 8 measurement iterations per (TUI, interpreter)
  pair within one process. PyPy needed extra warmup to JIT-stabilize
  (per the t718_5 methodology lesson).
- Each rep measures startup + workload + teardown via
  `time.perf_counter()` around the `async with app.run_test(...) as
  pilot:` block.

### Board (KanbanApp)

| Metric | CPython median | PyPy median | Delta |
|---|---:|---:|---:|
| Pilot workload (steady state) | 10108 ms | 8731 ms | **13.6% faster on PyPy** |
| Cold-start (`import aitask_board`, 5 reps) | 202 ms | 355 ms | 153 ms regression |

PyPy is slower for the first 1-2 workload-equivalents inside the
process (warmup[1]=15.6 s vs CPython warmup[1]=10.0 s), then converges
to a steady-state ~14% per-workload win. For a typical 30-60 s board
session, the per-launch ~150 ms cold-start regression is dwarfed by
the steady-state savings (~1.3 s per workload-equivalent × ~3-6
workload-equivalents per session = several seconds saved). Short
"glance" sessions (< 5 keystrokes, close immediately) marginally
favor CPython, but those are not the modal usage pattern.

**Verdict: KEEP.** `aitask_board.sh` continues to use
`require_ait_python_fast`.

### Codebrowser (CodeBrowserApp)

| Metric | CPython median | PyPy median | Delta |
|---|---:|---:|---:|
| Pilot workload (steady state) | 4067 ms | 4740 ms | **16.6% slower on PyPy** |
| Cold-start (`import codebrowser_app`, 5 reps) | 173 ms | 341 ms | 168 ms regression |

PyPy converges flat around 4700-4800 ms after 2-3 warmup iterations
and never crosses CPython's 4067 ms. Cold-start is ~2× slower. PyPy is
net-negative across the entire workload size range tested. The
workload exercises the syntax-highlighter (`code_viewer.py:40-48`) and
viewport scroll on a 5200-LOC Python file — the kind of Rich-render +
viewport-diff work the *Compile/JIT options* row above predicted PyPy
would win on. Empirically it doesn't here, plausibly because Rich's
rendering pipeline is C-accelerated for color/markup spans and the
remaining per-keystroke Python work is too small for JIT to amortize.

**Verdict: REVERT.** `aitask_codebrowser.sh` line 12 reverted from
`require_ait_python_fast` to `require_ait_python`. Codebrowser stays
on CPython regardless of `AIT_USE_PYPY`.

### Why the two diverge

- Board's workload includes a full `refresh_board()` pass per
  iteration (read all task files, parse frontmatter, rebuild the
  Kanban widget tree). This is heavy CPython interpretation —
  thousands of small Python operations per workload run, exactly the
  shape PyPy's JIT specializes well on.
- Codebrowser's workload is dominated by scroll + rendering of an
  already-parsed AST. The per-keystroke Python work is small and
  fragmented across many short call sites, which the JIT struggles to
  amortize while paying its fixed per-frame overhead.

This refines the rule for future long-running TUIs: PyPy is a likely
win when the hot path is heavy interpreted Python (many operations,
large data transforms, frontmatter parsing); it tends to lose when the
hot path is small per-frame Textual/Rich render work dispatched from
C-accelerated layers.

### What would change the codebrowser verdict

- A workload that re-parses or transforms large amounts of Python at
  steady state (e.g., live syntax-tree edits, large multi-file
  re-indexing).
- A future PyPy release closing the C-extension call-site overhead
  gap.
- Re-measurement is appropriate if either condition is met; otherwise
  do not re-attempt the swap.

## Related Tasks

- **t257** (`aitasks/t257_performance_when_chaning_selection.md`) — codebrowser scroll/selection lag. Likely a Textual render-diff issue, not interpreter speed. Adjacent to PyPy adoption but not duplicated by it.
- **t718_5** (above) — empirical verification of monitor/minimonitor under PyPy. REVERT verdict; CLAUDE.md note added.
- **t718_6** (this section) — empirical verification of board / codebrowser under PyPy. MIXED verdict: board KEEPs, codebrowser REVERTs.
- **t719_2** (archived) — hot-path integration of `tmux -C` control mode; reshaped the hot path that t718_5 benchmarks.
- **t719_4** (pending) — pipe-pane push. If/when archived, re-run the t718_5 benchmark before drawing fresh conclusions about PyPy on monitor/minimonitor.
