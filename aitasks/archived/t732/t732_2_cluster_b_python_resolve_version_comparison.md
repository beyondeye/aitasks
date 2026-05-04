---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [testing, bash_scripts, portability]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7
created_at: 2026-05-03 16:29
updated_at: 2026-05-04 17:30
completed_at: 2026-05-04 17:30
---

## Context

Child 2 of t732. Cluster B: `lib/python_resolve.sh` rejects a stub Python 3.13.0 as below the 3.11 minimum. The companion test `test_python_resolve_pypy.sh` was originally also in this cluster but has since been fixed (t728 + t731), so this child is scoped to the single remaining failure.

## Failing test

### tests/test_python_resolve.sh
```
Error: Python >=3.11 required (found 3.13.0 at /tmp/test_python_resolve.XXXXXX/bin/python3).
       Run 'ait setup' to install a newer interpreter.
```
3.13.0 IS ≥ 3.11. The resolver's version-comparison logic incorrectly rejects it.

## Root cause hypothesis

Two candidates, in priority order:

1. **Lex-vs-numeric comparison.** `lib/python_resolve.sh` may compare versions as strings: `"3.13.0" < "3.11"` is true lexically because `1` < `1` then comparing `3` vs `1` at position 3 — though more likely `"3.1"` (truncated) vs `"3.11"`. Need to read the actual comparator. Look around `AIT_VENV_PYTHON_MIN` (`lib/python_resolve.sh:32`) for the comparator.

2. **Stub-interaction bug.** The test scaffolds a fake `python3` via `make_stub` (see `tests/test_python_resolve.sh:50-90`) that intercepts `--version` and `-c` calls. The stub's `-c` path delegates to the real interpreter with `sys.version_info` patched. The resolver may probe via a path the stub doesn't intercept (e.g., `python3 -V`, `python3 -m platform`), getting the host's actual version instead of the patched one.

## Key files to modify

- `.aitask-scripts/lib/python_resolve.sh` — fix the version comparator. Use `sort -V` or numeric awk arithmetic, NOT lexicographic comparison.
- Possibly `tests/test_python_resolve.sh` — the `make_stub` may need to intercept additional invocation forms if the resolver probes via more than `-c`.

## Reference patterns

- `lib/python_resolve.sh:32` — `AIT_VENV_PYTHON_MIN="${AIT_VENV_PYTHON_MIN:-3.11}"`
- `lib/python_resolve.sh:37` — `AIT_PYPY_PREFERRED="${AIT_PYPY_PREFERRED:-3.11}"`
- `tests/test_python_resolve.sh:50-90` — `make_stub` block (the harness)
- `tests/test_python_resolve_pypy.sh` (currently passing) — for any portability gotchas the pypy fix already handled
- t728 commit (`22f64d04`) and t731 commit (`74c59788`) — recent resolver fixes; do not overlap

## Implementation plan

1. Read `lib/python_resolve.sh` end-to-end to locate the comparator.
2. If lex-comparison: convert to `printf '%s\n%s\n' "$found" "$min" | sort -V | head -1` style or pure-shell numeric comparison.
3. Run `bash -x tests/test_python_resolve.sh 2>&1 | head -100` to confirm the stub path being exercised, in case fix #2 is also needed.
4. `bash tests/test_python_resolve.sh` passes.
5. Sanity: `bash tests/test_python_resolve_pypy.sh` still passes.

## Verification

- `bash tests/test_python_resolve.sh` passes.
- `bash tests/test_python_resolve_pypy.sh` still passes (regression check).
- `./ait setup` on a host with Python 3.13 still finds the venv interpreter without spurious "≥3.11 required" errors.
