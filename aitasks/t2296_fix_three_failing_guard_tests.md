---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [codex, workflow]
gates: [risk_evaluated]
anchor: 2281
followup_kind: upstream_defect
created_at: 2026-11-13 14:16
updated_at: 2026-11-13 14:16
---

## Origin

Spawned from t2281 during Step 8b review.

## Upstream defect

- `tests/test_workflow_phase_standalone.sh:155-157` — the guard expects two `agent_key_from_command(shadow_command)` call sites in `.aitask-scripts/monitor/minimonitor_app.py`; there are none (`grep -c` gives 0), so "two documented shadow-side sites" fails (11/12).
- `tests/test_codex_no_plan_injection.sh` — fails on "dangling references to the removed plan-mode machinery": `.aitask-scripts/retired_scripts_manifest.txt:58` (`aitask_codex_plan_invoke.py`) and `:73` (`lib/codex_plan_policy.sh`) list the removed files the test forbids references to.
- `tests/test_issue_update_ledger.sh:231` — an unconfined `( cd "$REPO" && … \` chain is reported by `tests/lib/cd_guard_scan.py` as `unconfined-andchain`, so `tests/test_cd_guard_lint.sh` fails (91/92).

## Diagnostic context

All three were observed failing on 2026-11-13 on `main` at `530a62f96`, while closing t2281. None of the files involved was changed by t2281. t2281's own new test file had a missing `enter_scratch_cwd` call that the same lint caught; that was fixed inside t2281, which is how the remaining lint failure was isolated to `test_issue_update_ledger.sh`.

## Suggested fix

For each test, decide whether the test or the code is stale: the shadow-side call sites may have been renamed or removed on purpose (update the count and comment), the retired-scripts manifest is probably a legitimate place to name removed files (exempt it in the test), and the `cd` chain needs the guarded form from `aidocs/framework/testing_conventions.md`.
