---
title: "PyPy Runtime — Internals"
linkTitle: "PyPy Runtime"
weight: 30
description: "PyPy resolver semantics, per-TUI bottleneck analysis, diagnostics, and overrides"
---

aitasks ships with an opt-in **PyPy 3.11** sibling venv for the long-running Textual TUIs. The user-facing install flow lives in [Installation → PyPy Runtime]({{< relref "/docs/installation/pypy" >}}); this page documents the resolver semantics, the per-TUI bottleneck reasoning, runtime overrides, and diagnostic commands.

## Resolver semantics

Once the PyPy venv exists at `~/.aitask/pypy_venv/`, the launcher resolver in `.aitask-scripts/lib/python_resolve.sh` auto-routes the five fast-path TUIs through PyPy:

| TUI            | Command           |
|----------------|-------------------|
| Board          | `ait board`       |
| Code Browser   | `ait codebrowser` |
| Settings       | `ait settings`    |
| Brainstorm     | `ait brainstorm`  |
| Syncer         | `ait syncer`      |

CPython remains the default for everything else. PyPy is **sibling**, not replacement — short-lived CLIs (`ait pick`, `ait create`, etc.), the `monitor` / `minimonitor` TUIs, and `ait stats-tui` continue on CPython, where PyPy's ~150-300 ms warmup would hurt, where the bottleneck is OS-level (fork/exec) and PyPy cannot help, or where the TUI depends on a CPython-only package (`plotext`).

## TUIs that stay on CPython

- **`ait monitor` / `ait minimonitor`** — bottleneck is `fork+exec(tmux)` per refresh tick, an OS-level cost PyPy cannot accelerate. A separate task will empirically re-evaluate; until then, these stay on CPython.
- **`ait stats-tui`** — chart panes depend on the `plotext` package, which is installed only in the CPython venv.
- **`ait stats`** (one-shot CLI) and other short-lived CLIs — the ~150-300 ms PyPy warmup would dominate total runtime.

## Override per invocation — `AIT_USE_PYPY`

The `AIT_USE_PYPY` env var forces a specific interpreter for a single command:

| `AIT_USE_PYPY` | PyPy installed? | Result |
|----------------|-----------------|--------|
| `1`            | Yes             | PyPy (forced) |
| `1`            | No              | error: install with `ait setup --with-pypy` |
| `0`            | (any)           | CPython (override) |
| unset          | Yes             | PyPy (default once installed) |
| unset          | No              | CPython |

Examples:

```bash
AIT_USE_PYPY=0 ait board       # one-off CPython run with PyPy installed
AIT_USE_PYPY=1 ait codebrowser # error if PyPy not installed
```

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

For the per-TUI bottleneck analysis and PyPy compatibility audit that motivated this design, see [`aidocs/python_tui_performance.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/python_tui_performance.md) in the repo.
