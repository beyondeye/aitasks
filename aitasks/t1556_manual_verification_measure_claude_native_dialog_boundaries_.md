---
priority: medium
effort: medium
depends: [1540]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1540]
anchor: 1159
followup_kind: manual_verification
created_at: 2026-08-17 19:01
updated_at: 2026-08-17 19:01
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1540

## Verification Checklist

- [ ] Launch a real `ait minimonitor`, follow a Claude pane parked at a tool-permission dialog, press `L` to arm, and confirm the banner reads armed — the real TUI keypress path (t1540's live 4b drove MiniMonitorApp programmatically, not the TUI).
- [ ] With the loop armed, move the option cursor onto option 2 ("Yes, and always allow …") and back; confirm no round is injected and no banner change. This is the specific defect t1540 fixed — before it, that move classified WORK.
- [ ] Let the followed Claude agent do real work above a live permission dialog; confirm exactly one recheck round lands in the shadow pane and the shadow actually re-reviews.
- [ ] Repeat the above in a same-window shadow split (`tmux.shadow_same_window: true`, the default) so the followed pane sits at the halved height the loop really runs in.
- [ ] Confirm at a very short pane (9 rows or fewer) that the truncated-option dialog still behaves — this is the `claude_proceed` regime, where the reported kind differs.
- [ ] Check `ait monitor` still flags Claude panes correctly at other prompts (AskUserQuestion, plan approval) — no regression from widening `claude_help_bar`.
