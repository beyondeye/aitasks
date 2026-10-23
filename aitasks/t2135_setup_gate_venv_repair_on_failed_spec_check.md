---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [setup, python_deps]
gates: [risk_evaluated]
anchor: 2133
followup_kind: upstream_defect
created_at: 2026-10-23 12:22
updated_at: 2026-10-23 12:22
---

## Origin
Spawned from t2133 during Step 8b review.

## Upstream defect
- .aitask-scripts/aitask_setup.sh:setup_python_venv / setup_pypy_venv — the "need repair" checks gate only on `missing_imports`/`bad_specs` and ignore the new `specs_check_ok`, so if the version inspection itself fails while imports succeed (e.g. no importable packaging), setup treats spec ranges as satisfied

## Diagnostic context
t2133 pinned `rich>=14.3.3` and found that `verify_venv_specs` did
`out="$(…)" || out=""`: a failed inspection (broken interpreter, unimportable
`packaging`) produced an empty `bad_specs`, indistinguishable from "all in
range" (confirmed with `/bin/false` as the interpreter). t2133 added the global
`specs_check_ok` (false when the inspection command fails) and made the new
read-only `report_venv_dep_drift` (the `ait upgrade` hint) report a failed check
instead of staying silent. It deliberately did NOT change the setup call sites:

- `setup_python_venv`: `[[ ${#missing_imports[@]} -gt 0 || ${#bad_specs[@]} -gt 0 ]]`
  decides retry/die — a failed spec check with good imports passes.
- `setup_pypy_venv`: same condition decides retry/remove-venv.
- Opt-in tiers (`--with-chat`, `--with-dev`) use the same pattern.

A broken interpreter is already caught by `verify_venv_imports`, so the gap is
narrow: imports succeed but the spec inspection fails, e.g. neither
`packaging` nor `pip._vendor.packaging` importable. In that case a raised floor
(like rich>=14.3.3) would not be enforced and setup reports success.

## Suggested fix
Include `specs_check_ok != true` in each "need repair" condition (and in the
final failure condition / message), naming "version check failed" in the warn
and die text. Extend `tests/test_setup_pip_install_guards.sh` with a
behavioural case whose stub passes imports but fails the `python -` inspection.
