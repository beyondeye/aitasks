---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: []
verifies: [t1223_1, t1223_2, t1223_3, t1223_4, t1223_5, t1223_6]
anchor: 1223
created_at: 2026-07-31 12:11
updated_at: 2026-07-31 12:11
boardidx: 930
---

Carry-over of deferred manual-verification items from t1223_7. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [ ] [t1223_3] Upgrade a scratch repo (no live session) to a pinned version: a shell spawns rooted in that repo, State reads `upgrading…` while the pane lives, then `re-check needed` once it exits. — DEFER 2026-07-31 12:10
- [ ] [t1223_3] Attempt to upgrade the repo the syncer is running from: the TUI EXITS FIRST, then the upgrade runs in the vacated window. Confirm nothing under `.aitask-scripts/` changed while the TUI was still alive. — DEFER 2026-07-31 11:45 auto: requires live self-upgrade handoff and process-lifecycle observation
- [ ] [t1223_3] Run `ait syncer` and quit with `Ctrl-C`: the temporary handoff directory is gone afterwards (no leftover under the mktemp root). — DEFER 2026-07-31 11:45 auto: requires live Ctrl-C handoff cleanup observation
- [ ] [t1223_6] `cd website && hugo build --gc --minify` succeeds with no broken relref, and the syncer page renders correctly in the local dev server. — DEFER 2026-07-31 11:45 auto: Hugo build passed; local dev-server visual rendering needs human observation
- [ ] [t1223_6] Read the published syncer page: the active-target refusal, the declared tmux-scoped detection bound, the self-upgrade exit, the "launched / result unknown" reporting, and the settings layer prompt with masking are each documented and match the as-built behavior observed above. — DEFER 2026-07-31 11:45 auto: documentation text inspected; live behavior comparison needs human observation
