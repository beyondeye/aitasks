---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [custom_shortcuts, tui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-10 09:05
updated_at: 2026-07-15 10:42
---

## Origin

Spawned from t1120_6 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/shortcut_scopes.py:100-120 (module load helper)` — registry-coverage sweep fails on Python 3.14: the module is exec'd via spec without registering in sys.modules first, so dataclass KW_ONLY resolution crashes for syncer_app (`'NoneType' object has no attribute '__dict__'`); `tests/test_shortcuts_registry_coverage.sh` fails on a clean tree.

## Diagnostic context

While registering the new chatlink TUI in `KNOWN_BINDING_SOURCES` (t1120_6), `tests/test_shortcuts_registry_coverage.sh` reported `syncer_app: import failed: AttributeError: 'NoneType' object has no attribute '__dict__'`. Verified pre-existing: the failure reproduces identically on a clean tree with all t1120_6 changes stashed. Minimal repro:

```python
import importlib.util
spec = importlib.util.spec_from_file_location('syncer_app', 'syncer/syncer_app.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)   # crashes in dataclasses._is_type on py3.14
```

Python 3.14's `dataclasses._is_type` resolves `KW_ONLY` (and other markers) via `sys.modules.get(cls.__module__).__dict__` — when the module was never inserted into `sys.modules` before `exec_module`, the `get` returns `None` and the attribute access crashes.

## Suggested fix

In the sweep's module loader, insert the module into `sys.modules[module_name]` before `spec.loader.exec_module(m)` (the standard importlib recipe), removing it on failure. Then confirm `tests/test_shortcuts_registry_coverage.sh` passes on Python 3.14.
