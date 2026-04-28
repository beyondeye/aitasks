---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [ait_setup, installation, python]
created_at: 2026-04-28 11:25
updated_at: 2026-04-28 11:25
---

## Context

This is child 1 of t695. Pure additive change — introduces a centralized Python interpreter resolution layer that all subsequent children build on. Must land first; nothing depends on it yet, but t695_4 (refactor direct python3 callers) will source this helper.

The framework currently has ~9 TUI launchers using `${PYTHON:-python3}` and ~3 scripts that hardcode `python3`. There is no central place that defines "which Python should aitasks use", and no way to make remote-sandbox flows (aitask-pick-rem / aitask-pick-web — where `~/.aitask/` doesn't exist) fall back gracefully.

## Key Files to Modify

- `.aitask-scripts/lib/python_resolve.sh` (NEW — sourced lib, no whitelisting per CLAUDE.md "Adding a New Helper Script")

## Reference Files for Patterns

- `.aitask-scripts/lib/terminal_compat.sh:1-30, 80-96` — lib helper style (double-source guard via `_AIT_*_LOADED`, platform-aware functions like `sed_inplace`, `portable_date`).
- `.aitask-scripts/lib/task_utils.sh` — another lib example with helper functions. Note `_AIT_TASK_UTILS_LOADED` guard.
- `.aitask-scripts/aitask_board.sh:14,37` — existing `${PYTHON:-python3}` pattern that this helper replaces.
- `.aitask-scripts/aitask_sync.sh:39-44` — existing venv-then-python3 fallback pattern (the helper should encapsulate this).

## Implementation Plan

1. Create `.aitask-scripts/lib/python_resolve.sh`:
   - Shebang: `#!/usr/bin/env bash` (per CLAUDE.md shell convention)
   - `set -euo pipefail` is set by callers — lib files don't set it themselves; just rely on caller
   - Double-source guard:
     ```bash
     if [[ -n "${_AIT_PYTHON_RESOLVE_LOADED:-}" ]]; then return 0; fi
     _AIT_PYTHON_RESOLVE_LOADED=1
     ```
   - `resolve_python()` function:
     - If `_AIT_RESOLVED_PYTHON` is already set (cached), echo it and return.
     - Try in order: `$AIT_PYTHON` → `$HOME/.aitask/bin/python3` → `$HOME/.aitask/venv/bin/python` → `command -v python3`.
     - For each candidate, check `[[ -x "$cand" ]]` (or `command -v` for the system one). First hit wins.
     - Cache the result in `_AIT_RESOLVED_PYTHON` and echo it.
     - Echo empty if nothing found.
   - `require_python()` function:
     - Calls `resolve_python()`. If empty, calls `die "No Python interpreter found. Run 'ait setup' or install python3 system-wide."` (use `die` from `terminal_compat.sh`).
   - `require_modern_python <min_version>` function:
     - Argument: `<min_version>` like `3.11` (parse to major/minor).
     - Resolves Python via `require_python`. Then runs `"$python" -c "import sys; sys.exit(0 if sys.version_info >= (M, m) else 1)"`.
     - On version mismatch: `die "Python ≥<min_version> required (found <found_version> at <path>). Run 'ait setup' to install a newer interpreter."`.
   - Source `terminal_compat.sh` at top of the file (need `die`, `info`, `warn`):
     ```bash
     # shellcheck source=lib/terminal_compat.sh
     source "$(dirname "${BASH_SOURCE[0]}")/terminal_compat.sh"
     ```

2. Add a unit test at `tests/test_python_resolve.sh`:
   - Set up a scratch dir with stub `python3` / `python3.11` / `python3.13` shebang scripts (each prints its identifier).
   - Test 1: With `PATH=$scratch:$PATH` and `AIT_PYTHON` unset, `~/.aitask/` empty, verify `resolve_python` returns the system one.
   - Test 2: With `AIT_PYTHON=/path/to/stub`, verify it wins.
   - Test 3: Lay down a fake `~/.aitask/bin/python3` (in a `HOME=$scratch` override), verify it wins over system.
   - Test 4: Cache test — call `resolve_python` twice, verify second call doesn't re-search (e.g., remove the stub between calls, second still returns cached value).
   - Test 5: `require_modern_python 3.11` against a stub that reports 3.9 — verify it dies with the expected error.
   - Use existing `assert_eq` / `assert_contains` test helpers (search `tests/test_*.sh` for examples).
   - Print PASS/FAIL summary at the end.

## Verification Steps

- `bash tests/test_python_resolve.sh` exits 0 with all PASSes.
- `shellcheck .aitask-scripts/lib/python_resolve.sh` clean.
- Source the lib in an interactive shell and call `resolve_python` — verify it returns a sane path.
- Verify the double-source guard: `source lib/python_resolve.sh; source lib/python_resolve.sh; declare -f resolve_python` — function should exist and not be redefined.

## Notes for sibling tasks

- The `_AIT_RESOLVED_PYTHON` env var is the single cached resolution. Children t695_2/t695_3/t695_4 must not bypass this cache — they should always go through `resolve_python()`.
- The helper deliberately does NOT install Python — that's t695_2's job. t695_1 only resolves what's already on the system.
- t695_4 will source this helper and migrate all `${PYTHON:-python3}` patterns to use `$(resolve_python)`.
