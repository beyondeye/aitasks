---
priority: medium
effort: low
depends: [t635_27]
issue_type: chore
status: Ready
labels: [gates]
anchor: 635
created_at: 2026-07-01 10:46
updated_at: 2026-07-01 10:46
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

## Coordination
Depends on t635_27 (docs_updated_live_verify). Reverse pointer added there.
