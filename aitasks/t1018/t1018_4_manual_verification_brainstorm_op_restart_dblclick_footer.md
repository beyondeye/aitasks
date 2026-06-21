---
priority: medium
effort: medium
depends: [t1018_1, t1018_2, t1018_3]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [t1018_1, t1018_2, t1018_3]
anchor: 1018
created_at: 2026-06-21 10:23
updated_at: 2026-06-21 10:24
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1018_1] The replacement alt+<letter> preview keys (ratio / numbered) actually fire through the real ghostty->tmux->Textual stack inside tmux (headless pilot cannot prove delivery; this is the original chord-delivery bug class).
- [ ] [t1018_1] No retry-apply binding leaks into the footer on tabs/screens where it is irrelevant; each shows only on its owning surface.
- [ ] [t1018_1] A focused wizard TextArea ignores the new alt+<letter> keys (typing is unaffected).
- [ ] [t1018_2] On a real session with a genuinely failed operation (agents in Error within a Waiting group), "Re-run whole operation fresh" relaunches the agents from scratch and produces output.
- [ ] [t1018_2] "Re-run fresh" surfaces the pre-filled wizard / a destructive-action confirm before relaunching, and offers to clean up the old failed group.
- [ ] [t1018_2] "Retry only the failed step" re-applies a completed agent's output without relaunching the whole operation.
- [ ] [t1018_2] The old ctrl+shift+x / ctrl+shift+y retry-apply chords are gone and their function is reachable from the focused GroupRow.
- [ ] [t1018_3] A real mouse double-click on a Running-tab operation (group) row expands/collapses it (same as Enter); single-click still only focuses, and Enter still toggles (no regression).
- [ ] [t1018_3] The focused operation group keeps focus across a status refresh (let the Running tab auto-refresh, or trigger an agent action, while a group is focused — focus is retained, not dropped).
- [ ] [t1018_3] Hovering the focused operation group shows a shade of the focus accent (orange), not the gray hover background.
