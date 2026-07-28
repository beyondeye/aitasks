---
priority: low
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [tui]
gates: [risk_evaluated]
anchor: 1223
created_at: 2026-07-28 17:29
updated_at: 2026-07-28 17:29
---

## Origin

Risk-mitigation ("after") follow-up for t1223_5, created at Step 8d after
implementation landed.

## Risk addressed

Code-health risk 1 of `aiplans/archived/p1223/p1223_5_settings_tab_and_push_action.md`
(severity: medium), verbatim:

> `syncer_app.py` is already 1698 lines and load-bearing for daily git sync;
> this adds a third table, a third worker group, a multi-modal write flow and
> new gating.

## Goal

`syncer_app.py` now carries **three** hand-copied refresh machines — Branches,
Versions and Settings — each a `_<x>_gen` / `_<x>_active` / `_pending_<x>`
triple plus a `_request_<x>` / `_apply_<x>` / `_finish_<x>` quartet, all routed
through the same pure `coalesce_request`. A fourth tab would add a fourth copy.

Extract one small helper (e.g. a `CoalescedRefresh` object owning the triple and
exposing `request(explicit)` / `finish()`), leaving `coalesce_request` itself
untouched as the pure policy, and migrate all three call sites.

**One invariant must survive the refactor, and is the reason this is worth
doing:** a worker whose body raises must still reach its `finish`. t1223_5 shipped
a bug where an exception escaping `_settings_worker` never reached
`_finish_settings`, leaving `_settings_active` stuck true so every later request
parked in the pending slot and the tab's reload key went silently dead for the
rest of the session. `_refresh_worker` documents the same hazard for
cancellation. Centralising the machinery is the structural fix that makes the
bad path impossible rather than something each of three copies must remember.

## Key files

- `.aitask-scripts/syncer/syncer_app.py` — `coalesce_request`, `PENDING_UNSET`,
  the three `_request_*` / `_apply_*` / `_finish_*` sets, `_on_refresh_error`,
  `_on_settings_error`, `_finish_refresh_cancelled`.
- `tests/test_syncer_rows.py` — `CoalesceRequestTests` (pure policy, must stay
  green untouched) plus the per-tab worker tests, including
  `test_a_worker_level_failure_still_unsticks_the_refresh_flag`.

## Verification

```bash
python3 tests/test_syncer_rows.py
```

Extend the stuck-flag test to cover **every** tab's worker, not just Settings —
the shared helper is what makes that a single guarantee.
