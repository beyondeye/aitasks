---
priority: medium
effort: medium
depends: [1159_3]
issue_type: enhancement
status: Ready
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
anchor: 1159
followup_kind: review_finding
created_at: 2026-08-13 11:33
updated_at: 2026-08-13 11:33
---

Build on t1159_3 (spin-off triage arm) by making the shadow review disposition signal useful when deciding whether to park a concern as a separate follow-up task.

## Goal

Use the existing terminal free-text disposition metadata — `blocking`, `follow-up`, and `informational` — as the single deferral-safety signal. Keep it explicitly separate from concern priority (`high` / `medium` / `low`): a high-impact concern may still be safe to defer when the current task satisfies its obligations.

## Scope

- Extend the relevant shadow review producers that currently lack disposition trailers, especially plan-review outputs, using the existing canonical `Disposition: ...` terminal-body format rather than widening the parsed marker grammar.
- Preserve the implementation-review disposition rubric as the semantic authority: `blocking` means the current task must address it; `follow-up` means separable tracked work; `informational` asks for no action.
- Surface the derived disposition clearly in the minimonitor concern picker so users can recognize `follow-up` concerns while choosing forward, reject, or the t1159_3 spin-off action. A suggestion or visual hint is acceptable; do not auto-select or force spin-off.
- Ensure the t1159_3 draft-creation path continues to preserve the canonical marker line, including its disposition trailer, and its existing `followup_of` / `followup_kind: review_finding` provenance remains intact.

## Verification

Cover producer output, parser derivation/backwards compatibility, picker rendering at narrow widths, and the path that creates a spin-off draft. Verify that priority and disposition remain orthogonal and that a `follow-up` concern is suggested but never automatically spun off.

## Relationship

This is a follow-up review finding from t1159_3, not a change to its current spin-off foundation. It depends on t1159_3 being implemented first and should cross-reference the t1159 shadow review loop automation parent design where needed.
