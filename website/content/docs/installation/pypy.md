---
title: "PyPy Runtime (Optional)"
linkTitle: "PyPy Runtime"
weight: 60
description: "Optional PyPy 3.11 sibling interpreter for faster long-running TUIs"
---

aitasks supports an opt-in **PyPy 3.11** sibling interpreter for `ait board`. PyPy's tracing JIT yields a measurable speedup on the board's Textual + Rich workload, which is one of the framework's primary interaction surfaces.

**Scope:** the installed PyPy interpreter currently accelerates `ait board` only. Other Textual TUIs (`ait settings`, `ait brainstorm`, `ait syncer`, `ait codebrowser`, `ait monitor`, `ait minimonitor`, `ait stats`) run on the default CPython venv — they either lose under PyPy in empirical benchmarks or were never routed there in the first place.

CPython remains the default; PyPy is a sibling install, not a replacement. For the resolver semantics, per-TUI bottleneck analysis, the `AIT_USE_PYPY` override, and diagnostics, see [Development → PyPy Runtime — Internals]({{< relref "/docs/development/pypy" >}}).

## Install

```bash
ait setup --with-pypy
```

This installs PyPy 3.11 into `~/.aitask/pypy_venv/` (~100-150 MB) with the same dependency set as the regular CPython venv. `ait setup` (without the flag) also offers an interactive prompt on TTYs.

After installation, `ait board` auto-routes through PyPy on next launch — no further action required.

## Disable / remove

- **One-off override:** `AIT_USE_PYPY=0 ait board` (see [Development → PyPy Runtime — Internals]({{< relref "/docs/development/pypy" >}}) for the full override table).
- **Persistent uninstall:** `rm -rf ~/.aitask/pypy_venv` — the resolver falls through to CPython silently. Re-run `ait setup --with-pypy` to reinstall.

---

**Next:** [Known Issues]({{< relref "known-issues" >}})
