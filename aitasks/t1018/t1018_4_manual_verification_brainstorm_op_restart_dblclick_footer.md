---
priority: medium
effort: medium
depends: [t1018_1, t1018_2, t1018_3]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t1018_1, t1018_2, t1018_3]
assigned_to: dario-e@beyond-eye.com
anchor: 1018
created_at: 2026-06-21 10:23
updated_at: 2026-06-21 13:57
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [defer] [t1018_1] The replacement alt+<letter> preview keys (ratio / numbered) actually fire through the real ghostty->tmux->Textual stack inside tmux (headless pilot cannot prove delivery; this is the original chord-delivery bug class). — DEFER 2026-06-21 13:57 requires real ghostty->tmux terminal delivery; detached tmux send-keys cannot prove ghostty delivery, though focused unittest key-dispatch coverage passed
- [fail] [t1018_1] No retry-apply binding leaks into the footer on tabs/screens where it is irrelevant; each shows only on its owning surface. — FAIL 2026-06-21 13:54 follow-up t1039
- [x] [t1018_1] A focused wizard TextArea ignores the new alt+<letter> keys (typing is unaffected). — PASS 2026-06-21 13:57 python -m unittest focused suite passed; alt+w key dispatch does not corrupt focused TextArea text
- [defer] [t1018_2] On a real session with a genuinely failed operation (agents in Error within a Waiting group), "Re-run whole operation fresh" relaunches the agents from scratch and produces output. — DEFER 2026-06-21 13:57 existing failed synthesize_001 found, but detached tmux could not reliably focus the row to launch n; no live relaunch attempted to avoid mutating wrong operation
- [x] [t1018_2] "Re-run fresh" surfaces the pre-filled wizard / a destructive-action confirm before relaunching, and offers to clean up the old failed group. — PASS 2026-06-21 13:57 unittest test_n_reruns_via_preseeded_wizard passed; code path opens pre-seeded ActionsWizardScreen and then offers old-group cleanup
- [defer] [t1018_2] "Retry only the failed step" re-applies a completed agent's output without relaunching the whole operation. — DEFER 2026-06-21 13:57 no safe live completed-output apply scenario was driven; unittest coverage verifies i dispatch calls the grouped applier without relaunch
- [x] [t1018_2] The old ctrl+shift+x / ctrl+shift+y retry-apply chords are gone and their function is reachable from the focused GroupRow. — PASS 2026-06-21 13:57 static grep confirms ctrl+shift+x/y bindings are gone; focused unittest suite verifies i retry-apply is exposed/called from GroupRow
- [x] [t1018_3] A real mouse double-click on a Running-tab operation (group) row expands/collapses it (same as Enter); single-click still only focuses, and Enter still toggles (no regression). — PASS 2026-06-21 13:57 live tmux mouse sequence double-clicked synthesize_001 and expanded it; Enter collapsed it; unittest covers single-click focus/no-toggle
- [x] [t1018_3] The focused operation group keeps focus across a status refresh (let the Running tab auto-refresh, or trigger an agent action, while a group is focused — focus is retained, not dropped). — PASS 2026-06-21 13:57 after a real 32s Running-tab refresh wait, focused synthesize_001 still rendered its focus hint
- [x] [t1018_3] Hovering the focused operation group shows a shade of the focus accent (orange), not the gray hover background. — PASS 2026-06-21 13:57 code inspection confirms GroupRow:focus:hover uses accent-lighten-1; text capture cannot display color
