---
priority: low
effort: low
depends: []
issue_type: test
status: Ready
labels: [test, setup, codeagent]
anchor: 1705
followup_kind: qa_test_gap
created_at: 2026-09-18 15:47
updated_at: 2026-09-18 15:47
---

## Problem

`tests/test_session_hook_install.sh` Group D ("the codex [hooks] block round-trips through the TOML merge") asserts by shelling out to bare `python3 -c "import tomllib, ..."` (lines ~228-253). `tomllib` is stdlib only from Python 3.11. On a machine whose `python3` is the macOS system interpreter (3.9.6 here) all five Group D assertions fail with `ModuleNotFoundError: No module named 'tomllib'` and the file reports `34 passed, 5 failed` — a false red.

Found during t1705_11's auto-verification pass (2026-09-18). Re-running with the framework venv first on `PATH` (`PATH=~/.aitask/venv/bin:$PATH bash tests/test_session_hook_install.sh`) gives `39 passed, 0 failed`, so the product merge is fine: `merge_codex_settings()` in `aitask_setup.sh` already prefers `$VENV_DIR/bin/python` and only falls back to `python3`.

## Fix

Make the test's TOML assertions use the same interpreter the product uses — resolve `$VENV_DIR/bin/python` (or `~/.aitask/venv/bin/python`) first and fall back to `python3`, mirroring `merge_codex_settings()`; or fall back to `tomli` when `tomllib` is missing and SKIP Group D with a clear message when neither is importable. Check the other bare `python3` call sites in the same file (lines ~47, 63, 91, 173, 189) for the same hazard — they passed here only because they do not import 3.11-only modules.

## Verification

- `bash tests/test_session_hook_install.sh` from a shell where `python3` is 3.9: Group D passes (or skips loudly), no `tomllib` traceback.
- Same file with the venv on PATH: still 39/39.
