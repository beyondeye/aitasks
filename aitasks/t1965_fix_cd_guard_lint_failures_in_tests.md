---
priority: medium
effort: low
depends: []
issue_type: test
status: Implementing
labels: [tests, test_infrastructure]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1711
followup_kind: upstream_defect
created_at: 2026-10-13 08:33
updated_at: 2026-10-13 08:47
---

## Origin

Spawned from t1959 during Step 8b review (first listed in t1959's body from t1711. The set has grown since then).

## Upstream defect

`bash tests/test_cd_guard_lint.sh` fails on main (90 passed, 2 failed as of 2026-10-13), independent of t1711/t1959:

- `unconfined-andchain` cd sites:
  - `tests/test_aitasks_home.sh:319`
  - `tests/test_install_engine_binary.sh:224`
  - `tests/test_setup_hooks_only.sh:74`
  - `tests/test_upgrade_prunes_retired_scripts.sh:73`
- No `enter_scratch_cwd` call before the first cd:
  - `tests/test_add_model.sh` (first cd at line 134; last touched by t1940)
  - `tests/test_list_panes_session_scope_live.sh` (line 211)
  - `tests/test_opencode_models_merge.sh` (line 52)
  - `tests/test_opencode_models_reserved.sh` (line 45)
  - `tests/test_setup_hooks_only.sh` (line 74)

Line numbers are as of commit c6fbbaf85. Re-run the lint for the current list, because other in-flight work keeps adding tests.

## Diagnostic context

Found while running the setup suites for t1711 and again for t1959. The files involved were not touched by either task. The scanner is `tests/lib/cd_guard_scan.py`. t1832 (live-tree leak tripwire) is related but does not own these sites.

## Suggested fix

Per `aidocs/framework/testing_conventions.md`: add `. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"; enter_scratch_cwd` at the top of each file missing it, and confine each `cd X && …` chain in a `( … )` subshell (or use `git -C` / `ls -A <dir>` with no cd at all). Re-run `bash tests/test_cd_guard_lint.sh` and each touched test file.
