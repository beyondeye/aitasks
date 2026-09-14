---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Implementing
labels: [tmux]
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: risk_mitigation
created_at: 2026-09-14 16:52
updated_at: 2026-09-14 17:06
---

## Origin

Risk-mitigation ("after") follow-up for t1802, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — the composed restore path is only provable by the live suites, which refuse to run inside tmux

- Unit tests prove each half separately, for both modes. Only the live suites prove the composed hook → store → coordinator path, and they cannot run inside this tmux session. · severity: medium · → mitigation: run_live_restore_suites_outside_tmux

## Goal

t1802 (commit 85ed142f6) did two things. The restore coordinator now delivers `AITASK_AGENT_STRING` to a restored agent, and a blank agent string is now a no-op in the session store. Unit tests cover both halves. The live suites that exercise the composed hook → store → coordinator path were extended, but they could not run in the implementing session, because it ran on the `-L ait` tmux server those suites require stopped. Run them from a plain terminal and confirm the new assertions. Include a pre-fix control for the environment assertions, because the record assertions pass on the store guard alone.

## Verification Checklist

- [ ] From a terminal NOT inside tmux, with the `-L ait` server stopped, `bash tests/test_frozen_agents_acceptance.sh` passes, including the t1802 assertions in Cases 5 and 6c: the replacement's environment report has `AITASK_AGENT_STRING=claudecode/opus5`, and the record keeps `agent_string` and `agent_kind`
- [ ] In the same terminal, `bash tests/test_restore_flows_live.sh` passes, including the t1802 assertions in Case 1 (resume) and Case 2 (re-pick)
- [ ] Pre-fix control: with the `.aitask-scripts/lib/agent_restore.py` part of 85ed142f6 temporarily reverted, re-run both suites and confirm the `AITASK_AGENT_STRING` environment assertions FAIL. The record assertions may still pass, because the store guard alone satisfies them. Then restore the change.
