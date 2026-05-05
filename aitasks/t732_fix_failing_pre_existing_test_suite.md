---
priority: medium
effort: high
depends: []
issue_type: bug
status: Ready
labels: [testing, qa, bash_scripts]
children_to_implement: [t732_7]
created_at: 2026-05-03 12:37
updated_at: 2026-05-05 08:48
boardcol: now
boardidx: 20
---

## Origin

Surfaced during t623_1 regression testing (2026-05-03). When running every shell test under `tests/`, **14 of 112 fail on `main` (commit `d627c0f5`) on a clean Linux/CPython 3.14.3 environment**. None of the failures relate to t623_1's changes (verified via `grep -l "install_global_shim\|SHIM_DIR\|packaging/shim\|release.yml" tests/test_*.sh` against all failing tests — zero matches).

Driver script:
```bash
PASS_T=0; FAIL_T=0; FAILED_TESTS=()
for t in tests/test_*.sh; do
  if bash "$t" >/dev/null 2>&1; then
    PASS_T=$((PASS_T + 1))
  else
    FAIL_T=$((FAIL_T + 1))
    FAILED_TESTS+=("$t")
  fi
done
```

## Failing tests, grouped by likely root cause

The 14 failures cluster into a few independent root causes. Each cluster should ultimately become its own child task once an owner triages.

### Cluster A — Textual / Python 3.14 API drift (TUI tests)

- **`tests/test_multi_session_minimonitor.sh`** — `AttributeError: 'MiniMonitorApp' object has no attribute '_thread_id'. Did you mean: '_thread_init'?` from `textual/dom.py:525` (`run_worker`). Plus `RuntimeWarning: coroutine 'MiniMonitorApp._start_monitoring.<locals>._connect_control_client' was never awaited`. Likely Textual API drift between versions, or an unmounted-app race.
- **`tests/test_tui_switcher_multi_session.sh`** — `textual.css.query.NoMatches: No nodes match '#switcher_desync' on TuiSwitcherOverlay()` from `lib/tui_switcher.py:483` (`_render_desync_line`). The `#switcher_desync` Label query fires before mount in `_cycle_session` → `_render_desync_line`. Add a mount-guard or `query` (zero-or-more) instead of `query_one`.

### Cluster B — Python interpreter resolver portability

- **`tests/test_python_resolve.sh`** — `Error: Python >=3.11 required (found 3.13.0 at /tmp/test_python_resolve.RXK97p/bin/python3). Run 'ait setup' to install a newer interpreter.` 3.13.0 IS ≥ 3.11 — the comparison logic in `python_resolve.sh` rejects it. Possibly a string-compare bug ("3.11" < "3.13" lexically vs numerically), or the test scaffolds a fake `python3` that doesn't satisfy the version probe.
- **`tests/test_python_resolve_pypy.sh`** — `Error: PyPy not found. Run 'ait setup --with-pypy' to install it.` Test environment missing PyPy. Either the test must skip when PyPy is absent (clean handling) or the harness must install PyPy as a setup step.

### Cluster C — Branch-mode / data-worktree integration

- **`tests/test_init_data.sh`** — `7 passed / 23 failed / 30 total`. Notable failures: `Missing symlinks output (expected 'ALREADY_INIT', got 'NO_DATA_BRANCH')`, `aitasks/ symlink recreated ('aitasks' is not a symlink)`, `aiplans/ symlink recreated ('aiplans' is not a symlink)`. Init-data flow regression — symlinks not recreated under expected conditions.
- **`tests/test_t644_branch_mode_upgrade.sh`** — `8 passed / 8 failed / 16 total`. Branch-mode upgrade workflow regressions; failure context shows mismatched commit messages.
- **`tests/test_task_push.sh`** — `13 passed / 5 failed / 18 total`. Multiple `./ait git`-related failures. Critical clue: `./ait: line 7: /tmp/ait_push_test_G0gI6p/local/.aitask-scripts/lib/aitask_path.sh: No such file or directory`. The test harness sets up a fake repo missing `lib/aitask_path.sh`, which `./ait` line 7 sources unconditionally — the dispatcher cannot run. Either the test scaffolding must create that file, or `./ait` must tolerate its absence in early-init scenarios.
- **`tests/test_t167_integration.sh`** — `14 passed / 3 failed / 17 total`. Failures: `D1: Upgrade run reports a commit (expected output containing 'committed to git')`, `D2: Upgrade commit message references new version (expected output containing 'v99.0.0-t167test')`. Upgrade flow no longer surfaces commit info as expected.

### Cluster D — External-tool / agent metadata drift

- **`tests/test_codex_model_detect.sh`** — `Total runs: 24 / MATCH: 0 / PARTIAL: 3 / MISMATCH: 5 / ERROR: 16`. Codex CLI model-name detection has drifted; either Codex changed its model output format, or `models_codex.json` is out of date. Root cause needs investigation against the current Codex CLI version.
- **`tests/test_gemini_setup.sh`** — Test 8 fails with `/tmp/.../bin/python: No such file or directory`. The test harness builds a venv at a temp path but the merge helper invokes a python that does not exist. Suggests setup ordering issue or an absolute-path bake-in.

### Cluster E — Smaller / single-symptom failures

- **`tests/test_brainstorm_cli.sh`** — Exits silently after `Test 1: brainstorm init basic`. No `FAIL:` line, just early termination — likely an unhandled `set -e` exit. Re-run with `bash -x` to find the exact line.
- **`tests/test_contribute.sh`** — `122 passed / 1 failed / 123 tests`. Single failure (location not surfaced in the truncated output). Run with verbose to identify.
- **`tests/test_explain_context.sh`** — Exits silently with no `FAIL:` line. Same pattern as brainstorm_cli — unhandled `set -e` early termination.
- **`tests/test_migrate_archives.sh`** — Exits silently after `Test 11: Dispatcher path`. Same pattern. Likely the dispatcher path test invokes something that bails.

## Suggested approach

This task is a **triage parent**. The clusters above are independent and have different owners / root causes. Recommended split (during planning):

1. **Child A** — Textual/Python 3.14 TUI API drift (covers `test_multi_session_minimonitor` + `test_tui_switcher_multi_session`).
2. **Child B** — `python_resolve.sh` portability (covers `test_python_resolve` + skip-when-PyPy-absent for `test_python_resolve_pypy`).
3. **Child C** — Branch-mode regressions (covers `test_init_data`, `test_t644_branch_mode_upgrade`, `test_task_push`, `test_t167_integration`).
4. **Child D** — External-tool drift (covers `test_codex_model_detect` model registry refresh + `test_gemini_setup` venv-path fix).
5. **Child E** — Silent-exit quartet (covers `test_brainstorm_cli`, `test_explain_context`, `test_migrate_archives`, `test_contribute` 1-of-123). Each likely a tiny fix once located via `bash -x`.

Children C and D may themselves split further — that's a planning-phase decision. CLuster A is the highest-priority cluster because TUI regressions affect daily user experience.

## Verification

For each child:
1. Reproduce the failure with `bash <test>` on `main`.
2. Identify root cause (often the test has shifted, not just the code; both directions need to be checked).
3. Land the fix.
4. `bash <test>` passes.
5. Add a regression note in CLAUDE.md only if the failure mode is a recurring portability gotcha.

Whole-task verification:
- `for t in tests/test_*.sh; do bash "$t" >/dev/null 2>&1 || echo "FAIL: $t"; done` reports 0 failures (or, if some failures are out of scope, only those documented as out-of-scope in this task's plan).

## Out of scope

- Adding a CI workflow that runs the full test suite (separate task — depends on this one passing).
- Rewriting tests that are structurally fragile (separate task; gather candidates after fixing the present 14).
