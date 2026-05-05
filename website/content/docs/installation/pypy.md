---
title: "PyPy Runtime (Optional)"
linkTitle: "PyPy Runtime"
weight: 60
description: "Optional PyPy 3.11 sibling interpreter for faster long-running TUIs"
---

## What it is

aitasks supports an opt-in **PyPy 3.11** sibling interpreter for the
long-running Textual TUIs. PyPy's tracing JIT typically yields **2-5×**
speedups on Textual + Rich workloads, helping board / codebrowser /
settings / brainstorm / syncer TUIs feel snappier under heavy use.

CPython remains the default. PyPy is sibling, not replacement —
short-lived CLI scripts (`ait pick`, `ait create`, etc.), the
monitor / minimonitor TUIs, and `ait stats-tui` continue to use CPython,
where PyPy's ~150-300 ms warmup would hurt, where the bottleneck is
OS-level (fork/exec) and PyPy cannot help, or where the TUI depends on
a CPython-only package (`plotext`).

## Install

```bash
ait setup --with-pypy
```

This installs PyPy 3.11 into `~/.aitask/pypy_venv/` (~100-150 MB) with the
same dependency set as the regular CPython venv. `ait setup` (without the
flag) also offers an interactive prompt on TTYs.

Once installed, the five fast-path TUIs auto-route through PyPy:

| TUI            | Command           |
|----------------|-------------------|
| Board          | `ait board`       |
| Code Browser   | `ait codebrowser` |
| Settings       | `ait settings`    |
| Brainstorm     | `ait brainstorm`  |
| Syncer         | `ait syncer`      |

No further action required — the resolver in `lib/python_resolve.sh` picks
PyPy automatically when the venv exists.

## Override per invocation

The `AIT_USE_PYPY` env var lets you force CPython (or force PyPy) for a
single command:

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

## TUIs that don't use PyPy

`ait monitor` and `ait minimonitor` stay on CPython. Their bottleneck is
`fork+exec(tmux)` per refresh tick — an OS-level cost that PyPy cannot
accelerate. A separate task will empirically verify whether PyPy yields
any meaningful improvement under representative workloads; until that
lands, monitor / minimonitor stay on CPython.

`ait stats-tui` stays on CPython because its chart panes depend on the
`plotext` package, which is installed only in the CPython venv.

`ait stats` (the one-shot CLI variant) and other short-lived CLIs also
stay on CPython — the ~150-300 ms PyPy warmup would dominate their total
runtime.

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

## Disable / remove

- **One-off:** `AIT_USE_PYPY=0 ait board`
- **Persistent:** `rm -rf ~/.aitask/pypy_venv` — the resolver falls
  through to CPython silently. Re-run `ait setup --with-pypy` to reinstall.

## Background

For the per-TUI bottleneck analysis and PyPy compatibility audit that
motivated this design, see
[`aidocs/python_tui_performance.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/python_tui_performance.md)
in the repo.

---

**Next:** [Known Issues]({{< relref "known-issues" >}})
