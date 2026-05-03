---
Task: t728_fix_resolve_pypy_python_hardcoded_literal.md
Worktree: (none — working on current branch per profile fast)
Branch: main
Base branch: main
---

## Context

`AIT_PYPY_PREFERRED` is the single source of truth for the preferred PyPy version, defined at `lib/python_resolve.sh:37`. The same file's `resolve_pypy_python()` function ignores it: line 112 hardcodes `pypy3.11 pypy3` as the PATH-candidate list. Bumping `AIT_PYPY_PREFERRED` to `3.12` would silently match a stale `pypy3.11` binary on PATH first.

Task t727 fixed the symmetric bug in `aitask_setup.sh`'s `find_pypy()` (line 468) by substituting `"pypy$AIT_PYPY_PREFERRED" pypy3`. This task applies the byte-equivalent fix to the second offender.

## Change

**File:** `.aitask-scripts/lib/python_resolve.sh`

**Line 112 — change:**
```bash
    for cand in pypy3.11 pypy3; do
```
**to:**
```bash
    for cand in "pypy$AIT_PYPY_PREFERRED" pypy3; do
```

That is the entire change. No new functions, no refactor, no test fixes (out of scope per task description).

## Out of scope (per task description)

- Deduping `find_pypy()` and `resolve_pypy_python()` — they live in different modules with different consumers.
- Fixing `tests/test_python_resolve_pypy.sh` — pre-existing-broken (PyPy stub not detected by `resolve_pypy_python` even when present at `~/.aitask/pypy_venv/bin/python`). Track separately.

## Verification

1. **Byte-equivalence check** vs t727's fix:
   ```bash
   grep -n '"pypy$AIT_PYPY_PREFERRED" pypy3' .aitask-scripts/aitask_setup.sh .aitask-scripts/lib/python_resolve.sh
   ```
   Both files should print a matching line.

2. **No new shellcheck warnings:**
   ```bash
   shellcheck .aitask-scripts/lib/python_resolve.sh
   ```

3. **Behavior probe** (manual):
   ```bash
   AIT_PYPY_PREFERRED=3.12 bash -c "source .aitask-scripts/lib/python_resolve.sh; resolve_pypy_python"
   ```
   Should attempt `pypy3.12` lookup before `pypy3` (after this fix), instead of `pypy3.11` then `pypy3` (before). On a system with no PyPy installed this returns empty without erroring — the verification is that the script doesn't fail.

4. **Reference Step 9** (Post-Implementation): commit, archive via `aitask_archive.sh 728`, push.
