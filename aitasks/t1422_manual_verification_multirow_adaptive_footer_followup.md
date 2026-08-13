---
priority: medium
effort: medium
depends: [1418]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1418]
followup_kind: manual_verification
created_at: 2026-08-05 10:51
updated_at: 2026-08-13 23:07
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1418

## Verification Checklist

- [ ] Click a footer key with the mouse in a real terminal (e.g. `n New Task`) and confirm it fires — click-to-fire is inherited from FooterKey.on_mouse_down and was never exercised by a mouse in testing.
- [ ] Click a footer key on the SECOND and THIRD rows specifically, confirming the hit region follows the reflowed position rather than the original single-row layout.
- [ ] Set `footer_max_rows: 1` in aitasks/metadata/userconfig.yaml, relaunch `ait board`, and confirm the footer is one row with a `+N more (?)` marker; then set `2`, relaunch, confirm two rows.
- [ ] Set `footer_max_rows` to garbage (e.g. `banana`) and confirm the board still launches with the default 3 rows rather than crashing.
- [ ] Launch `ait board` in a short terminal (e.g. 20 rows) and confirm the taller footer leaves the board usable — cards still render, scrolling still works, nothing is cut off.
- [ ] Resize a real terminal slowly across the ~440 / ~200 / ~120 column thresholds and confirm the footer reflows without flicker, duplicated rows, or leftover painted text.
- [ ] Press Escape to focus the board and confirm `m Move to Col`, `X Collapse Col`, `^↑ Task Top` and `^↓ Task Btm` are all visible and actually fire.
- [ ] Confirm `^p palette` stays anchored bottom-right on every row count, and that ctrl+p still opens the command palette.
- [ ] Switch board views (a / l / f / i / y / z) and confirm the footer re-flows correctly as check_action hides and shows keys, with no stale rows.
- [ ] TODO: verify .aitask-scripts/board/aitask_board.py end-to-end in tmux
