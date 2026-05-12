---
title: "PyPy Runtime (Optional)"
linkTitle: "PyPy Runtime"
weight: 60
description: "Optional PyPy 3.11 sibling interpreter for faster long-running TUIs"
---

aitasks supports an opt-in **PyPy 3.11** sibling interpreter for the long-running Textual TUIs. PyPy's tracing JIT typically yields **2-5×** speedups on Textual + Rich workloads, helping `ait board`, `ait codebrowser`, `ait settings`, `ait brainstorm`, and `ait syncer` feel snappier under heavy use.

CPython remains the default; PyPy is a sibling install, not a replacement. For the resolver semantics, per-TUI bottleneck analysis, the `AIT_USE_PYPY` override, and diagnostics, see [Development → PyPy Runtime — Internals]({{< relref "/docs/development/pypy" >}}).

## Install

```bash
ait setup --with-pypy
```

This installs PyPy 3.11 into `~/.aitask/pypy_venv/` (~100-150 MB) with the same dependency set as the regular CPython venv. `ait setup` (without the flag) also offers an interactive prompt on TTYs.

After installation, the five fast-path TUIs auto-route through PyPy on next launch — no further action required.

## Disable / remove

- **One-off override:** `AIT_USE_PYPY=0 ait board` (see [Development → PyPy Runtime — Internals]({{< relref "/docs/development/pypy" >}}) for the full override table).
- **Persistent uninstall:** `rm -rf ~/.aitask/pypy_venv` — the resolver falls through to CPython silently. Re-run `ait setup --with-pypy` to reinstall.

---

**Next:** [Known Issues]({{< relref "known-issues" >}})
