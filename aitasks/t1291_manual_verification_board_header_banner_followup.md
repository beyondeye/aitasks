---
priority: medium
effort: medium
depends: [1278]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1278]
created_at: 2026-07-28 12:05
updated_at: 2026-07-28 12:05
boardidx: 59392
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1278

## Verification Checklist

- [ ] Re-run the item this task exists to fix: in a live `ait board`, enter By-Trail with a real trail and press `d` — the header row returns to `⟳ checking freshness…` and then settles on `⚠ stale: N`, while detail-bearing drift markers appear on the owning cards (including an archived member drawn as a ghost card)
- [ ] Confirm the header row is drawn at all in a normal terminal: row 0 reads `aitasks board — Auto-refresh: off` (or `Auto-refresh: Nmin`) outside By-Trail, in every base filter
- [ ] Change the auto-refresh setting from the board settings action and confirm the header row text updates to match — this text was invisible for the app's entire history, so it has never been eyeballed
- [ ] With a stale trail active, resize the terminal down to ~80 and then ~60 columns: `⚠ stale: N` must stay fully readable at both, with the trail title eliding (…) instead of the marker being cut off
- [ ] Repeat the resize check while the banner is in the `⟳ checking freshness…` state (press `d` and resize before it settles): the marker must survive to ~55 columns; below that it is documented to clip
- [ ] Confirm the board lost no vertical space: the lanes still start immediately below the filter row with a single blank separator row, and the same number of cards fit on screen as before the change
- [ ] Confirm the narrow-terminal filter reflow still behaves: below ~100 columns the search box drops onto its own line and the header row is still drawn above it
- [ ] Open a trail whose title is very long and confirm the header reads sensibly (title elided mid-string, marker intact) rather than truncating at the right edge
- [ ] TODO: verify .aitask-scripts/board/aitask_board.py end-to-end in tmux (interactive surface touched by this task's commit)
