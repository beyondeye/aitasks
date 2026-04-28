---
Task: t677_use_aitask_venv_in_python_tests.md
Base branch: main
plan_verified: []
---

# t677 — Use aitask venv in Python-dependent tests

## Context

On any host where system `python3` lacks `yaml` (PyYAML), `textual`, or `rich` (the typical situation on macOS, but reproducible anywhere the system Python is bare), 11 tests in `tests/` fail with `ModuleNotFoundError`. The repo's `~/.aitask/venv/` has those packages installed, and `aitask_board.sh` already uses the canonical resolution pattern:

```bash
VENV_PYTHON="$HOME/.aitask/venv/bin/python"
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="${PYTHON:-python3}"
fi
```

(`.aitask-scripts/aitask_board.sh:8-14`)

`tests/test_crew_groups.sh:124-128` uses the same pattern at test scope. The 11 failing tests do not — they invoke bare `python3`, which on a host with a bare system Python misses the deps.

The task spec proposes Option 1: a shared helper `tests/lib/venv_python.sh` exposing `AITASK_PYTHON`, sourced by each affected test, with `python3` substituted at every call site. This is the chosen approach.

**One nuance discovered during exploration:** `tests/test_explain_context.sh` has **no direct `python3` calls**. It fails because `.aitask-scripts/aitask_explain_context.sh:245` (the production script under test) invokes bare `python3`. To make this test pass on the same hosts as the others, the production script also needs the venv-resolution pattern. This is a one-line, in-scope fix that mirrors `aitask_board.sh`.

## Approach

1. **New helper** — `tests/lib/venv_python.sh` exposing `AITASK_PYTHON` with a double-source guard.
2. **Test edits (10 files)** — source the helper near the top, then replace every `python3` literal with `"$AITASK_PYTHON"` (variable substitution works equally well for direct invocations, `-c "..."`, and `<<EOF` heredocs).
3. **Production-script edit (1 file)** — `.aitask-scripts/aitask_explain_context.sh` adopts the same venv-resolution pattern as `aitask_board.sh` so the test it backs (`tests/test_explain_context.sh`) passes without modifying the test itself.
4. **Verify** — run all 11 tests; each must report `ALL TESTS PASSED`.

## Files

### New file: `tests/lib/venv_python.sh`

```bash
#!/usr/bin/env bash
# Resolve the Python interpreter for tests that need yaml / textual / rich.
# Prefers the shared aitask venv at ~/.aitask/venv/bin/python (where ait setup
# installs the deps); falls back to system python3.

if [[ -z "${_AIT_VENV_PYTHON_LOADED:-}" ]]; then
    _AIT_VENV_PYTHON_LOADED=1

    AITASK_PYTHON="python3"
    if [[ -x "$HOME/.aitask/venv/bin/python" ]]; then
        AITASK_PYTHON="$HOME/.aitask/venv/bin/python"
    fi
fi
```

Match the existing convention in `.aitask-scripts/lib/terminal_compat.sh` and `task_utils.sh`: `_AIT_*_LOADED` guard, `#!/usr/bin/env bash` shebang.

### Test edits (10 files)

For each test below, near the top (after the existing `SCRIPT_DIR=...`-style block), add:

```bash
# shellcheck source=lib/venv_python.sh
. "$SCRIPT_DIR/lib/venv_python.sh"
```

If the test does not already define `SCRIPT_DIR`, define a local one before sourcing. Then substitute every literal `python3` invocation with `"$AITASK_PYTHON"` (preserving the rest of each call exactly — args, heredoc delimiters, env vars, etc.).

| Test file | Call sites | Pattern |
|-----------|-----------|---------|
| `tests/test_agentcrew_error_recovery.sh` | 2 inside helper functions (lines ~51, 55) | `python3 "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_status.py" "$@"` |
| `tests/test_agentcrew_terminal_push.sh` | 1 inside helper function (line ~50) | same as above |
| `tests/test_apply_initializer_output.sh` | 1 (line ~55) | `python3 - <<EOF_PY` |
| `tests/test_apply_initializer_tolerant.sh` | 2 (lines ~62, ~198) | `python3 - <<EOF_PY` and `python3 - <<'EOF_PY'` |
| `tests/test_explain_format_context.sh` | 3+ (lines ~152, 206, 212) | `python3 "$SCRIPT" "$@"` and direct invocations |
| `tests/test_install_merge.sh` | ~10 (lines 69, 91, 99, 107, 119, 132, 145, 152, 158, 165) | `python3 "$MERGE_SCRIPT" ...` |
| `tests/test_multi_session_minimonitor.sh` | ~6 (lines 44, 65, 105, 142, 163, 230) | `python3 <<'PY'` heredocs, often with `PYTHONPATH=...` env |
| `tests/test_multi_session_monitor.sh` | ~17 (lines 63, 79, 137, 171, 221, 268, 311, 356, 397, 450, 492, 512, 539, 563, 593, 659, 704) | mix of `python3 -c "..."` and `python3 <<'PY'` |
| `tests/test_stats_verified_rankings.sh` | 5 (lines 27, 55, 71, 110, 134) | `python3 - <<'PY'` |
| `tests/test_tui_switcher_multi_session.sh` | 2+ (lines 52, 419) | heredoc + `python3 -c "..."` |

**Substitution mechanics:** `python3 - <<'PY'` becomes `"$AITASK_PYTHON" - <<'PY'`; `python3 -c "..."` becomes `"$AITASK_PYTHON" -c "..."`; `python3 "$SCRIPT" args` becomes `"$AITASK_PYTHON" "$SCRIPT" args`. Variable expansion inside heredocs is unaffected — the `python3` substitution is on the command line, not inside the heredoc body. Where the line starts with an env-var prefix like `PYTHONPATH=... python3 ...`, the prefix stays put: `PYTHONPATH=... "$AITASK_PYTHON" ...`.

**Use the actual line numbers from each file** — the table above is from a coarse scan and is approximate. During implementation, grep each file for `python3` and substitute every match.

### Production-script edit (1 file)

`.aitask-scripts/aitask_explain_context.sh` — the test `tests/test_explain_context.sh` does not invoke `python3` itself; it calls this script, which currently has at line 245:

```bash
python3 "$FORMAT_SCRIPT" \
```

Add a venv-resolution block near the top of `main()` (or globally, near the existing `SCRIPT_DIR` block — pick whichever matches the script's existing structure), modeled on `aitask_board.sh:8-14`:

```bash
VENV_PYTHON="$HOME/.aitask/venv/bin/python"
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="python3"
fi
```

Then change line 245 from `python3 "$FORMAT_SCRIPT" \` to `"$PYTHON" "$FORMAT_SCRIPT" \`.

This is a minimal, in-place change that mirrors the existing convention in `aitask_board.sh`. It does NOT add the package-availability check that `aitask_board.sh` does — that's out of scope; the production script already crashes if deps are missing, and this task only needs to prefer the venv when present.

## Verification

After implementation, on this host (which has `~/.aitask/venv/bin/python` populated):

```bash
bash tests/test_agentcrew_error_recovery.sh
bash tests/test_agentcrew_terminal_push.sh
bash tests/test_apply_initializer_output.sh
bash tests/test_apply_initializer_tolerant.sh
bash tests/test_explain_context.sh
bash tests/test_explain_format_context.sh
bash tests/test_install_merge.sh
bash tests/test_multi_session_minimonitor.sh
bash tests/test_multi_session_monitor.sh
bash tests/test_stats_verified_rankings.sh
bash tests/test_tui_switcher_multi_session.sh
```

Each must end with `ALL TESTS PASSED` and exit 0.

Lint:
```bash
shellcheck tests/lib/venv_python.sh
shellcheck .aitask-scripts/aitask_explain_context.sh
```

**Fallback / graceful-degradation note:** The task spec accepts either pass or skip on hosts without venv. This plan does NOT add a `require_python_modules`-style skip helper — it only adds the venv-preference resolver. On a host where venv is absent and system `python3` lacks deps, tests will fail loudly the same way they do now (`ModuleNotFoundError`). That is acceptable per the spec; if a clean skip path becomes desirable later, a `require_python_modules` function can be added to the same helper file in a follow-up task.

## Reference for Step 9 (Post-Implementation)

Standard archival via `./.aitask-scripts/aitask_archive.sh 677`. No worktree to clean up (profile `fast` set `create_worktree: false`). Single commit covering the helper, the 10 test edits, and the one production-script edit, using `chore:` issue type from the task frontmatter:

```
chore: Use aitask venv Python in 11 dependency-using tests (t677)
```

## Final Implementation Notes

- **Actual work done:** Created `tests/lib/venv_python.sh` (new file, 14 lines) exposing `AITASK_PYTHON` with the standard `_AIT_*_LOADED` double-source guard; added a one-line file-level `# shellcheck disable=SC2034` directive so shellcheck doesn't flag the variable as unused (it's consumed by sourcing scripts). Sourced the helper near the top of all 10 tests with direct `python3` invocations and substituted every literal `python3` → `"$AITASK_PYTHON"` (preserving heredoc delimiters, env-var prefixes, and arg ordering at every call site). For `tests/test_explain_context.sh` (no direct `python3` calls — failure was in the underlying production script), modified `.aitask-scripts/aitask_explain_context.sh` to add a 6-line venv-resolution block near the top and changed line 251 from `python3 "$FORMAT_SCRIPT"` to `"$PYTHON" "$FORMAT_SCRIPT"`.
- **Deviations from plan:** None. The plan's "use actual line numbers" caveat applied — confirmed during edits — and one Python string literal `"python3"` in `tests/test_multi_session_monitor.sh:325` was correctly NOT touched (it's test data describing a process command name, not a command invocation).
- **Issues encountered:** Initial shellcheck of the helper flagged SC2034 (`AITASK_PYTHON` appears unused). A line-scoped `# shellcheck disable=SC2034` only suppresses the immediate next assignment; the second assignment inside the `if` re-triggered it. Resolved by promoting the directive to file-level (placed before the guard `if`).
- **Key decisions:** (1) Helper exposes `AITASK_PYTHON` only — no `require_python_modules` skip helper, since the task spec accepts loud `ModuleNotFoundError` on hosts without venv. (2) The production-script change in `aitask_explain_context.sh` mirrors the simpler form (no missing-package check) rather than the full `aitask_board.sh` form — the missing-package check is out of scope. (3) For test files where the source line follows existing `SCRIPT_DIR=...`/`PROJECT_DIR=...` blocks, inserted the `. "$SCRIPT_DIR/lib/venv_python.sh"` line immediately after that block before the first `PASS=0` so each test's setup-vs-runtime structure is preserved.
- **Upstream defects identified:** None.

### Verification results

All 11 tests pass on this host (Linux, `~/.aitask/venv/bin/python` present with yaml/textual/rich):

| Test | Result |
|------|--------|
| test_agentcrew_error_recovery.sh | 5/5 PASS |
| test_agentcrew_terminal_push.sh | 6/6 PASS |
| test_apply_initializer_output.sh | 8/8 PASS |
| test_apply_initializer_tolerant.sh | 15/15 PASS |
| test_explain_context.sh | 29/29 PASS |
| test_explain_format_context.sh | 30/30 PASS |
| test_install_merge.sh | 20/20 PASS |
| test_multi_session_minimonitor.sh | 24/24 PASS |
| test_multi_session_monitor.sh | 43/43 PASS |
| test_stats_verified_rankings.sh | 5/5 PASS |
| test_tui_switcher_multi_session.sh | 45/45 PASS |

Lint:
- `shellcheck tests/lib/venv_python.sh`: clean.
- `shellcheck -x .aitask-scripts/aitask_explain_context.sh`: only the pre-existing info-level SC1091 for `lib/task_utils.sh` (untouched by this task).
