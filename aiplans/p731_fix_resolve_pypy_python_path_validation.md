---
Task: t731_fix_resolve_pypy_python_path_validation.md
Base branch: main
plan_verified: []
---

## Context

`resolve_pypy_python()` in `.aitask-scripts/lib/python_resolve.sh` validates `sys.implementation.name == 'pypy'` on its first candidate loop (override + venv path) but NOT on its second loop (PATH lookups for `pypy<version>` / `pypy3`). A misnamed CPython on PATH (e.g., a `pypy3` shim pointing at CPython) would silently pollute `_AIT_RESOLVED_PYPY` for the rest of the shell. `find_pypy()` in `aitask_setup.sh` validates uniformly across all candidates; the runtime resolver should match.

While auditing, a separate pre-existing breakage in `tests/test_python_resolve_pypy.sh` was confirmed: Tests 2-8 silently never run on this machine (only Test 1 runs) because the test stubs invoke `REAL_PY=$(command -v python3)` which resolves to the framework wrapper at `~/.aitask/bin/python3`. That wrapper is `exec "$HOME/.aitask/venv/bin/python" "$@"`, but the tests override `HOME=$SCRATCH` in subshells, so the wrapper exits 127 and `set -e` aborts the whole test file at Test 2's `result=$(...)` assignment. This must land in the same task — without it, the new Test 9 cannot reliably validate the fix.

## Files to modify

- `.aitask-scripts/lib/python_resolve.sh` — restructure `resolve_pypy_python()` to validate impl.name on every candidate.
- `tests/test_python_resolve_pypy.sh` — (a) resolve REAL_PY to the underlying venv binary instead of the wrapper, (b) add Test 9 covering misnamed CPython on PATH.

## Implementation

### Step 1: Restructure `resolve_pypy_python()` in `lib/python_resolve.sh`

Replace lines 97-121 (the function body) with the unified candidate loop from the task description's Suggested Fix. Single loop iterates `(AIT_PYPY, PYPY_VENV_DIR/bin/python, pypy<AIT_PYPY_PREFERRED>, pypy3)`; absolute paths are kept verbatim, relative names are resolved via `command -v`; every successful candidate must pass the `sys.implementation.name == 'pypy'` check before being cached/returned.

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

This matches the structure of `find_pypy()` in `aitask_setup.sh:463-483`.

### Step 2: Fix REAL_PY resolution in `tests/test_python_resolve_pypy.sh`

Replace line 42:

```bash
REAL_PY="$(command -v python3)"
```

with a resolution that bypasses the framework wrapper and locks in the actual binary path (independent of `$HOME`):

```bash
# Resolve to the underlying interpreter so stubs work after HOME is overridden.
# (`command -v python3` may return the framework wrapper at ~/.aitask/bin/python3,
# which exec's into $HOME/.aitask/venv/bin/python — broken once HOME=$SCRATCH.)
REAL_PY="$(python3 -c 'import sys; print(sys.executable)' 2>/dev/null)"
[[ -z "$REAL_PY" || ! -x "$REAL_PY" ]] && REAL_PY="$(command -v python3)"
```

`sys.executable` resolves through the wrapper to the actual venv `python3` binary on Linux/macOS, which doesn't depend on `HOME` at runtime. The fallback covers exotic environments where the introspection fails.

### Step 3: Add Test 9 in `tests/test_python_resolve_pypy.sh`

Insert before the `=== Test 8 ===` block (so the double-source test stays last). Mirror Test 7 but place the misnamed CPython on PATH at `$SCRATCH/bin/pypy3`:

```bash
# === Test 9: misnamed CPython on PATH (pypy3) is rejected (impl != pypy) ===
unset _AIT_RESOLVED_PYPY
rm -f "$SCRATCH/.aitask/pypy_venv/bin/python"          # clear venv path
make_cpython_stub pypy3 "3.11.0"                        # CPython masquerading as pypy3 on PATH
result="$(HOME="$SCRATCH" PATH="$SUBPATH" "$TEST_BASH" --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON _AIT_RESOLVED_PYPY AIT_PYPY
source '$LIB'
resolve_pypy_python
")"
if [[ "$result" == "$SCRATCH/bin/pypy3" ]]; then
    FAIL=$((FAIL + 1))
    TOTAL=$((TOTAL + 1))
    echo "FAIL: Test 9: misnamed CPython on PATH should be rejected"
    echo "  actual: $result"
else
    PASS=$((PASS + 1))
    TOTAL=$((TOTAL + 1))
fi
rm -f "$SCRATCH/bin/pypy3"                              # tidy for any later additions
```

Notes:
- The venv path is removed so the only viable candidate is the PATH `pypy3` stub — confirms the fix targets the correct loop.
- The trailing `rm -f` keeps Test 9 from leaking into Test 8 (no current dependency, but defensive).

## Verification

1. `bash tests/test_python_resolve_pypy.sh` — expect `Tests: 9  Pass: 9  Fail: 0` (currently runs only Test 1 then aborts).
2. `shellcheck .aitask-scripts/lib/python_resolve.sh` — clean.
3. Spot-check that the existing Test 7 still passes for the *right* reason after the REAL_PY fix (the impl.name check should now actively reject the fake CPython at the venv path, not just succeed by accident from a stub exec failure).

## Step 9 (Post-implementation)

Standard archival flow per task-workflow SKILL.md Step 9: no separate branch (working on `main` per `fast` profile), so skip merge; commit with `bug: <description> (t731)` format; run `./.aitask-scripts/aitask_archive.sh 731`; push.

## Final Implementation Notes

- **Actual work done:** Implemented all three planned steps verbatim. (1) `resolve_pypy_python()` body replaced with the unified candidate loop — `(AIT_PYPY, PYPY_VENV_DIR/bin/python, pypy<AIT_PYPY_PREFERRED>, pypy3)` — that resolves absolute paths verbatim, looks up relative names via `command -v`, and gates every successful candidate behind the `sys.implementation.name == 'pypy'` check before caching. (2) `tests/test_python_resolve_pypy.sh` REAL_PY now resolves via `python3 -c 'import sys; print(sys.executable)'` first (with a `command -v` fallback), bypassing the framework wrapper at `~/.aitask/bin/python3` whose `exec "$HOME/.aitask/venv/bin/python"` indirection breaks once tests override `HOME=$SCRATCH`. (3) Test 9 added before Test 8: clears the venv stub, places a `make_cpython_stub pypy3 "3.11.0"` on PATH at `$SCRATCH/bin/pypy3`, asserts `resolve_pypy_python` does NOT return it.
- **Deviations from plan:** None.
- **Issues encountered:** Confirmed during diagnosis that the REAL_PY breakage was masking the silent-PASS of Test 7 (the venv-path CPython stub was rejected because the wrapper `exec` failed with 127, not because the impl.name check actively rejected it). Both effects (wrapper-exec failure → spurious rejection; broken Test 2 from same root cause) collapse into a single 5-line REAL_PY change that lifts the test file end-to-end.
- **Key decisions:** Kept the `command -v python3` fallback in REAL_PY resolution to cover environments where `sys.executable` introspection is unavailable (extremely unlikely in practice, but defensive and zero-cost). Inserted Test 9 BEFORE Test 8 so the `Test 8: double-source guard` remains the conceptual end-cap of the file. Added a trailing `rm -f "$SCRATCH/bin/pypy3"` to Test 9 even though no current test depends on its absence — defensive against future test additions.
- **Upstream defects identified:** None.

### Verification results

- `bash tests/test_python_resolve_pypy.sh` → `Tests: 9  Pass: 9  Fail: 0` (was: only Test 1 ran, then `set -e` aborted at Test 2's `result=$(...)` assignment).
- `shellcheck .aitask-scripts/lib/python_resolve.sh` → clean (only the pre-existing SC1091 info note about following `terminal_compat.sh`, which is by design — same as before this task).
- Test 7 now passes for the right reason: the venv-path fakepy stub correctly reports `sys.implementation.name == 'cpython'`, so the impl.name guard actively rejects it.
