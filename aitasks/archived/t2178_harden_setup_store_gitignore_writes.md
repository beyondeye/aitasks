---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [install, ait_setup]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2173
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-01 09:16
updated_at: 2026-11-03 17:36
completed_at: 2026-11-03 17:36
---

## Origin

Spawned from t2177 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh` — `setup_gate_logs_gitignore`, `setup_testmap_gitignore`, `setup_shadow_store_gitignore`, `setup_scratchpad_gitignore` and `setup_worktree_dirs_gitignore` write `.gitignore` with unchecked `echo ... >> "$gitignore"` and test with `[[ -f ]]`. When `.gitignore` is read-only or a non-regular file, they either abort `ait setup` under `set -euo pipefail` or report "rule added" for a write that never happened. (`setup_python_cache_gitignore` and `setup_draft_directory` have the same shape and are worth checking too.)

## Diagnostic context

t2173_1 hardened only the discovery-cache rule (`setup_cache_gitignore`: checked writes, read-back, a three-way 0/1/2 result, never fatal, warns honestly). t2177 generalised that into `_ait_add_gitignore_rules <gitignore> <comment> <rule>...` (each rule guarded separately; only missing rules written under one comment; added names left in `_ait_gitignore_added`) plus `_ait_warn_gitignore_rules_failed <what> <rule>...`. It added the upgrade-path writer `upgrade_store_gitignore_rules` for the same five store/worktree groups. t2177 left the `setup_*` functions themselves unchanged on purpose and pinned agreement with test 27h in `tests/test_setup_git.sh`: setup's and upgrade's `.gitignore` must be byte-identical.

## Suggested fix

Rebuild each `setup_*` store helper on `_ait_add_gitignore_rules` (the `setup_cache_gitignore` shape: rc 1 → "already", rc 2 → shared warning and return 0, rc 0 → `_ait_commit_gitignore_rule`). Ideally share the rule/comment strings with `upgrade_store_gitignore_rules` so one table drives both routes. Keep 27h green. Add the 27f read-only/directory failure cases for each `setup_*` helper, and keep the 27a/27b dirty-baseline cases passing.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-03T09:48:34Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-03T15:32:03Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-03T15:36:10Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:0e8a3e302286c75f

> **✅ gate:risk_evaluated** run=2026-11-03T15:36:10Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2178/risk_evaluated_2026-11-03T15:36:10Z-risk_evaluated-a1.log`
