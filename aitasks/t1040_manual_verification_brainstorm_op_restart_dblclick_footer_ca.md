---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Implementing
labels: []
verifies: [t1018_1, t1018_2, t1018_3]
assigned_to: dario-e@beyond-eye.com
anchor: 1018
created_at: 2026-06-21 13:58
updated_at: 2026-06-24 18:28
---

Carry-over of deferred manual-verification items from t1018_4. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [ ] [t1018_1] The replacement alt+<letter> preview keys (ratio / numbered) actually fire through the real ghostty->tmux->Textual stack inside tmux (headless pilot cannot prove delivery; this is the original chord-delivery bug class). — DEFER 2026-06-21 13:57 requires real ghostty->tmux terminal delivery; detached tmux send-keys cannot prove ghostty delivery, though focused unittest key-dispatch coverage passed
- [ ] [t1018_2] On a real session with a genuinely failed operation (agents in Error within a Waiting group), "Re-run whole operation fresh" relaunches the agents from scratch and produces output. — DEFER 2026-06-21 13:57 existing failed synthesize_001 found, but detached tmux could not reliably focus the row to launch n; no live relaunch attempted to avoid mutating wrong operation
- [ ] [t1018_2] "Retry only the failed step" re-applies a completed agent's output without relaunching the whole operation. — DEFER 2026-06-21 13:57 no safe live completed-output apply scenario was driven; unittest coverage verifies i dispatch calls the grouped applier without relaunch
