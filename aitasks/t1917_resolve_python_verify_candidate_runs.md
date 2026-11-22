---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [install_scripts]
gates: [risk_evaluated]
anchor: 1910
followup_kind: upstream_defect
created_at: 2026-10-08 17:00
updated_at: 2026-10-08 17:00
---

## Origin
Spawned from t1910 during Step 8b review.

## Upstream defect
- `.aitask-scripts/lib/python_resolve.sh:60-76 — resolve_python accepts any candidate that passes -x without running it, so a ~/.aitask/bin/python3 wrapper whose venv is gone (or an unrunnable python3 on PATH) "resolves" and every caller fails at exec time instead of falling through to the next candidate`

## Diagnostic context
t1910 added `check_superseded_model_defaults()` to `install.sh`, which resolves its interpreter with `resolve_python` (sourced from `aitask_setup.sh --source-only`). The full-install test (`tests/test_install_superseded_models.sh`) ran `install.sh` with an isolated `HOME` while the real `~/.aitask/bin` stayed on `PATH`. `resolve_python` skipped `$HOME/.aitask/venv/bin/python` and `$HOME/.aitask/bin/python3` (absent under the fake HOME), then returned `command -v python3` = the real `~/.aitask/bin/python3` wrapper — which execs `$HOME/.aitask/venv/bin/python`, nonexistent under that HOME. The helper died with exit 127 (`No such file or directory`). The installer handled it (warned and continued), and the test now strips `~/.aitask/bin` from `PATH`, but the resolver itself reported a broken interpreter as resolved.

Real-world shape: a user removes `~/.aitask/venv` (or it is half-deleted) while the `~/.aitask/bin/python3` wrapper remains — every `resolve_python` / `require_ait_python` caller then gets an interpreter that cannot start, and `require_modern_python` reports a misleading version error or the caller fails at exec. Note that `install.sh::report_claude_session_hook` already detects "python3 on your PATH ... does not run" through a different code path, so the framework knows wrappers can be broken.

## Suggested fix
In `resolve_python`, accept a candidate only if it actually runs (e.g. `"$cand" -c 'import sys' >/dev/null 2>&1`), falling through to the next candidate otherwise; keep the result cached in `_AIT_RESOLVED_PYTHON` so the probe costs one exec per shell. Add a test with a wrapper whose target is missing.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2347** id=2026-11-22T17:07:54Z.f3627a23ac5b4a08d1d745a3 from=t2347 from_verified=yes at=2026-11-22T17:07:54Z base=34009f16337e675aff7c1972ae5403e76da34ff7 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t2347 (commit 34009f163), which changed lib/python_resolve.sh:
> | 
> | 1. Stale line range. Your body cites `.aitask-scripts/lib/python_resolve.sh:60-76`
> |    for resolve_python. As of 34009f163 the function is at lines 61-87, shifted by
> |    a header note and a PYPY_VENV_DIR comment.
> | 
> | 2. Empty candidates need to stay skipped before any run-probe. The two HOME-based
> |    candidates are now `"${HOME:+$HOME/.aitask/venv/bin/python}"` and
> |    `"${HOME:+$HOME/.aitask/bin/python3}"`, which are empty when HOME is unset or
> |    empty (cron/systemd/env -i under `set -u`). The existing `[[ -n "$cand" && -x
> |    "$cand" ]]` check skips them. A `"$cand" -c 'import sys'` probe added there
> |    should keep that empty check first. The same holds in resolve_pypy_python,
> |    whose venv candidate is now `"${PYPY_VENV_DIR:+$PYPY_VENV_DIR/bin/python}"`.
> |    tests/test_python_resolve_unset_home.sh pins the no-HOME behaviour: AIT_PYTHON
> |    wins, the PATH python3 fallback resolves, nothing root-level is tried.
> | 
> | 3. Related: the ~/.aitask/bin/python3 wrapper (`exec "$HOME/.aitask/venv/bin/python"`)
> |    is exactly the "passes -x but does not run" case your task targets, and it also
> |    breaks whenever HOME differs from the one it was installed under. The new test
> |    avoids it by reducing resolve_python's answer to sys.executable in the parent
> |    shell.
> | 
> | This is a claim about the tree at 34009f163, not an instruction.
