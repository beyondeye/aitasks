---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: []
verifies: [1217]
anchor: 1234
created_at: 2026-07-28 14:43
updated_at: 2026-07-28 14:43
---

Carry-over of deferred manual-verification items from t1234. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [ ] Launch `ait diffviewer` on a plan file — plan content renders (plan_loader.py, the only importer whose insert was swapped board->lib rather than dropped) — DEFER 2026-07-28 13:02 auto: diffviewer launched but selecting and visually confirming plan content requires interactive TUI navigation
- [ ] In `ait board`, edit and save a task — serialize_frontmatter round-trip is intact and boardcol/boardidx remain ordered last in the frontmatter — DEFER 2026-07-28 13:02 auto: editing and save ordering requires interactive board mutation; not performed against user task data
- [ ] Run `ait sync` against a task file with a conflict — exercises board/aitask_merge.py under aitask_sync.sh's real PYTHONPATH=board argv (no test covers that argv) — DEFER 2026-07-28 13:02 auto: real sync-conflict exercise blocked by remote fetch failure and requires a safe conflict fixture
