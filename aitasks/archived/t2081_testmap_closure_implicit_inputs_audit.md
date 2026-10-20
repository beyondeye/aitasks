---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [2082]
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-10-20 12:35
updated_at: 2026-10-20 15:24
completed_at: 2026-10-20 15:24
---

## Origin
Risk-mitigation ("after") follow-up for t1854_4, created at Step 8d after implementation landed.

## Risk addressed
goal-achievement — implicit runner inputs missing from the eligibility closure.

- Anchor eligibility can only be as sound as M2.3's closure. Implicit runner inputs that no scanner models (pytest `conftest.py` ancestors, Gradle build files, Go package siblings outside the facts) are not in the disjointness set, so a dirty one can still anchor. This sits alongside the stated edit-and-revert residual. · severity: medium · → mitigation: testmap_closure_implicit_inputs_audit
- D12's unresolved-ref rule may make dirty-tree anchors rare, which means fewer `EVIDENCED` rows and less self-healing (the fail-safe direction, but it erodes the feature's value). · severity: medium (residual — quantified by the inline post-phase; any remedy is fed to this audit task)

## Goal
Audit, per reference runner (pytest, go-test, gradle-class, bash-file), the implicit inputs a run reads that M2.3's test-side closure does not model. Examples: `conftest.py` ancestors and `pytest.ini`/`pyproject.toml` for pytest; `go.mod`, `go.sum` and same-package siblings for go-test; Gradle build files and version catalogs for gradle-class. Add them to M3.4's anchor-eligibility disjointness set (`goengines/internal/testmap/cost/eligibility.go`), or mark the unit opaque, each with a red-proved fixture test asserting the exact `anchor_reason`.

Measured input from t1854_4 (2026-10-20, this repo):
- **89 % of bash tests are opaque:** 400 / 448 have an unresolved `source`/`exec` ref in {test} ∪ closure, mostly fixture paths created at test time (`aitasks/t10_alpha.md`, `.codex/`, `.opencode/skills/...`). Under the strict D12 rule, dirty-tree anchors are therefore effectively disabled on this repo.
- **Hook cost:** the eligibility inputs cost ≈ 0.9 s cold / 0.27 s warm, on dirty trees only.

**Required before relaxing D12 (user decision in t1854_4):** a narrowing to "unresolved refs matter only when a modified path is outside the scan universe" was rejected as unproven. Counterexample: an **unchanged excluded helper**, reached through an unresolved ref, can itself read a **modified file inside the scan universe**. Add exactly that case as a red test, and keep it failing-closed, before proposing any relaxation of the unresolved-ref rule (e.g. classifying runtime-created fixture refs).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-20T11:33:24Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-20T12:20:22Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-20T12:24:06Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:e8a79b4d2c3adfff

> **✅ gate:risk_evaluated** run=2026-10-20T12:24:06Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2081/risk_evaluated_2026-10-20T12:24:06Z-risk_evaluated-a1.log`
