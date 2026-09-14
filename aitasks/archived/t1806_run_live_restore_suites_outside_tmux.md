---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Done
labels: [tmux]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: risk_mitigation
created_at: 2026-09-14 16:52
updated_at: 2026-09-14 17:19
completed_at: 2026-09-14 17:19
---

## Origin

Risk-mitigation ("after") follow-up for t1802, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — the composed restore path is only provable by the live suites, which refuse to run inside tmux

- Unit tests prove each half separately, for both modes. Only the live suites prove the composed hook → store → coordinator path, and they cannot run inside this tmux session. · severity: medium · → mitigation: run_live_restore_suites_outside_tmux

## Goal

t1802 (commit 85ed142f6) did two things. The restore coordinator now delivers `AITASK_AGENT_STRING` to a restored agent, and a blank agent string is now a no-op in the session store. Unit tests cover both halves. The live suites that exercise the composed hook → store → coordinator path were extended, but they could not run in the implementing session, because it ran on the `-L ait` tmux server those suites require stopped. Run them from a plain terminal and confirm the new assertions. Include a pre-fix control for the environment assertions, because the record assertions pass on the store guard alone.

## Verification Checklist

- [x] From a terminal NOT inside tmux, with the `-L ait` server stopped, `bash tests/test_frozen_agents_acceptance.sh` passes, including the t1802 assertions in Cases 5 and 6c: the replacement's environment report has `AITASK_AGENT_STRING=claudecode/opus5`, and the record keeps `agent_string` and `agent_kind` — PASS 2026-09-14 17:15 auto: run from a non-tmux shell with -L ait stopped; 160/160 passed (cases 5 and 6c included); the t1802 env assertions are proven live by item 3's pre-fix control
- [x] In the same terminal, `bash tests/test_restore_flows_live.sh` passes, including the t1802 assertions in Case 1 (resume) and Case 2 (re-pick) — PASS 2026-09-14 17:15 auto: run 1 failed Case 1 at restore preflight (RESTORE_FAILED|no_session) before any t1802 code ran; a pre-existing fixture race (freeze before the hook stamps the pane blanks the seeded session id) reproduced deterministically and filed as a follow-up; run 2 passed 84/84 with the Case 1 and Case 2 t1802 assertions
- [x] Pre-fix control: with the `.aitask-scripts/lib/agent_restore.py` part of 85ed142f6 temporarily reverted, re-run both suites and confirm the `AITASK_AGENT_STRING` environment assertions FAIL. The record assertions may still pass, because the store guard alone satisfies them. Then restore the change. — PASS 2026-09-14 17:18 auto: with the agent_restore.py hunk of 85ed142f6 reverted, exactly the four AITASK_AGENT_STRING env assertions failed (acceptance cases 5 and 6c: 158/160; restore-flows cases 1 and 2: 82/84) and every record assertion still passed; file restored via git checkout, tree clean
