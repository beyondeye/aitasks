---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing, python]
created_at: 2026-06-03 23:15
updated_at: 2026-06-03 23:15
---

Surfaced by the t926 periodic macOS compat audit (test suite run on macOS,
Darwin arm64). Not macOS-specific — reproduces anywhere the system `python3`
lacks the framework deps.

## Problem

Several bash tests shell out to Python via **bare `python3`** (the system
interpreter on `PATH`) instead of the framework's canonical resolver
`resolve_python` (in `.aitask-scripts/lib/python_resolve.sh`, which prefers
`$HOME/.aitask/venv/bin/python`). On a machine whose system `python3` does not
have `yaml` / `textual` / `rich` installed (the normal case — those deps live in
the aitask venv), these tests fail with `ModuleNotFoundError: No module named
'yaml'` / `'textual'`.

## Failing tests observed in t926 (162 PASS / 10 FAIL; these 2 + downstream)

- `tests/run_all_python_tests.sh` — lines ~15-19 invoke `python3 -m pytest` /
  `python3 -m unittest`. Result: `Ran 210 tests ... FAILED (failures=9,
  errors=59)`, where the 59 errors are all `No module named 'yaml'/'textual'`
  import failures and the 9 failures cascade from those import failures
  (e.g. `test_shortcut_scopes` cannot load board/tui modules).
- `tests/test_crew_report.sh` — lines 117/134/148/166/188 run
  `python3 .aitask-scripts/agentcrew/agentcrew_report.py ...`; dies under
  `set -e` at Test 1 with `ModuleNotFoundError: No module named 'yaml'`.

Verified the venv DOES exist and DOES have the deps:
`~/.aitask/venv/bin/python -c "import yaml, textual"` → OK. The tests simply
don't use it.

## Suggested fix

Source `.aitask-scripts/lib/python_resolve.sh` and use
`PY="$(resolve_python)"` (or `require_python`) in these test harnesses instead
of bare `python3`. Sweep the rest of `tests/` for the same bare-`python3`
pattern in the same pass (`grep -n 'python3' tests/*.sh`). This is the t695_2
canonical-venv resolution path; see `python_resolve.sh` header.

## Verification

After fix, on a machine where system `python3` lacks `yaml`/`textual`:
`bash tests/run_all_python_tests.sh` and `bash tests/test_crew_report.sh` both
pass (they pick up the venv interpreter).
