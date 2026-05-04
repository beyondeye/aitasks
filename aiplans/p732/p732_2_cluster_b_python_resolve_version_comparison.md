---
Task: t732_2_cluster_b_python_resolve_version_comparison.md
Parent Task: aitasks/t732_fix_failing_pre_existing_test_suite.md
Sibling Tasks: aitasks/t732/t732_3_cluster_c_branch_mode_and_upgrade_commit.md, aitasks/t732/t732_4_cluster_d_external_tool_drift.md, aitasks/t732/t732_6_cluster_f_codemap_help_text.md, aitasks/t732/t732_7_verify_full_suite_zero_failures.md
Archived Sibling Plans: aiplans/archived/p732/p732_1_cluster_a_textual_tui_api_drift.md, aiplans/archived/p732/p732_5_cluster_z_test_scaffold_missing_aitask_path.md
Base branch: main
plan_verified:
  - claudecode/opus4_7 @ 2026-05-04 17:23
---

# p732_2 — Cluster B: python_resolve.sh test scaffold REAL_PY wrapper bug (verified)

## Context

`bash tests/test_python_resolve.sh` fails Test 6 (`require_modern_python accepts 3.13`) on hosts that have run `ait setup`. The error message is misleading — it claims the version comparator rejects 3.13.0 as below 3.11, but the comparator is correct. The real bug is in the test harness: `REAL_PY` resolves to the framework's `python3` wrapper, which is broken inside the test's `HOME`-overridden subshells.

## Verified diagnosis

The plan's two original hypotheses were:
1. **Lex-vs-numeric comparator** — RULED OUT. `lib/python_resolve.sh:86` uses `"$p" -c "import sys; sys.exit(0 if sys.version_info >= ($major, $minor) else 1)"` — Python tuple comparison is numeric and correct.
2. **Stub-interaction** — CONFIRMED, with a concrete refinement.

**Concrete root cause**

- `tests/test_python_resolve.sh:42` sets `REAL_PY="$(command -v python3)"` at the top of the test file.
- On a developer host that has run `ait setup`, `command -v python3` returns `/home/<user>/.aitask/bin/python3`.
- That path is a thin bash wrapper:
  ```bash
  #!/usr/bin/env bash
  exec "$HOME/.aitask/venv/bin/python" "$@"
  ```
- Each test subshell sets `HOME="$SCRATCH"` so framework lookups land inside the scratch dir. When the stub later runs `"$real_py" -c "..."`, the wrapper expands `$HOME` to `$SCRATCH` and tries to exec `$SCRATCH/.aitask/venv/bin/python` — a path that does not exist. Exit code 127 (`No such file or directory`); `require_modern_python` interprets that as "version check failed" and emits the misleading "Python >=3.11 required (found 3.13.0 …)" message.

The companion `tests/test_python_resolve_pypy.sh:42-47` already carries the exact fix (added during t728 / t731). Test 6's logic is otherwise correct; it just needs the same REAL_PY hardening.

## Fix

Single, minimal change to `tests/test_python_resolve.sh:42-43` — replace:

```bash
# Resolve a real Python interpreter on the host for stub delegation
REAL_PY="$(command -v python3)"
[[ -z "$REAL_PY" ]] && { echo "No python3 on host; cannot run tests."; exit 2; }
```

with the same block already in `test_python_resolve_pypy.sh:42-47`:

```bash
# Resolve to the underlying interpreter so stubs work after HOME is overridden.
# (`command -v python3` may return the framework wrapper at ~/.aitask/bin/python3,
# which exec's into $HOME/.aitask/venv/bin/python — broken once HOME=$SCRATCH.)
REAL_PY="$(python3 -c 'import sys; print(sys.executable)' 2>/dev/null)"
[[ -z "$REAL_PY" || ! -x "$REAL_PY" ]] && REAL_PY="$(command -v python3)"
[[ -z "$REAL_PY" ]] && { echo "No python3 on host; cannot run tests."; exit 2; }
```

`lib/python_resolve.sh` is **not** modified — its comparator was already correct. Diagnostic mistake corrected in the plan; no behavior change to the framework.

## Why we mirror the duplicated block (no helper extraction)

The two test files now carry identical 4-line REAL_PY resolution blocks. The aitasks `tests/` tree generally inlines its scaffolding rather than sharing a helper; this task's scope is "make the failing test pass", not "refactor test scaffolding". Mirroring the verified pattern keeps the change minimal and reviewable. If a test-scaffold helper is wanted later, it can be a sibling refactor task — not a blocker for cluster B.

## Files modified

- `tests/test_python_resolve.sh` — replace lines 42-43 with the 4-line REAL_PY-via-`sys.executable` block plus comment.

## Verification

1. `bash tests/test_python_resolve.sh` reports `Tests: 8  Pass: 8  Fail: 0`.
2. `bash tests/test_python_resolve_pypy.sh` still passes (no regression — file untouched).
3. Sanity smoke: `./ait setup`-style flow — not exercised by this change because no production code is modified; the framework comparator was already correct.

## Step 9

Archive via `./.aitask-scripts/aitask_archive.sh 732_2`.
