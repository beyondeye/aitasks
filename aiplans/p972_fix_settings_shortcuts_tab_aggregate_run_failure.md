---
Task: t972_fix_settings_shortcuts_tab_aggregate_run_failure.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Fix settings-shortcuts-tab aggregate-run failure (t972)

## Context

`tests/test_settings_shortcuts_tab.py::test_tab_titles_carry_current_shortcut`
fails **only** under the aggregate single-process runner
(`tests/run_all_python_tests.sh`, which falls back to `unittest discover` since
pytest is absent), passing standalone. Assertion diff:
`'Proje(c)t Config' != 'Proje(C)t Config'` — the rendered tab label has a
lowercase mnemonic where the test expects uppercase.

**Root cause (confirmed):** `shortcuts_mixin.py` owns a module-level cache
`_LABEL_CASE_CACHE` for the global `shortcut_label_case` user setting
(`upper` → uppercase mnemonic, `preserve` → case-preserving). It is resolved
once from `aitasks/metadata/userconfig.yaml` and cached. The developer's local
(gitignored) `userconfig.yaml` contains `shortcut_label_case: preserve`, so any
test that resolves the cache while cwd is the repo root — i.e. any TUI test that
renders a shortcut label without chdir-ing into a temp workspace — leaves the
global cache at `False` (preserve). Verified: `_resolve_uppercase_key()` returns
`False` at repo-root cwd.

`test_settings_shortcuts_tab._Fixture.setUp` resets `keybinding_registry` and
chdirs into a temp workspace with a **setting-less** userconfig, but never calls
`refresh_label_case()`. Because the cache is already populated (`False`) by an
earlier module, the lazy resolver returns the stale `False` instead of reading
the temp userconfig — producing lowercase `(c)`. Standalone, the cache starts
`None` and resolves against the temp userconfig (no setting → default `upper`),
so it passes.

This is **not a single-leaker bug** — the leaked value comes from the real
userconfig read by *many* repo-root TUI tests, so resetting one module's
tearDown would not make the victim order-independent. The robust fix is to make
the victim isolate this global state itself, exactly as the sibling
`tests/test_shortcut_label_case.py::_Fixture` already does (it calls
`refresh_label_case()` in both `setUp` and `tearDown`).

## Approach

Add `shortcut_label_case` cache isolation to
`tests/test_settings_shortcuts_tab.py`'s `_Fixture`, mirroring the established
pattern in `tests/test_shortcut_label_case.py`.

### File: `tests/test_settings_shortcuts_tab.py`

1. **Import** the reset helper near the other lib imports (after the
   `import keybinding_registry` / `import shortcut_persist` lines):
   ```python
   from shortcuts_mixin import refresh_label_case  # noqa: E402
   ```

2. **`_Fixture.setUp`** — call `refresh_label_case()` alongside the existing
   `keybinding_registry._reset_for_tests()` so the cache is dropped and the next
   resolve reads the temp workspace's (setting-less) userconfig → default
   `upper`:
   ```python
   keybinding_registry._reset_for_tests()
   refresh_label_case()
   ```

3. **`_Fixture.tearDown`** — call `refresh_label_case()` alongside the existing
   final `keybinding_registry._reset_for_tests()` so this module does not leak a
   resolved cache to later modules:
   ```python
   keybinding_registry._reset_for_tests()
   refresh_label_case()
   ```

`refresh_label_case()` only sets the cache to `None` (lazy); the real resolution
defers to render time, when cwd is the temp workspace. Validated with a probe:
poisoned cache (`False` at repo root) → after `refresh_label_case()` against a
setting-less temp userconfig → `True` (uppercase). Order-independent.

No production code changes. The `shortcut_label_case` feature, the cache, and
`refresh_label_case()` all behave correctly — this is purely test-isolation
hygiene.

## Risk

### Code-health risk: low
- Test-only change: one import plus two one-line calls in a single test
  fixture, mirroring an existing sibling-test pattern. No production code
  touched, blast radius one file. · severity: low · → mitigation: none

### Goal-achievement risk: low
- Fix is validated by direct probe and makes the failure resolution
  order-independent; the suggested-fix alternative (victim-side setUp) is the
  one chosen, and it is strictly more robust than patching a single leaker. ·
  severity: low · → mitigation: none

## Verification

1. **Targeted (standalone still passes):**
   ```bash
   bash tests/run_all_python_tests.sh -k test_tab_titles_carry_current_shortcut
   ```
   (unittest fallback runs the single matching test → OK)

2. **Aggregate run (the actual regression) now passes:**
   ```bash
   bash tests/run_all_python_tests.sh
   ```
   Expect: the previously-failing
   `test_tab_titles_carry_current_shortcut` passes; suite ends with `OK`
   (no `FAILED (failures=1)`).

3. Optional sanity: temporarily confirm the developer userconfig still has
   `shortcut_label_case: preserve` (the trigger) so the test is exercised
   against the leak condition.

## Step 9 — Post-Implementation

Standard archival: commit the test fix (`bug: ... (t972)`), update + commit the
plan via `./ait git`, then `./.aitask-scripts/aitask_archive.sh 972` and
`./ait git push`. No branch/worktree to clean up (working on current branch).
