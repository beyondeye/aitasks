---
title: "PyPy Runtime — Internals"
linkTitle: "PyPy Runtime"
weight: 30
description: "PyPy resolver semantics, per-TUI bottleneck analysis, diagnostics, and overrides"
---

aitasks ships with an opt-in **PyPy 3.11** sibling venv for `ait board`. The user-facing install flow lives in [Installation → PyPy Runtime]({{< relref "/docs/installation/pypy" >}}); this page documents the resolver semantics, the per-TUI bottleneck reasoning, runtime overrides, and diagnostic commands.

## Resolver semantics

Once the PyPy venv exists at `~/.aitask/pypy_venv/`, the launcher resolver in `.aitask-scripts/lib/python_resolve.sh` auto-routes the fast-path TUI through PyPy:

| TUI            | Command           |
|----------------|-------------------|
| Board          | `ait board`       |

CPython remains the default for every other launcher. PyPy is **sibling**, not replacement.

## TUIs that stay on CPython

- **`ait codebrowser`** — empirical benchmarks (`t718_6`) showed PyPy ~17% slower steady-state with a ~168 ms cold-start regression. Routed back to CPython.
- **`ait settings` / `ait brainstorm` / `ait syncer`** — never empirically measured under PyPy. Originally routed by analogy with board, then de-routed by `t785` / `t831`. To A/B-test one of these TUIs under PyPy, point `AIT_PYTHON` at the PyPy venv binary for that invocation (`AIT_PYTHON=~/.aitask/pypy_venv/bin/python ait settings`).
- **`ait monitor` / `ait minimonitor`** — bottleneck is `fork+exec(tmux)` per refresh tick, an OS-level cost PyPy cannot accelerate. Measured 76-90% slower at typical pane counts (`t718_5`).
- **`ait stats-tui`** — chart panes depend on the `plotext` package, which is installed only in the CPython venv.
- **`ait stats`** (one-shot CLI) and other short-lived CLIs — the ~150-300 ms PyPy warmup would dominate total runtime.

## Override per invocation — `AIT_USE_PYPY`

The `AIT_USE_PYPY` env var forces a specific interpreter for a single command, but it is only honored on launchers that resolve through `require_ait_python_fast` — currently `ait board` is the only such launcher:

| `AIT_USE_PYPY` | PyPy installed? | Result for `ait board` |
|----------------|-----------------|------------------------|
| `1`            | Yes             | PyPy (forced) |
| `1`            | No              | error: install with `ait setup --with-pypy` |
| `0`            | (any)           | CPython (override) |
| unset          | Yes             | PyPy (default once installed) |
| unset          | No              | CPython |

Examples:

```bash
AIT_USE_PYPY=0 ait board   # one-off CPython run with PyPy installed
AIT_USE_PYPY=1 ait board   # error if PyPy not installed
```

Other launchers (`ait settings`, `ait codebrowser`, etc.) ignore this variable. Use `AIT_PYTHON=~/.aitask/pypy_venv/bin/python ait <command>` if you want a one-off PyPy run on a launcher that defaults to CPython.

## Diagnostics

Confirm the PyPy venv is healthy:

```bash
~/.aitask/pypy_venv/bin/python -c "import sys; print(sys.implementation.name, sys.implementation.version)"
# Expected output: pypy sys.version_info(major=3, minor=11, ...)
```

Confirm `textual` is importable:

```bash
~/.aitask/pypy_venv/bin/python -c "import textual; print(textual.__version__)"
```

## Background

For the per-TUI bottleneck analysis and PyPy compatibility audit that motivated this design, see [`aidocs/framework/python_tui_performance.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/framework/python_tui_performance.md) in the repo.
