---
priority: medium
effort: medium
depends: [1622]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1622]
anchor: 1598
followup_kind: manual_verification
created_at: 2026-08-26 17:42
updated_at: 2026-08-26 17:42
boardcol: now
boardidx: 14406
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1622

## Verification Checklist

- [ ] Launch `ait minimonitor` beside a live agent: it paints and accepts input immediately at boot — the up-to-5s dead window is gone.
- [ ] Press `m` in the first instants after minimonitor boots, before the seed lands: the refusal reads "Own window not detected yet", NOT "Not inside tmux".
- [ ] After boot settles, press `m` in minimonitor: it switches to the full monitor with the companion agent focused (proves `_own_window_name` was seeded).
- [ ] Press `k` / Enter in minimonitor: the sibling action targets the followed agent pane, never the shadow pane (t1382 hazard).
- [ ] Leave a minimonitor as the only remaining pane in its window: it still auto-closes after the grace period — proves `_own_window_id` was seeded. A regression here silently DISABLES auto-close and no unit test can observe it live.
- [ ] Run `ait monitor` with the data branch behind origin: the session bar shows `desync: <ref> N↓`.
- [ ] In the full monitor, toggle auto-switch (`a`) repeatedly: the desync string stays on the bar from cache instead of blanking on each keypress.
- [ ] Set `tmux.minimonitor.session_bar: true`: the compact bar shows `↓N`, and neither boot nor refresh stalls.
- [ ] Against a deliberately slow or wedged tmux server, boot both TUIs: neither blocks at mount.
