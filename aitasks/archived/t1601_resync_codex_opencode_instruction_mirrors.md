---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [documentation]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1595
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-25 12:27
updated_at: 2026-08-25 16:45
completed_at: 2026-08-25 16:45
---

## Origin

Spawned from t1595 during Step 8b review.

## Upstream defect

- `.codex/instructions.md` / `.opencode/instructions.md` — the `>>>aitasks`
  task-format YAML block in both mirrors is missing the `gates:` and the four
  `active_gates*` lines that `seed/aitasks_agent_instructions.seed.md` and
  `AGENTS.md` both carry. The two mirrors are otherwise byte-identical to the
  seed block.

## Diagnostic context

Noticed while adding the `plan_approved_at` field to all four task-format
surfaces in t1595. Inserting the same block into each mirror left the new field
consistent, but a `diff` of the YAML blocks showed the five pre-existing missing
lines in the Codex and OpenCode copies.

The cause is documented in `aidocs/framework/aitasks_extension_points.md`
("Adding a new frontmatter field", layer 5): both mirror regenerations run
through `ait setup` and are **gated on the corresponding agent CLI being
installed locally** (`_is_agent_installed` → `setup_codex_cli` /
`setup_opencode`). On a machine without those CLIs, `ait setup` prints
"No … staging files found — skipping" and leaves the tracked files untouched,
so a field added to the seed lands in `AGENTS.md` only and the mirrors drift
silently. That is exactly what happened for the gate fields.

## Suggested fix

Copy the generated block out of `AGENTS.md` verbatim into both mirrors so all
four surfaces match the seed byte for byte (the doc prescribes exactly this
recovery). Then consider a drift guard: a small test asserting the `>>>aitasks`
block is identical across `seed/aitasks_agent_instructions.seed.md`,
`AGENTS.md`, `.codex/instructions.md` and `.opencode/instructions.md` would turn
this silent, install-dependent drift into a failing test — the same
single-source-plus-guard shape used elsewhere in the framework.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-25T13:21:27Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-25T13:36:32Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-25T13:45:36Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:48cc6cd5c8f029f0

> **✅ gate:risk_evaluated** run=2026-08-25T13:45:36Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1601/risk_evaluated_2026-08-25T13:45:36Z-risk_evaluated-a1.log`
