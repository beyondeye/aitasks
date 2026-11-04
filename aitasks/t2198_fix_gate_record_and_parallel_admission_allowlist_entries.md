---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [framework, codeagent]
gates: [risk_evaluated]
anchor: 2175
followup_kind: upstream_defect
created_at: 2026-11-04 15:18
updated_at: 2026-11-04 15:18
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
