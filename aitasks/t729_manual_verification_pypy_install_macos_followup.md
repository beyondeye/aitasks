---
priority: medium
effort: medium
depends: [727]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [727]
created_at: 2026-04-30 16:01
updated_at: 2026-04-30 16:01
boardidx: 10
boardcol: manual_verifications
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t727

## Verification Checklist

- [ ] Run 'ait setup --with-pypy' on macOS (Apple Silicon and/or Intel) — confirm 'brew install pypy3.11' runs and exits 0.
- [ ] Confirm '~/.aitask/python/pypy-3.11/bin/python3' symlink is created and points into the brew Cellar (the new layout-symmetry symlink added by t727 Step 4).
- [ ] Confirm find_pypy() resolves the brew-installed PyPy: 'bash -c "source .aitask-scripts/lib/python_resolve.sh; AIT_PYPY_PREFERRED=3.11 resolve_pypy_python"' echoes the symlink path.
- [ ] Run 'AIT_USE_PYPY=1 ait board' on macOS — confirm board launches via PyPy without startup error.
- [ ] Override test: 'AIT_PYPY_PREFERRED=3.12 ait setup --with-pypy' (assuming a 3.12 brew formula exists) — confirm the dynamic 'pypy$AIT_PYPY_PREFERRED' lookup tries the 3.12 formula. If no 3.12 formula yet, document the failure mode (brew install returns 'No available formula') as expected.
- [ ] Re-run 'ait setup --with-pypy' twice in a row on macOS — confirm idempotent behavior (no re-install, symlink unchanged).
