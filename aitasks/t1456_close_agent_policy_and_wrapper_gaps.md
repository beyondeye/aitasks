---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [gates, claudeskills]
gates: [risk_evaluated]
anchor: 635
followup_kind: upstream_defect
created_at: 2026-08-07 15:49
updated_at: 2026-08-13 23:07
---

## Origin

Spawned from t635_23 during Step 8b review, while porting the three gate skills
(`aitask-run-gates`, `aitask-gate-template`, `aitask-gate-docs-updated`) to the
Codex CLI and OpenCode trees.

## Upstream defects

- `.claude/settings.local.json:30` — missing the
  `aitask_gate_{build,fail,lint,log,pass,risk,record,tests_pass}.sh` verifier
  entries that `seed/claude_settings.local.json`, `.codex/rules/default.rules`
  and `seed/opencode_config.seed.json` all carry. The **runtime** Claude policy
  is a strict subset of its own **seed** mirror, so every machine-gate verifier
  prompts for permission in this repo while a freshly-seeded consumer project
  runs them cleanly — the inverse of the intended relationship.
- `.aitask-scripts/aitask_audit_wrappers.sh:226` — `discover` still reports the
  `aitask-explorechat` GAP triple (`.agents/skills/`, `.opencode/skills/`,
  `.opencode/commands/`). It is the last plain `.claude/skills/aitask-*` skill
  with no wrapper surface in any other agent tree. Decide deliberately: either
  port it like the gate skills, or record it as a permanently Claude-only skill
  in whatever exemption mechanism `wire_discover_into_verify` introduces (that
  task needs an exemption list, and `aitask-explorechat` is its motivating
  entry). Note it is a machine-spawned chatlink gateway skill, not a user
  command — a wrapper may or may not be meaningful for it.

## Diagnostic context

t635_23 closed the wrapper gap for the three gate skills and, via
`aitask_audit_wrappers.sh apply-helper-whitelist`, the helper-whitelist gap for
`aitask_resolve_config_path.sh` (missing from all 5 touchpoints) and
`aitask_run_gates.sh` (missing from touchpoint 1). Auditing those two helpers is
what exposed that touchpoint 1 — `.claude/settings.local.json` — is systematically
behind its seed mirror for the whole `aitask_gate_*.sh` verifier family, not just
for the two helpers that task needed.

The `aitask-explorechat` triple was visible in `discover` output throughout
t635_23 but was deliberately left alone: it is not a gate skill, and porting it
was outside that task's stated scope.

## Suggested fix

For the policy gap: run
`./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist <helper>` over
the `aitask_gate_*.sh` family (and ideally every helper `discover-helpers`
reports), then `apply-helper-whitelist` the misses. Worth considering a standing
check that touchpoint 1 is never a subset of touchpoint 4, since that asymmetry
is silent today.

For `aitask-explorechat`: coordinate with the `wire_discover_into_verify`
follow-up — whichever way it is decided, `discover` should end up with an empty
report or an explicit, documented exemption.
