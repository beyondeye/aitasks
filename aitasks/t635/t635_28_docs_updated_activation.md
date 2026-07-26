---
priority: medium
effort: low
depends: [t635_27]
issue_type: chore
status: Ready
labels: [gates]
anchor: 635
created_at: 2026-07-01 10:46
updated_at: 2026-07-26 00:00
---

## Context

t635_19 shipped the `docs_updated` procedure gate **dormant** (registry-present,
not in any profile `default_gates`). Auto-enabling an unproven work-gate on every
pick is high blast-radius, so it ships opt-in. This task flips it on once the
live-verify MV (t635_27) proves acceptable signal/noise.

## Scope
- Add `docs_updated` to `fast.yaml` `default_gates` (currently `[risk_evaluated]`)
  so it becomes the always-on per-task documentation checkpoint the framework
  intends. Confirm the Step-7 backfill + Step-8 dispatch behave for a task that
  now declares it by default.
- Gated on t635_27 (live-verify) passing — do not enable until proven.

## Premise refresh (2026-07-26 — t635_33 active-gates model)

This task was last updated 2026-07-01; **t635_33 landed 2026-07-19**, making
profile gate declaration two-keyed and render-time. Verified against live source
so the activation is done for the right reasons:

- **The one-line edit still works, and still activates.** `fast.yaml` has
  `default_gates: [risk_evaluated]` and **no `rendered_gates` key**.
  `gate_ledger._read_profile_rendered_gates` keys off *presence*:
  `rendered_gates` wins whenever the key exists (even `[]`), otherwise
  `default_gates` is the ceiling. So adding `docs_updated` to `default_gates`
  raises fast's render ceiling **and** its enforced set — no second key needed.
- **No re-render or golden regeneration is required.** `rendered_set` is
  injected into the Jinja context (`skill_template.render_skill`), but the
  task-workflow templates currently test it **only** for `risk_evaluated`
  (`SKILL.md:354,364,549`, `planning.md:163,308,309,398`). No block keys off
  `docs_updated`, so the rendered `task-workflow-fast-/SKILL.md` is
  byte-identical after the change. Re-rendering is a harmless no-op — do not
  budget for goldens churn. **Verify this still holds at pick time**: if any
  earlier task adds a `'docs_updated' in rendered_set` block, this stops being
  true and the fast variant must be re-rendered with goldens in the same commit.
- **The dispatch it activates is already rendered for fast.** The Step-8
  procedure-gate block is wrapped in `{%- if profile.record_gates … %}` alone
  (fast has `record_gates: true`) and is generic over `kind: procedure`. At
  runtime it calls `aitask_gate.sh procedure-gates`, which resolves from the
  **enforced active set** (`gate_ledger.unmet_procedure_gates:1056`). So
  activation flows through existing machinery; nothing new renders.
- **Blast radius is narrower than it looks.** `default.yaml` declares no gate
  keys at all and `remote.yaml` declares `rendered_gates: []` with no
  `record_gates` — neither renders the procedure dispatch, and both enforce
  nothing. This flip therefore touches **only** the `fast` profile. The real
  exposure is an attended fast-profile run under Codex CLI or OpenCode, where
  the gate skill does not exist in the agent's tree until **t635_23** lands
  (see Coordination below).

## Coordination
Depends on t635_27 (docs_updated_live_verify). Reverse pointer added there.

**Advisory ordering (not a hard `depends`)** — land after **t635_23** (ports the
gate skills to the Codex/OpenCode trees) and **t635_29** (agent-aware dispatch
resolution with its fail-safe unmet report). Until t635_23 lands, `docs_updated`
is Claude-only; activating first makes it mandatory on every fast-profile pick
including runs under agents whose tree cannot resolve the verifier skill, which
leaves archival blocked with no in-session remedy.
