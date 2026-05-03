---
Task: t732_2_cluster_b_python_resolve_version_comparison.md
Parent Task: aitasks/t732_fix_failing_pre_existing_test_suite.md
Sibling Tasks: aitasks/t732/t732_*.md
Archived Sibling Plans: aiplans/archived/p732/p732_*.md
Worktree: (current branch — fast profile sets create_worktree:false)
Branch: (current branch)
Base branch: main
---

# p732_2 — Cluster B: python_resolve.sh version comparison

## Goal

Fix `tests/test_python_resolve.sh` rejecting Python 3.13.0 as below the 3.11 minimum. Companion test `test_python_resolve_pypy.sh` is already passing (t728+t731) — keep it green.

## Confirmed failure (today)

```
Error: Python >=3.11 required (found 3.13.0 at /tmp/test_python_resolve.XXXXXX/bin/python3).
```

## Steps

1. Read `aitasks/t732/t732_2_cluster_b_python_resolve_version_comparison.md` for full context.
2. Read `.aitask-scripts/lib/python_resolve.sh` to locate the version comparator (around `AIT_VENV_PYTHON_MIN` at line 32).
3. Identify the bug class:
   - Lex-vs-numeric? Replace with `printf '%s\n%s\n' "$found" "$min" | sort -V | head -1` or equivalent numeric arithmetic.
   - Stub-interaction? `bash -x tests/test_python_resolve.sh 2>&1 | head -120` to see what invocation the resolver uses; extend `make_stub` (lines ~50-90 of the test) to intercept that form.
4. Patch and re-run: `bash tests/test_python_resolve.sh`.
5. Sanity: `bash tests/test_python_resolve_pypy.sh` still green.

## Verification

- `bash tests/test_python_resolve.sh` passes.
- `bash tests/test_python_resolve_pypy.sh` still passes.
- `./ait setup` on Python 3.13 host doesn't print spurious "≥3.11 required" errors.

## Step 9

Archive via `./.aitask-scripts/aitask_archive.sh 732_2`.
