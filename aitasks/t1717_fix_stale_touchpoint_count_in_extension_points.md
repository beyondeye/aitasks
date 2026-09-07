---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [framework, documentation]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1657
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-06 16:55
updated_at: 2026-09-07 09:11
---

## Origin

Spawned from t1657_4 during Step 8b review.

## Upstream defect

- `aidocs/framework/aitasks_extension_points.md:319` — the prose says "surface
  this **7-touchpoint** checklist as an explicit deliverable per helper", while
  the table immediately above it lists **5** rows.

## Diagnostic context

t1657_4 added a new skill-invoked helper (`aitask_live_endpoint.sh`) and followed
the "Adding a new helper script" section to allowlist it. The table and the prose
disagree on the count, so the doc cannot be followed literally.

The table is the correct half. Verified empirically against the most recently
added helper, `aitask_note.sh` (t1657_2), which is whitelisted in exactly these
five files and no others:

    .claude/settings.local.json
    .codex/rules/default.rules
    seed/claude_settings.local.json
    seed/codex_rules.default.rules
    seed/opencode_config.seed.json

`aitask_live_endpoint.sh` was added to the same five.

## Suggested fix

Reconcile the count. Two things to check before simply changing "7" to "5",
because the number may be a stale record of a real gap rather than a typo:

1. Whether a **runtime** OpenCode config (the counterpart of
   `seed/opencode_config.seed.json`) should be a touchpoint. The table lists a
   seed entry for OpenCode but no runtime one, unlike Claude and Codex which
   each have both — so 5 may be an undercount rather than 7 an overcount.
2. Whether `.agents/` (the shared Codex/agy root named in CLAUDE.md) carries a
   permission surface that belongs in the list.

If neither adds a row, the fix is a one-word correction to the prose.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-07T06:11:43Z status=pass attempt=1 type=human
