---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [whitelists, codeagent]
assigned_to: dario-e@beyond-eye.com
implemented_with: codex/gpt5_5
created_at: 2026-06-15 08:30
updated_at: 2026-06-15 10:12
---

## Problem

`./.aitask-scripts/aitask_project_resolve.sh` is invoked **autonomously by skills** (not user-typed) yet is not whitelisted in any code-agent permission touchpoint. Every cross-repo skill run therefore triggers a permission prompt for this helper, breaking the no-latency / autonomous (remote) intent — and because the **seed** mirrors are also missing it, every freshly-bootstrapped project inherits the gap.

## Callers (autonomous)

- `aitask-explore` — cross-repo scope detection (`aitask_project_resolve.sh list` and `... <name>`)
- `task-workflow` — `planning-cross-repo.md` and `parallel-cross-repo-planning.md`

## Evidence

`./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_project_resolve.sh` reports it MISSING from all 5 live touchpoints:

- `1` → `.claude/settings.local.json` (Claude Code)
- `3` → `.codex/rules/default.rules` (Codex CLI)
- `4` → `seed/claude_settings.local.json` (seed mirror of #1)
- `6` → `seed/codex_rules.default.rules` (seed Codex)
- `7` → `seed/opencode_config.seed.json` (seed OpenCode)

## Fix

Run the framework's own injector, which covers all touchpoints:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_project_resolve.sh
```

Then re-run `audit-helper-whitelist aitask_project_resolve.sh` to confirm zero MISSING lines.

## Secondary candidate

`aitask_projects.sh` (the `ait projects` wrapper) shows the identical MISSING pattern across the same 5 touchpoints. It is user-facing (`ait projects`) rather than skill-invoked, so it is lower priority — decide during implementation whether to whitelist it in the same pass.

See `aidocs/framework/skill_authoring_conventions.md` (helper-script whitelist coverage) and the `aitask-audit-wrappers` skill.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-15T07:12:22Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-15T07:12:30Z status=pass attempt=1 type=machine
