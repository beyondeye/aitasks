---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: test
status: Implementing
labels: [codexcli, codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1198]
assigned_to: dario-e@beyond-eye.com
anchor: 1171
implemented_with: claudecode/opus4_8
created_at: 2026-07-20 23:15
updated_at: 2026-07-21 11:07
boardidx: 50
---

## Origin

Risk-mitigation ("after") follow-up for t1185, created at Step 8d after
implementation landed.

## Risk addressed

- addresses: code-health — dual-manifest drift
- `The new helper introduces a second place (alongside install.sh's install_seed_* family) that knows the seed→metadata filename mapping, including the claude_settings.local.json → claude_settings.seed.json rename. If a future seed is added to one manifest and not the other, the two drift silently. · severity: low`

## Goal

Two independent manifests now encode the same seed→metadata filename mapping:

1. `install.sh` — the `install_seed_*()` family (`:378-706`), notably
   `install_seed_codex_config()` (`:660`), `install_seed_opencode_config()`
   (`:693`) and `install_seed_claude_settings()` (`:581`).
2. `.aitask-scripts/aitask_setup.sh` — the `pairs=()` list inside
   `ensure_agent_config_seeds()` (added by t1185).

Both must agree, including the non-identity rename
`claude_settings.local.json` → `claude_settings.seed.json`. A seed added to one
but not the other drifts silently: install-flow users would get the file while
source-tree/clean-clone users would not (or vice versa), reproducing exactly the
t1185 failure mode for a new file.

Add a test that derives both mappings from their sources and asserts they agree,
failing loudly on drift. Prefer extracting the pairs from the live source (grep
or the `--source-only` scaffold used by `tests/test_setup_agent_config_seeds.sh`)
over hardcoding a third copy of the list — a hardcoded expected list would just
become a fourth manifest to drift.

Consider whether the better structural answer is to eliminate the duplication
entirely (single shared manifest consumed by both `install.sh` and
`aitask_setup.sh`) and make the guard unnecessary; if so, propose that instead
and note the trade-off, since `install.sh` must remain standalone/self-contained
for bootstrap.

## Verification

- The guard fails when a seed pair is added to one manifest only (assert this
  with a negative control, not just the passing case).
- `bash tests/test_setup_agent_config_seeds.sh` still passes.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-21T07:38:33Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-21T07:58:00Z status=pass attempt=1 type=human
