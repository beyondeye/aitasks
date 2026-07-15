---
Task: t1143_fix_shortcut_scopes_sweep_py314_sys_modules.md
Base branch: main
plan_verified: []
---

> NOTE (AC deviation — read first): t1143's suggested fix targets
> `.aitask-scripts/lib/shortcut_scopes.py:100-120`. That fix is **already
> committed** (t1014, commit `6b997c1073`, 2026-06-18) and the production sweep
> `register_all_known_bindings()` passes cleanly. The bug that still reproduces
> the *identical* symptom lives in a **second, un-fixed copy** of the loader
> inside the test itself. So the real fix location moves from production code to
> the test file. Everything else about the task's diagnosis holds.

# Context

`tests/test_shortcuts_registry_coverage.sh` fails on a clean tree under Python
3.14.5 with:

```
syncer_app: import failed: AttributeError: 'NoneType' object has no attribute '__dict__'
```

**Root cause.** The test has its *own* module-loader loop (independent of the
production sweep in `shortcut_scopes.py`) that does:

```python
spec = importlib.util.spec_from_file_location(name, path)
mod  = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)          # ← module never inserted into sys.modules first
```

`syncer_app` defines `@dataclass(frozen=True)` classes under
`from __future__ import annotations`. On Python 3.14, `dataclasses._is_type`
resolves the owning module via `sys.modules.get(cls.__module__).__dict__`; with
the module absent from `sys.modules`, `.get()` returns `None` and the attribute
access raises. The production loader `_load_and_register`
(`shortcut_scopes.py:111`) was fixed for exactly this in t1014 by registering
the module in `sys.modules` before `exec_module` (popping on failure). The test's
duplicate loader never received that fix.

**Verified by direct reproduction:** loading `syncer_app` test-style (no
`sys.modules` entry) raises the exact error; inserting `sys.modules[name] = mod`
before `exec_module` makes it load cleanly. `register_all_known_bindings()`
(production path) already returns `[]` (no failures).

Intended outcome: `bash tests/test_shortcuts_registry_coverage.sh` passes on
Python 3.14.

# Change

**File:** `tests/test_shortcuts_registry_coverage.sh` (the embedded Python heredoc)

Apply the same `sys.modules`-before-`exec_module` recipe the production loader
uses, to the test's two `exec_module` call sites:

1. **Main TUI loop (~line 87-89).** Register before exec, pop on failure so a
   genuinely-broken module still surfaces as an `import failed` entry rather than
   leaving a half-initialized module registered:
   ```python
   spec = importlib.util.spec_from_file_location(name, path)
   mod = importlib.util.module_from_spec(spec)
   sys.modules[name] = mod          # ← py3.14 dataclass KW_ONLY / _is_type needs this
   try:
       spec.loader.exec_module(mod)
   except Exception:
       sys.modules.pop(name, None)
       raise
   ```
   (The surrounding `try/except Exception as e` that records `import failed`
   stays; the inner pop keeps `sys.modules` clean before it re-raises into it.)

2. **brainstorm-dag load (~line 103-109).** Same pattern for the
   `brainstorm_dag_display` module load, registering under its module name
   before `exec_module` and popping on failure, for consistency and to prevent a
   future recurrence if that module gains a similar dataclass.

No production code changes — `shortcut_scopes.py` is already correct.

Keep a short inline comment at the main-loop site pointing at the same py3.14
rationale as `shortcut_scopes.py:102-110`, so the two copies don't silently
diverge again.

## Risk

### Code-health risk: low
- Test-only change mirroring an already-shipped production pattern; blast radius
  is a single test file, no runtime/product behavior touched · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Fix is confirmed by direct before/after reproduction of the exact symptom; the
  acceptance check (the test passing on 3.14) is directly runnable · severity: low · → mitigation: TBD

# Verification

1. `bash tests/test_shortcuts_registry_coverage.sh` → expect
   `PASS — every TUI registered under its expected scope` and
   `PASS: tests/test_shortcuts_registry_coverage.sh` (exit 0) on Python 3.14.5.
2. Sanity: confirm the production sweep is unaffected —
   `python3 -c "import sys; sys.path.insert(0,'.aitask-scripts/lib'); import shortcut_scopes; print(shortcut_scopes.register_all_known_bindings())"`
   still prints `[]`.
3. `shellcheck tests/test_shortcuts_registry_coverage.sh` (no new warnings).

# Step 9 (Post-Implementation)

Standard cleanup/archival per task-workflow Step 9 (current-branch profile: no
worktree/merge). Gate `risk_evaluated` is recorded post-approval; archival via
`aitask_archive.sh 1143`.
