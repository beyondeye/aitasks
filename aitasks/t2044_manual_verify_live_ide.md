---
priority: medium
effort: low
depends: [2039]
issue_type: manual_verification
status: Ready
labels: [frozen, minimonitor, tmux, ait_ide]
verifies: [2039]
anchor: 2039
followup_kind: risk_mitigation
created_at: 2026-10-16 14:57
updated_at: 2026-10-16 14:57
---

## Origin

Risk-mitigation ("after") follow-up for t2039, created at Step 8d after implementation landed.

## Risk addressed

addresses: companion acceptance only proven indirectly

- "Every viewer window has a live minimonitor" is proven by the guard live test and
  unit tests, not by booting a real minimonitor in a reopened window on the user's
  server · severity: medium · → mitigation: manual_verify_live_ide

## Goal

On the real `-L ait` server, run `ait ide` in aitasks and confirm, by hand, what
t2039's automated tests can only prove piecewise: the cross-project groups and
per-project questions, each project's viewers landing in that project's own
session, and a live minimonitor in every viewer window after V and after R —
including the viewers recreated before the fix, which the startup top-up must
repair. The two live suites that refuse to run inside tmux
(`tests/test_frozen_agents_acceptance.sh`, `tests/test_restore_flows_live.sh`)
were not run by t2039 and are part of this check.
