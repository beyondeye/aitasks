---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: []
verifies: [t1018_1, t1018_2, t1018_3]
anchor: 1018
created_at: 2026-06-24 18:43
updated_at: 2026-06-24 18:43
boardidx: 160
---

Carry-over of deferred manual-verification items from t1040. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [ ] [t1018_1] The replacement alt+<letter> preview keys (ratio / numbered) actually fire through the real ghostty->tmux->Textual stack inside tmux (headless pilot cannot prove delivery; this is the original chord-delivery bug class). — DEFER 2026-06-24 18:29 auto 2026-06-24: focused unittest support passed via python -m unittest tests.test_brainstorm_proposal_preview; pytest unavailable in active env; no safe API access to prove real ghostty->tmux terminal delivery, so live-only check remains deferred
- [ ] [t1018_2] On a real session with a genuinely failed operation (agents in Error within a Waiting group), "Re-run whole operation fresh" relaunches the agents from scratch and produces output. — DEFER 2026-06-24 18:29 auto 2026-06-24: focused GroupRow recovery unittest passed via python -m unittest tests.test_brainstorm_group_recovery; pytest unavailable in active env; no safe live failed operation was targeted through a real ghostty session, so relaunch/output proof remains deferred
- [ ] [t1018_2] "Retry only the failed step" re-applies a completed agent's output without relaunching the whole operation. — DEFER 2026-06-24 18:29 auto 2026-06-24: focused GroupRow recovery unittest passed via python -m unittest tests.test_brainstorm_group_recovery and binding scope unittest passed; pytest unavailable in active env; no safe live completed-output apply scenario was driven, so retry-only proof remains deferred
