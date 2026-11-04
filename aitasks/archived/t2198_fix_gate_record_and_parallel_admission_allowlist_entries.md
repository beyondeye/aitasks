---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [framework, codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-04 15:18
updated_at: 2026-11-04 23:23
completed_at: 2026-11-04 23:23
---

## Origin

Spawned from t2175_4 during Step 8b review.

## Upstream defect

- `.claude/settings.local.json:40` — `aitask_gate_record.sh` (invoked by task-workflow `gate-recording.md`) has no allow entry in the repo's own Claude settings. The other four touchpoints have it (`.codex/rules/default.rules:34`, `seed/claude_settings.local.json:98`, `seed/codex_rules.default.rules:33`, `seed/opencode_config.seed.json:90`).
- `seed/opencode_config.seed.json:33` — the `aitask_parallel_admission` allow entries in all five touchpoints name the stem WITHOUT `.sh` (`Bash(./.aitask-scripts/aitask_parallel_admission:*)`, `prefix_rule(pattern = ["./.aitask-scripts/aitask_parallel_admission"], …)`, `"./.aitask-scripts/aitask_parallel_admission *"`), while task-workflow `parallel-admission.md` runs `./.aitask-scripts/aitask_parallel_admission.sh`. Under opencode's `<cmd> *` glob and codex's token-wise `prefix_rule` these entries likely never match; Claude's `:*` prefix may. **Unverified per agent** — check each agent's matching rule before changing anything (the stem form was introduced in 2384e4a64, t1569_4, possibly deliberately to cover sibling helpers).

## Diagnostic context

While adding the sitrep helpers' permission entries (t2175_4), `./.aitask-scripts/aitask_audit_wrappers.sh discover-helpers` + `audit-helper-whitelist <helper>` over every skill-referenced helper reported `MISSING:1:aitask_gate_record.sh` and `MISSING:{1,3,4,6,7}:aitask_parallel_admission.sh`. Reading the five files showed the first is a real single-file gap and the second is a stem-vs-`.sh` mismatch the audit's fixed-string check reports as missing.

## Suggested fix

Add `"Bash(./.aitask-scripts/aitask_gate_record.sh:*)",` to `.claude/settings.local.json`. For parallel admission: determine per agent whether the stem entry matches `aitask_parallel_admission.sh`; where it does not, add (or replace with) the exact `.sh` entry in all five touchpoints so `audit-helper-whitelist` reports clean. Consider a test that every helper `discover-helpers` reports is allow-listed in all five files.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-04T14:05:35Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-04T21:18:30Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-04T21:23:42Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:96e5baef64a8a2c7

> **✅ gate:risk_evaluated** run=2026-11-04T21:23:42Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2198/risk_evaluated_2026-11-04T21:23:42Z-risk_evaluated-a1.log`
