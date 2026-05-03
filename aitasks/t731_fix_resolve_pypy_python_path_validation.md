---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [ait_setup, python, installation]
created_at: 2026-05-03 08:31
updated_at: 2026-05-03 08:31
boardidx: 50
---

## Origin

Spawned from t728 during Step 8b review.

## Upstream defect

- `lib/python_resolve.sh:112-119 — resolve_pypy_python() does not validate sys.implementation.name == 'pypy' on its PATH-resolved candidates (second loop). Validation IS done on the first loop (override + venv path, lines 103-110). A misnamed CPython binary on PATH (e.g., a pypy3 shim pointing at /usr/bin/python3 or a Homebrew alias gone wrong) would falsely succeed at runtime and pollute _AIT_RESOLVED_PYPY for the rest of the shell. find_pypy() in aitask_setup.sh validates uniformly across all candidates; resolve_pypy_python() should match.`

## Diagnostic context

While auditing resolve_pypy_python() during t728 (a separate one-line literal substitution to honor AIT_PYPY_PREFERRED in the PATH lookup), the asymmetry between the two candidate loops became visible:

- First loop (lines 103-110): validates `impl.name == 'pypy'` after the executable check.
- Second loop (lines 112-119): just runs `command -v` and accepts whatever's executable, without any impl.name check.

find_pypy() in `aitask_setup.sh:463-483` puts all four candidate types through one uniform loop that validates impl.name on every candidate. The runtime resolver should match that contract — the runtime cost is identical (one `python -c` call per candidate, only on a cache miss), and the failure mode (wrong interpreter cached, downstream textual import errors that don't obviously trace back to PyPy detection) is much harder to debug than the install-time equivalent.

`tests/test_python_resolve_pypy.sh` Test 7 already covers the misnamed-CPython rejection at the venv path (`PYPY_VENV_DIR/bin/python`) but not at the PATH path. A new test case mirroring Test 7 — placing a misnamed CPython at `$SCRATCH/bin/pypy3` and asserting `resolve_pypy_python` does NOT return it — should be added.

Note: `tests/test_python_resolve_pypy.sh` is also pre-existing-broken (Test 2 fails because the PyPy stub at `$SCRATCH/.aitask/pypy_venv/bin/python` is not detected by `resolve_pypy_python`, despite Test 7 demonstrating that path *is* exercised — likely a bug in the stub's `-c` handling). That broken-test investigation may need to land first or alongside.

## Suggested fix

In `lib/python_resolve.sh`, restructure `resolve_pypy_python()` so the impl.name validation runs on every candidate, not just the first loop. Concretely:

```bash
resolve_pypy_python() {
    if [[ -n "${_AIT_RESOLVED_PYPY:-}" ]]; then
        echo "$_AIT_RESOLVED_PYPY"
        return 0
    fi
    local cand resolved
    local candidates=(
        "${AIT_PYPY:-}"
        "$PYPY_VENV_DIR/bin/python"
        "pypy$AIT_PYPY_PREFERRED"
        pypy3
    )
    for cand in "${candidates[@]}"; do
        [[ -z "$cand" ]] && continue
        if [[ "$cand" == /* ]]; then
            resolved="$cand"
        else
            resolved="$(command -v "$cand" 2>/dev/null || true)"
        fi
        [[ -z "$resolved" || ! -x "$resolved" ]] && continue
        if "$resolved" -c "import sys; sys.exit(0 if sys.implementation.name == 'pypy' else 1)" 2>/dev/null; then
            _AIT_RESOLVED_PYPY="$resolved"
            echo "$resolved"
            return 0
        fi
    done
    return 0
}
```

This matches the structure of `find_pypy()` in `aitask_setup.sh` (which is intentionally separate per the t718_1 install-vs-runtime split — see t728's plan file for that analysis).

## Verification

- Add a Test 9 to `tests/test_python_resolve_pypy.sh` mirroring Test 7: place a misnamed CPython stub at `$SCRATCH/bin/pypy3`, ensure `resolve_pypy_python` does NOT return it.
- `shellcheck .aitask-scripts/lib/python_resolve.sh` clean.
- Existing Test 2 + Test 7 still pass (after the pre-existing Test 2 breakage is resolved).
