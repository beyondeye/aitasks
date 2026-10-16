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

## Verification Checklist

- [ ] On the real -L ait server, run `ait ide` in aitasks: the frozen-agent list shows one group per project (aitasks first, then thinking_backend, thinking_app) and asks one V/R/P/S question per project it may act on
- [ ] Answer V for thinking_backend: its viewers come back in its own session `thinking_back` (not in `aitasks`), and the closing line names that session
- [ ] thinking_app (view-only records, its session `thinkingapp` gone): V creates its own session through the bootstrap; S leaves the records listed in `ait frozenagent`
- [ ] Every viewer window recreated by V shows a live minimonitor pane that stays up, even though the `monitor` window is the active one
- [ ] The viewers recreated before this fix (no minimonitor) get one at the next `ait ide` start, and the startup prints "Companions: N viewer window(s) got their minimonitor back."
- [ ] Restore one agent with R (and another from its viewer): the restored agent's window has exactly one minimonitor
- [ ] Start `ait ide` in two terminals at nearly the same moment: no window ends up with two minimonitors
- [ ] `ait ide --help` describes the cross-project behaviour; `ait ide --no-frozen-check` skips both the offer and the minimonitor top-up
- [ ] From a terminal NOT inside tmux, run `bash tests/test_frozen_agents_acceptance.sh` and `bash tests/test_restore_flows_live.sh` (they refuse to run inside tmux) and confirm both pass
- [ ] In codebrowser, open the create-task dialog from a codebrowser window that is not the session's current window: the "split into this window" default names the codebrowser's own window
