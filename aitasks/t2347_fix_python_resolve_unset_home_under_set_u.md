---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [brainstorm]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2278
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-22 11:49
updated_at: 2026-11-22 18:27
---

## Origin

Spawned from t2339 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/python_resolve.sh:38 — top-level `$HOME` expansion (PYPY_VENV_DIR default) aborts any `set -u` script that sources it at startup when HOME is unset (the t2339 bridges now guard it; direct sourcers still crash)`

## Diagnostic context

t2339 made the Python shell bridges (`lib/launch_modes_sh.sh`,
`lib/followup_kinds_sh.sh`, `lib/plan_paths_sh.sh`) resolve their interpreter
through `lib/python_resolve.sh`. Review reproduced a regression:
`env -i PATH=/usr/bin:/bin AIT_PYTHON=/usr/bin/python3 bash
.aitask-scripts/aitask_crew_init.sh --help` went from exit 0 to exit 1 with

    .aitask-scripts/lib/python_resolve.sh: line 38: HOME: unbound variable

Line 38 is `PYPY_VENV_DIR="${PYPY_VENV_DIR:-$HOME/.aitask/pypy_venv}"`, which is
evaluated at source time; `resolve_python()` also expands `$HOME` for its venv
and wrapper candidates. t2339 worked around it inside the bridges only: they
honour an executable `$AIT_PYTHON` first and source `python_resolve.sh` only
when HOME is set (`tests/test_shell_bridge_python_resolve.sh`, "HOME unset"
section). Every other script that sources `python_resolve.sh` at startup under
`set -euo pipefail` still aborts when HOME is unset (cron / systemd / `env -i`
contexts), even with `AIT_PYTHON` pointing at a working interpreter.

## Suggested fix

Use `${HOME:-}` for the top-level default and skip the HOME-based candidates in
`resolve_python()` when HOME is empty, so `$AIT_PYTHON` and `command -v
python3` still resolve. Cover it with an `env -i` (no HOME) case that sources
`python_resolve.sh` under `set -u` and calls `resolve_python`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-22T16:27:08Z status=pass attempt=1 type=human
